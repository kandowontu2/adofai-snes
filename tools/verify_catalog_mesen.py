"""Replay each selected chart and verify captured PPU pixels in MesenCE."""
import argparse
import concurrent.futures
import json
import shutil
import subprocess
import sys
from pathlib import Path
from verification_data import identity,freeze_data_identity
from run_mesen_campaign import suite_digest


def empty_startup_failure(log_path, replay_folder):
    """Recognize a silent process failure within five seconds of launch."""
    message = log_path.read_text()
    if not any(f'Mesen exited {code} without a result' in message
               for code in (4294967295, 3221226505)):
        return False
    emulator_log = replay_folder / 'emulator.log'
    config = replay_folder / 'config.lua'
    if not emulator_log.exists() or not config.exists() or emulator_log.stat().st_size:
        return False
    # Preparing a replay hashes the large master data before writing its config.
    # Measure Mesen's lifetime, rather than including that preparation time.
    return 0 <= emulator_log.stat().st_mtime - config.stat().st_mtime < 5


def script_watchdog_failure(replay_folder):
    """A host Lua callback deadline, distinct from any game assertion."""
    result = replay_folder / 'result.txt'
    if not result.exists():return False
    lines = result.read_text().splitlines()
    return (len(lines)==2 and lines[1]=='FAIL' and
            lines[0].endswith('Maximum execution time (1 seconds) exceeded.'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pack', required=True)
    parser.add_argument('--ids', type=int, nargs='+')
    parser.add_argument('--workers', type=int, default=2)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    pack = root / 'build/packs' / args.pack
    levels = json.loads((pack / 'pack.json').read_text())['levels']
    selected = args.ids or levels
    assert len(set(selected)) == len(selected) and set(selected) <= set(levels)
    folder = pack / 'verification/catalog'
    folder.mkdir(parents=True, exist_ok=True)
    frozen = identity(pack / 'adofai.sfc', fresh=True)
    freeze_data_identity(pack / 'adofai.sfc', frozen)
    suite = suite_digest()
    results = []
    # Track-pixel checks do not cover the shared menu/background/font region.
    # Reject a broken wide-atlas VRAM layout before running the song sweep.
    if 'WIDE_SNAPSHOT_SUPPORT = 1' in (pack / 'addresses.inc').read_text():
        subprocess.run([sys.executable, 'tools/verify_background_vram_mesen.py',
                        '--pack', args.pack, '--levels', str(selected[0]),
                        '--tag', 'catalog', '--boot-only'], cwd=root, check=True)

    def verify(level):
        index = levels.index(level) + 1
        startup_retry = False
        stages = [
            [sys.executable, 'tools/run_mesen_campaign.py', '--pack', args.pack,
             '--levels', str(index), '--autoplay', '--sampled-graphics', '--resume'],
            [sys.executable, 'tools/verify_mesen_ppu.py', '--pack', args.pack,
             '--level', str(index), '--folder', str(pack / f'verification/mesen-{index}-autoplay')],
        ]
        with (folder / f'{level}.log').open('w') as log:
            for command in stages:
                process = subprocess.run(command, cwd=root, stdout=log, stderr=subprocess.STDOUT)
                # Concurrent Mesen instances can occasionally exit immediately
                # without booting or emitting output. Retry that narrow startup
                # failure once; runtime assertions and timeouts still fail.
                if (process.returncode and Path(command[1]).name == 'run_mesen_campaign.py'
                        and empty_startup_failure(folder / f'{level}.log',
                                                  pack / f'verification/mesen-{index}-autoplay')):
                    startup_retry = True
                    print('Retrying empty Mesen startup exit once', file=log, flush=True)
                    process = subprocess.run(command, cwd=root, stdout=log, stderr=subprocess.STDOUT)
                if process.returncode:
                    return dict(id=level, local=index, passed=False, stage=Path(command[1]).name)
        return dict(id=level, local=index, passed=True, startup_retry=startup_retry)

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        jobs = {pool.submit(verify, level): level for level in selected}
        for job in concurrent.futures.as_completed(jobs):
            try:
                result = job.result()
            except Exception as error:
                result = dict(id=jobs[job], passed=False, error=repr(error))
            results.append(result)
            report = dict(**frozen, suite_digest=suite, requested=selected,
                          complete=len(results) == len(selected),
                          passed=len(results) == len(selected) and all(r['passed'] for r in results),
                          results=sorted(results, key=lambda r: r['id']))
            (folder / 'results.json').write_text(json.dumps(report, indent=2))
            print(json.dumps(result), flush=True)
    # Heavy host I/O can interrupt a Lua callback for its one-second budget.
    # Once the concurrent batch drains, retry that exact failure once in
    # isolation. Preserve its original log; never retry gameplay assertions.
    for row in results:
        level=row['id'];index=levels.index(level)+1
        if (not row['passed'] and row.get('stage')=='run_mesen_campaign.py' and
                script_watchdog_failure(pack/f'verification/mesen-{index}-autoplay')):
            shutil.copyfile(folder/f'{level}.log',folder/f'{level}-host-watchdog.log')
            retried=verify(level);row.clear();row.update(retried,host_watchdog_retry=True)
            print(json.dumps(row),flush=True)
    report = dict(**frozen,suite_digest=suite,requested=selected,complete=True,
                  passed=all(r['passed'] for r in results),results=sorted(results,key=lambda r:r['id']))
    (folder/'results.json').write_text(json.dumps(report,indent=2))
    assert identity(pack / 'adofai.sfc', fresh=True) == frozen, 'Pack changed during verification'
    assert suite_digest() == suite, 'Verification suite changed during verification'
    if not all(r['passed'] for r in results):
        raise SystemExit('Catalog verification failed; inspect per-chart logs')


if __name__ == '__main__':
    main()
