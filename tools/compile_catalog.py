"""Compile a re-imported catalog with every authored motion frame retained."""
import argparse
import concurrent.futures
import hashlib
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--catalog',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--workers',type=int,default=4)
    p.add_argument('--resume',action='store_true',help='Reuse complete raw caches with the same imported source')
    p.add_argument('--report',type=Path,help='Write this batch separately when repairing part of a catalog')
    args=p.parse_args();args.out.mkdir(parents=True,exist_ok=True)
    ids=json.loads(args.catalog.read_text())['levels']
    priority=[n for n in (166,155,158,298,299,300,309,312) if n in ids]
    ids=priority+[n for n in ids if n not in priority]
    def compile_one(n):
        if shutil.disk_usage(ROOT).free<25*1024**3:raise RuntimeError('Less than 25 GiB free; preserve space for delivery')
        folder=args.out/str(n);folder.mkdir(exist_ok=True)
        source=ROOT/f'assets/private/level{n}.json'
        source_sha=hashlib.sha256(source.read_bytes()).hexdigest()
        frozen=folder/'source-level.json'
        if args.resume and frozen.exists() and hashlib.sha256(frozen.read_bytes()).hexdigest()==source_sha:
            chart=json.loads((folder/f'level{n}.json').read_text())
            required=[folder/f'{prefix}{n}.bin' for prefix in ('animation','chart','patterns','timeline','track_chr','track_map','checkpoints','visibility_index')]
            if chart.get('snapshot_map_top')==16 and chart.get('motion_step')==1 and all(p.exists() for p in required) and (folder/f'level{n}.brr').exists():
                print('CACHED',n,flush=True)
                return dict(id=n,passed=True,source_sha256=source_sha,cached=True)
        with (folder/'compile.log').open('w') as log:
            result=subprocess.run([sys.executable,str(ROOT/'tools/campaign_assets.py'),'--pack','master',
                '--out',str(folder),'--levels',str(n),'--full-snapshot-source','--camera-position',
                '--camera-rotation','--camera-zoom','--motion-step','1','--no-pcm','--chart-cache-only'],
                cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
        row=dict(id=n,passed=result.returncode==0,source_sha256=source_sha)
        if row['passed']:
            assert hashlib.sha256(source.read_bytes()).hexdigest()==source_sha,'Source changed during compile'
            (folder/'source-level.json').write_bytes(source.read_bytes())
        print(('COMPILED' if row['passed'] else 'FAILED'),n,flush=True)
        return row
    results=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        jobs={pool.submit(compile_one,n):n for n in ids}
        for job in concurrent.futures.as_completed(jobs):
            try:results.append(job.result())
            except Exception as e:results.append(dict(id=jobs[job],passed=False,error=repr(e)))
            target=args.report or args.out/'results.json';temp=target.with_suffix('.json.new')
            temp.write_text(json.dumps(sorted(results,key=lambda r:r['id']),indent=2))
            for attempt in range(100):
                try:temp.replace(target);break
                except PermissionError:
                    if attempt==99:raise
                    time.sleep(.05)
    assert all(r['passed'] for r in results),[r for r in results if not r['passed']]
    print('COMPILED ALL',len(results),'CHARTS',flush=True)


if __name__=='__main__':main()
