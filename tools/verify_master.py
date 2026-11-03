"""Run independent per-world master ROM checks with bounded concurrency."""
import argparse,concurrent.futures,hashlib,json,os,subprocess,sys,time
from pathlib import Path
from verification_data import data_sha256
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'build/packs/master'

def main():
    global BASE
    ap=argparse.ArgumentParser()
    ap.add_argument('--pack',default='master')
    ap.add_argument('--checks',nargs='+',choices=['controller','audio','render','mesen','checkpoints','mesen-checkpoints'],default=['controller','audio','render'])
    ap.add_argument('--levels',nargs='+',type=int)
    ap.add_argument('--workers',type=int,default=6)
    ap.add_argument('--resume',action='store_true')
    args=ap.parse_args();BASE=ROOT/'build/packs'/args.pack
    digest=hashlib.sha256((BASE/'adofai.sfc').read_bytes()).hexdigest();data_digest=data_sha256(BASE)
    env=os.environ.copy()
    for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):env[name]='1'
    pack_levels=json.loads((BASE/'pack.json').read_text())['levels']
    levels=args.levels or pack_levels
    def verify(level):
        v=BASE/'verification';v.mkdir(exist_ok=True)
        chart=json.loads((BASE/f'level{level}.json').read_text())
        local=pack_levels.index(level)+1
        commands={
            'controller':['emulate_campaign.py','--pack',args.pack,'--level',str(local),'--mode','perfect','--audio','--music-only'],
            'audio':['check_campaign_audio.py',str(v/f'perfect-{local}')],
            'render':['verify_render.py','--pack',args.pack,'--level',str(local)],
            'mesen':['run_mesen_campaign.py','--pack',args.pack,'--levels',str(local),'--resume'],
            'checkpoints':['verify_checkpoints.py','--packs',args.pack,'--levels',str(local)],
            'mesen-checkpoints':['run_mesen_campaign.py','--pack',args.pack,'--levels',str(local),'--checkpoints','--resume']}
        for check in args.checks:
            if 'checkpoints' in check and not chart['checkpoints']:continue
            stamp=v/f'master-{check}-{level}.json'
            if args.resume and stamp.exists():
                previous=json.loads(stamp.read_text())
                if previous.get('rom_sha256')==digest and previous.get('msu_sha256')==data_digest:continue
            log=v/f'master-{check}-{level}.log'
            with log.open('w') as f:
                result=subprocess.run([sys.executable,str(ROOT/'tools'/commands[check][0]),*commands[check][1:]],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,env=env)
            if result.returncode:return dict(level=level,code=chart['code'],failed=check,log=str(log))
            assert hashlib.sha256((BASE/'adofai.sfc').read_bytes()).hexdigest()==digest,'ROM changed during verification'
            assert data_sha256(BASE)==data_digest,'MSU data changed during verification'
            stamp.write_text(json.dumps(dict(rom_sha256=digest,msu_sha256=data_digest,check=check,level=level,passed=True),indent=2))
        return dict(level=level,code=chart['code'],checks=args.checks,passed=True)
    started=time.time();results=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures={pool.submit(verify,n):n for n in levels}
        for future in concurrent.futures.as_completed(futures):
            try:row=future.result()
            except Exception as e:row=dict(level=futures[future],error=repr(e))
            results.append(row);print(json.dumps(row),flush=True)
    report=dict(rom_sha256=digest,msu_sha256=data_digest,checks=args.checks,seconds=round(time.time()-started,2),results=sorted(results,key=lambda r:r['level']))
    destination=ROOT/(f'build/{args.pack}-verification-'+ '-'.join(args.checks)+'.json')
    destination.write_text(json.dumps(report,indent=2))
    assert all(r.get('passed') for r in results),f'Checks failed: see {destination}'
    print(f'PASS: {len(results)} worlds, {args.checks}',flush=True)

if __name__=='__main__':main()
