"""Compile authored visibility and opaque track layers in isolated jobs."""
import argparse,concurrent.futures,json,os,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--levels',type=int,nargs='+');ap.add_argument('--workers',type=int,default=4)
    args=ap.parse_args();env=os.environ.copy()
    for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):env[key]='1'
    def compile_one(n):
        log=ROOT/f'build/authored-{n}-compile.log'
        with log.open('w') as f:
            result=subprocess.run([sys.executable,'tools/campaign_assets.py','--pack','master','--out',str(args.out),
                                   '--levels',str(n),'--chart-cache-only'],cwd=ROOT,env=env,stdout=f,stderr=subprocess.STDOUT)
        row=dict(level=n,passed=result.returncode==0,log=str(log));print(json.dumps(row),flush=True);return row
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        rows=list(pool.map(compile_one,args.levels or range(1,62)))
    (args.out/'authored-compile.json').write_text(json.dumps(dict(passed=all(r['passed'] for r in rows),results=rows),indent=2))
    assert all(r['passed'] for r in rows),[r for r in rows if not r['passed']]

if __name__=='__main__':main()
