"""Replay every embedded-audio cartridge without any MSU/PCM dependency."""
import argparse,concurrent.futures,json,os,subprocess,sys,time
from pathlib import Path
from verification_data import identity
ROOT=Path(__file__).resolve().parents[1]


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--checks',nargs='+',choices=['controller','audio','render','mesen','checkpoints','mesen-checkpoints','menu'],default=['controller','audio','render'])
    ap.add_argument('--workers',type=int,default=6);ap.add_argument('--resume',action='store_true')
    ap.add_argument('--catalog',type=Path,default=ROOT/'build/standalone-catalog.json');args=ap.parse_args()
    catalog=json.loads(args.catalog.read_text())
    env=os.environ.copy()
    for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):env[key]='1'
    jobs=[(r,local,n) for r in catalog['roms'] for local,n in enumerate(r['levels'],1)]
    def verify(job):
        rom,local,n=job;pack=rom['key'];base=ROOT/'build/packs'/pack;v=base/'verification';v.mkdir(exist_ok=True)
        current=identity(base/'adofai.sfc');assert current['msu_sha256'] is None
        assert not list(base.glob('*.pcm')) and not list(base.glob('*.msu'))
        chart=json.loads((base/f'level{n}.json').read_text())
        commands={
            'controller':['emulate_campaign.py','--pack',pack,'--level',str(local),'--mode','perfect','--audio','--music-only'],
            'audio':['check_campaign_audio.py',str(v/f'perfect-{local}')],
            'render':['verify_render.py','--pack',pack,'--level',str(local)],
            'mesen':['run_mesen_campaign.py','--pack',pack,'--levels',str(local),'--resume'],
            'checkpoints':['verify_checkpoints.py','--packs',pack,'--levels',str(local)],
            'mesen-checkpoints':['run_mesen_campaign.py','--pack',pack,'--levels',str(local),'--checkpoints','--resume'],
            'menu':['verify_menu_pages.py','--pack',pack]}
        for check in args.checks:
            if 'checkpoints' in check and not chart['checkpoints']:continue
            if check=='menu' and local!=1:continue
            stamp=v/f'standalone-{check}-{local}.json'
            if args.resume and stamp.exists():
                prior=json.loads(stamp.read_text())
                if prior.get('rom_sha256')==current['rom_sha256'] and prior.get('passed'):continue
            log=v/f'standalone-{check}-{local}.log'
            with log.open('w') as output:
                result=subprocess.run([sys.executable,str(ROOT/'tools'/commands[check][0]),*commands[check][1:]],cwd=ROOT,env=env,stdout=output,stderr=subprocess.STDOUT)
            if result.returncode:return dict(pack=pack,local=local,id=n,failed=check,log=str(log))
            assert identity(base/'adofai.sfc')==current
            stamp.write_text(json.dumps(dict(**current,check=check,level=n,passed=True),indent=2))
        return dict(pack=pack,local=local,id=n,checks=args.checks,passed=True)
    started=time.time();rows=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures={pool.submit(verify,j):j for j in jobs}
        for future in concurrent.futures.as_completed(futures):
            try:row=future.result()
            except Exception as exc:row=dict(pack=futures[future][0]['key'],id=futures[future][2],error=repr(exc))
            rows.append(row);print(json.dumps(row),flush=True)
    report=dict(checks=args.checks,seconds=round(time.time()-started,2),results=sorted(rows,key=lambda r:r['id']))
    target=ROOT/('build/standalone-verification-'+'-'.join(args.checks)+'.json');target.write_text(json.dumps(report,indent=2))
    assert all(r.get('passed') for r in rows),str(target)
    print('PASS:',len(rows),'songs',args.checks,flush=True)


if __name__=='__main__':main()
