"""Replay each selected chart and verify captured PPU pixels in MesenCE."""
import argparse
import concurrent.futures
import json
import subprocess
import sys
from pathlib import Path
from verification_data import identity
from run_mesen_campaign import suite_digest


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
    frozen = identity(pack / 'adofai.sfc')
    suite = suite_digest()
    results = []

    def verify(level):
        index = levels.index(level) + 1
        stages = [
            [sys.executable, 'tools/run_mesen_campaign.py', '--pack', args.pack,
             '--levels', str(index), '--autoplay', '--sampled-graphics', '--resume'],
            [sys.executable, 'tools/verify_mesen_ppu.py', '--pack', args.pack,
             '--level', str(index), '--folder', str(pack / f'verification/mesen-{index}-autoplay')],
        ]
        with (folder / f'{level}.log').open('w') as log:
            for command in stages:
                process = subprocess.run(command, cwd=root, stdout=log, stderr=subprocess.STDOUT)
                if process.returncode:
                    return dict(id=level, local=index, passed=False, stage=Path(command[1]).name)
        return dict(id=level, local=index, passed=True)

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
    assert identity(pack / 'adofai.sfc') == frozen, 'Pack changed during verification'
    assert suite_digest() == suite, 'Verification suite changed during verification'
    if not all(r['passed'] for r in results):
        raise SystemExit('Catalog verification failed; inspect per-chart logs')


if __name__ == '__main__':
    main()
