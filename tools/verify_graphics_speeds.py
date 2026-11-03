"""Check every displayed frame, including held frames with background DMA."""
import argparse,concurrent.futures,json,os,subprocess,sys
from pathlib import Path
from verification_data import identity
ROOT=Path(__file__).resolve().parents[1]

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--pack',default='master');ap.add_argument('--standalone',action='store_true')
    ap.add_argument('--speeds',type=float,nargs='+',default=[1.,1.3,2.]);ap.add_argument('--workers',type=int,default=4)
    ap.add_argument('--catalog',type=Path,default=ROOT/'build/standalone-catalog.json');ap.add_argument('--levels',type=int,nargs='+');ap.add_argument('--resume',action='store_true');ap.add_argument('--out',type=Path);args=ap.parse_args()
    packs=[r['key'] for r in json.loads(args.catalog.read_text())['roms']] if args.standalone else [args.pack]
    jobs=[];env=os.environ.copy()
    for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):env[key]='1'
    for pack in packs:
        base=ROOT/'build/packs'/pack
        for local,n in enumerate(json.loads((base/'pack.json').read_text())['levels'],1):
            if args.levels and n not in args.levels:continue
            for speed in args.speeds:jobs.append((pack,local,n,speed))
    def check(job):
        pack,local,n,speed=job;base=ROOT/'build/packs'/pack;v=base/'verification';v.mkdir(exist_ok=True)
        current=identity(base/'adofai.sfc');suffix='' if speed==1 else f'-speed-{round(speed*10)}'
        report=v/f'render-{n}{suffix}.json'
        if args.resume and report.exists():
            old=json.loads(report.read_text())
            if all(old.get(k)==value for k,value in current.items()) and old.get('every_frame') and old.get('completed_song'):
                return dict(pack=pack,level=n,speed=speed,passed=True,**current)
        log=v/f'graphics-{n}-{round(speed*10)}.log'
        with log.open('w') as output:
            r=subprocess.run([sys.executable,'tools/verify_render.py','--pack',pack,'--level',str(local),'--speed',str(speed),'--every-frame'],cwd=ROOT,env=env,stdout=output,stderr=subprocess.STDOUT)
        assert identity(base/'adofai.sfc')==current
        row=dict(pack=pack,level=n,speed=speed,passed=r.returncode==0,log=str(log),**current)
        print(json.dumps(row),flush=True);return row
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:rows=list(pool.map(check,jobs))
    name=('sa1-standalone' if args.catalog.stem.startswith('sa1-') else 'standalone') if args.standalone else args.pack
    path=args.out or ROOT/f'build/graphics-speeds-{name}.json'
    path.write_text(json.dumps(dict(passed=all(r['passed'] for r in rows),every_frame=True,speeds=args.speeds,results=rows),indent=2))
    assert all(r['passed'] for r in rows),str(path)
    print(f'PASS: {len(rows)} complete-song, every-frame PPU checks',flush=True)

if __name__=='__main__':main()
