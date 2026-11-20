"""Render a compiled catalog, retaining each source frame and gameplay pixel.

The VFX switch removes optional decorations only. Gameplay replacements and
the Neo Cosmos T3 scenes remain present in both settings. Inputs are copied
before rendering, so a failed job cannot change the raw compiler cache.
"""
import argparse
import concurrent.futures
import hashlib
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def optional_scenery(data, chart):
    from gameplay_decorations import is_gameplay
    if chart['id'] in (68, 73):  # T3 gameplay scenes are never optional.
        return False
    if not any(chart.get(k) for k in ('decoration_tracks', 'maze_decoration_tracks')):
        return False
    whitelist = chart.get('decoration_gameplay_images')
    return any(not is_gameplay(d, chart) and
               (not whitelist or d.get('decorationImage') in whitelist)
               for d in data.get('featured_decorations', []))


def atomic_json(path, value):
    temporary = path.with_suffix('.json.new')
    temporary.write_text(json.dumps(value, indent=2), encoding='utf-8')
    for attempt in range(100):
        try:
            temporary.replace(path)
            return
        except PermissionError:
            if attempt==99:raise
            time.sleep(.05)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--catalog', type=Path, required=True)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--workers', type=int, default=2)
    parser.add_argument('--levels', type=int, nargs='+')
    parser.add_argument('--report',type=Path,help='Write this batch separately when repairing part of a catalog')
    parser.add_argument('--reuse-failed-projections',action='store_true',help='Re-encode complete frozen failed frames; independent PPU verification is still required')
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    ids = args.levels or json.loads(args.catalog.read_text())['levels']
    priority = [n for n in (166, 155, 158, *range(298, 323)) if n in ids]
    ids = priority + [n for n in ids if n not in priority]

    def render_one(n):
        raw = args.source / str(n)
        deadline = time.monotonic() + 24 * 3600
        while not (raw / 'source-level.json').exists():
            progress = args.source / 'results.json'
            if progress.exists():
                rows = json.loads(progress.read_text())
                failure = next((r for r in rows if r['id'] == n and not r['passed']), None)
                if failure:
                    raise RuntimeError(f'Raw compile failed: {failure}')
            if time.monotonic() > deadline:
                raise TimeoutError(f'Raw compiler did not finish {n}')
            time.sleep(5)
        if shutil.disk_usage(ROOT).free < 25 * 1024**3:
            raise RuntimeError('Less than 25 GiB free; preserve delivery space')
        source_sha = hashlib.sha256((raw / 'source-level.json').read_bytes()).hexdigest()
        target = args.out / str(n)
        target.mkdir(exist_ok=True)
        receipt = target / 'result.json'
        if receipt.exists():
            old = json.loads(receipt.read_text())
            if old.get('passed') and old.get('source_sha256') == source_sha:
                print('CACHED', n, flush=True)
                return old
        chart = json.loads((raw / f'level{n}.json').read_text())
        data = json.loads((raw / 'source-level.json').read_text())
        shutil.copyfile(raw/'source-level.json',target/'source-level.json')
        assert chart.get('snapshot_map_top') == 16, (n, 'Old viewport in raw cache')
        variants = ['on', 'off'] if optional_scenery(data, chart) else ['on']
        optional_omitted=bool(chart.get('optional_scenery_omitted'))
        for variant in variants:
            work = target / variant
            work.mkdir(exist_ok=True)
            if variant=='off' and optional_omitted:
                for path in (target/'on').iterdir():
                    if path.suffix in ('.bin','.brr') or path.name in (f'level{n}.json',f'level{n}-audio.json',f'level{n}-hit-mix.json'):
                        shutil.copyfile(path,work/path.name)
                frozen=work/'source-imports';frozen.mkdir(exist_ok=True)
                shutil.copyfile(raw/'source-level.json',frozen/f'level{n}.json')
                print('REUSED IDENTICAL OPTIONAL-OFF',n,flush=True)
                continue
            failed=work/f'failed-projection{n}.pickle'
            existing=work/'source-imports'/f'level{n}.json'
            reuse=args.reuse_failed_projections and failed.exists()
            if reuse:
                assert existing.exists() and hashlib.sha256(existing.read_bytes()).hexdigest()==source_sha,(n,'Stale frozen projection')
                local=json.loads((work/f'level{n}.json').read_text())
                assert local['notes']==chart['notes'] and local['snapshot_map_top']==16
                # Legacy failure caches predate a per-variant signature.
                # A palette failure before write() can leave the earlier ON
                # cache beside metadata from a later optional-OFF attempt.
                # Re-render that ambiguous case from its frozen source.
                if local.get('optional_scenery_omitted'):reuse=False
            frozen=work/'source-imports';frozen.mkdir(exist_ok=True)
            shutil.copyfile(raw/'source-level.json',frozen/f'level{n}.json')
            if not reuse:
                for path in raw.iterdir():
                    if path.suffix in ('.bin', '.brr') or path.name in (
                            f'level{n}.json',f'level{n}-audio.json',f'level{n}-hit-mix.json'):
                        shutil.copyfile(path, work / path.name)
                local = dict(chart)
                if variant == 'off':local['decoration_vfx_off'] = True
                atomic_json(work / f'level{n}.json', local)
            command=[sys.executable,str(ROOT/'tools/projected_snapshots.py'),
                     '--source',str(work),'--out',str(work),'--levels',str(n),*(['--reuse-failed'] if reuse else [])]
            with (work/'render.log').open('w') as log:
                result=subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
            if result.returncode:
                failure=(work/'render.log').read_text()
                capacity=any(message in failure for message in (
                    'Projected frame palette capacity','Snapshot atlas capacity',
                    'Indexed snapshot atlas capacity','Decoration colors exceed source palette',
                    'Snapshot exceeds the immutable packet buffer'))
                if variant!='on' or not capacity or not optional_scenery(data,chart):
                    raise subprocess.CalledProcessError(result.returncode,command)
                # Consistently omit optional scenery on a chart that cannot
                # fit its hardware atlas. Never lower gameplay resolution,
                # remove source frames, or discard required track objects.
                shutil.copyfile(work/'render.log',work/'optional-scenery-capacity.log')
                local['decoration_vfx_off']=True
                local['optional_scenery_omitted']='hardware_palette_capacity'
                local['snapshot_aligned']=True
                atomic_json(work/f'level{n}.json',local)
                command=[arg for arg in command if arg!='--reuse-failed']
                with (work/'render.log').open('w') as log:
                    subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True)
                optional_omitted=True
            rendered = json.loads((work / f'level{n}.json').read_text())
            assert rendered['snapshot_frames'] >= chart['notes'][-1]['frame'] + 120
            assert not rendered.get('snapshot_preview')
            print('RENDERED', n, variant, rendered['snapshot_frames'], flush=True)
        row = dict(id=n, passed=True, source_sha256=source_sha, variants=variants,
                   optional_scenery_omitted=optional_omitted)
        atomic_json(receipt, row)
        return row

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        pending=list(ids);jobs={};deadline=time.monotonic()+24*3600
        while pending or jobs:
            # A worker waiting for the last import must not block ready
            # earlier songs. Submit only completed raw caches.
            ready=[n for n in pending if (args.source/str(n)/'source-level.json').exists()]
            for n in ready[:args.workers-len(jobs)]:
                pending.remove(n);jobs[pool.submit(render_one,n)]=n
            if not jobs:
                assert time.monotonic()<deadline,('Raw compiler did not finish',pending)
                time.sleep(2)
                continue
            finished,_=concurrent.futures.wait(jobs,timeout=2,return_when=concurrent.futures.FIRST_COMPLETED)
            for job in finished:
                n=jobs.pop(job)
                try:
                    results.append(job.result())
                except Exception as error:
                    row = dict(id=n, passed=False, error=repr(error))
                    results.append(row)
                    print('FAILED', row, flush=True)
                atomic_json(args.report or args.out / 'results.json', sorted(results, key=lambda r: r['id']))
    assert all(r['passed'] for r in results), [r for r in results if not r['passed']]
    print('RENDERED ALL', len(results), 'CHARTS', flush=True)


if __name__ == '__main__':
    main()
