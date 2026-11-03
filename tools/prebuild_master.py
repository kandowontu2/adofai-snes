"""Compile independent master charts in bounded separate processes."""
import argparse,concurrent.futures,json,subprocess,sys
from pathlib import Path
from official_catalog import WORLDS
from import_tech import TECH
ROOT=Path(__file__).resolve().parents[1]

def compile_one(n,out):
    log=ROOT/f'build/master-cache-{n}.log'
    with log.open('w') as f:
        result=subprocess.run([sys.executable,str(ROOT/'tools/campaign_assets.py'),'--pack','master','--out',str(out),'--levels',str(n),'--chart-cache-only'],stdout=f,stderr=subprocess.STDOUT)
    assert result.returncode==0,(n,log.read_text()[-2000:])
    return n

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--levels',type=int,nargs='+');ap.add_argument('--workers',type=int,default=8);ap.add_argument('--out',type=Path,default=ROOT/'build/packs/master');args=ap.parse_args()
    failed=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        jobs={pool.submit(compile_one,n,args.out):n for n in (args.levels or [m['id'] for m in WORLDS+TECH])}
        for job in concurrent.futures.as_completed(jobs):
            try:print('Cached',job.result(),flush=True)
            except Exception as e:failed.append(jobs[job]);print('FAILED',jobs[job],str(e),flush=True)
    assert not failed,('Chart builds failed',failed)

if __name__=='__main__':main()
