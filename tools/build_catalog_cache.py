"""Build complete per-chart render caches, reporting every failure explicitly."""
import argparse
import concurrent.futures
import json
import shutil
import subprocess
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--levels', type=int, nargs='+', required=True)
    parser.add_argument('--workers', type=int, default=2)
    parser.add_argument('--resume', action='store_true')
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    logs = args.out / 'logs'
    logs.mkdir(exist_ok=True)

    def build(level):
        metadata=args.out / f'level{level}.json'
        if args.resume and metadata.exists():
            chart=json.loads(metadata.read_text())
            if (chart.get('mode1_snapshot') and chart.get('snapshot_compression') in ('lz4','lz4-split')
                    and not chart.get('snapshot_preview') and chart.get('snapshot_postroll',0)>=120
                    and all((args.out/f'{prefix}{level}.bin').exists() for prefix in
                            ('stream_data','stream_index','mode1_seeds','patterns','chart'))):
                return dict(level=level,rendered=True,cached=True)
        if shutil.disk_usage(args.out).free < 30 * 1024**3:
            return dict(level=level, error='Less than 30 GiB free; stopped before compiling')
        with (logs / f'{level}.log').open('w') as log:
            commands = [
                [sys.executable, 'tools/campaign_assets.py', '--pack', 'master', '--levels', str(level),
                 '--out', str(args.out), '--chart-cache-only', '--no-pcm', '--camera-rotation',
                 '--camera-zoom', '--camera-position', '--motion-step', '1', '--full-snapshot-source'],
                [sys.executable, 'tools/projected_snapshots.py', '--source', str(args.out),
                 '--out', str(args.out), '--levels', str(level)],
            ]
            for command in commands:
                result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT)
                if result.returncode:
                    return dict(level=level, error=f'{Path(command[1]).name} exited {result.returncode}')
        return dict(level=level, rendered=True)

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(build, level): level for level in args.levels}
        for future in concurrent.futures.as_completed(futures):
            try:
                result = future.result()
            except Exception as exc:
                result = dict(level=futures[future], error=repr(exc))
            results.append(result)
            print(json.dumps(result), flush=True)
            (args.out / 'render-report.json').write_text(json.dumps(sorted(results, key=lambda r: r['level']), indent=2))
    if any('error' in r for r in results):
        raise SystemExit('One or more charts failed; this cache is NOT release-ready')


if __name__ == '__main__':
    main()
