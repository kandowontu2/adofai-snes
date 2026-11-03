"""Full controller/audio, autoplay, and raster checks for official ROM packs."""
import argparse,hashlib,json,subprocess,sys
from pathlib import Path
from official_catalog import PACKS
ROOT=Path(__file__).resolve().parents[1]

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--packs',nargs='+',choices=PACKS,default=list(PACKS))
    ap.add_argument('--checks',nargs='+',choices=['controller','audio','watch','render'],default=['controller','audio','watch','render'])
    ap.add_argument('--resume',action='store_true')
    args=ap.parse_args();results=[]
    for pack in args.packs:
        base=ROOT/'build/campaign' if pack=='main' else ROOT/f'build/packs/{pack}'
        digest=hashlib.sha256((base/'adofai.sfc').read_bytes()).hexdigest()
        for local,n in enumerate(PACKS[pack]['levels'],1):
            chart=json.loads((base/f'level{n}.json').read_text());logs=base/'verification';logs.mkdir(exist_ok=True)
            commands=[]
            if 'controller' in args.checks:commands.append(('controller',['emulate_campaign.py','--pack',pack,'--level',str(local),'--mode','perfect','--audio','--music-only']))
            if 'audio' in args.checks:commands.append(('audio',['check_campaign_audio.py',str(logs/f'perfect-{local}')]))
            if 'watch' in args.checks:commands.append(('watch',['emulate_campaign.py','--pack',pack,'--level',str(local),'--mode','watch']))
            if 'render' in args.checks:commands.append(('render',['verify_render.py','--pack',pack,'--level',str(local)]))
            for label,command in commands:
                report_path=(logs/f'perfect-{local}/result.json' if label=='controller' else logs/f'watch-{local}/result.json' if label=='watch' else logs/f'perfect-{local}/audio-check.json' if label=='audio' else logs/f'render-{local}.json')
                if args.resume and report_path.exists():
                    prior=json.loads(report_path.read_text())
                    good=prior.get('rom_sha256')==digest
                    if label in ('controller','watch'):
                        end=prior['final'];good&=end['state']==3 and end['step']==chart['steps'] and end['combo']==chart['hits'] and end['misses']==0
                    if label=='audio':good&=min(x['correlation'] for x in prior['windows'])>.90 and abs(prior['drift_ms'])<20 and prior.get('comparison_window_seconds')==2
                    if good:continue
                with (logs/f'{label}-{local}.log').open('w') as f:
                    result=subprocess.run([sys.executable,str(ROOT/'tools'/command[0]),*command[1:]],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT)
                if result.returncode:
                    print((logs/f'{label}-{local}.log').read_text()[-3500:],flush=True)
                    raise RuntimeError(f'{chart["code"]} {label} failed')
            row=dict(code=chart['code'],pack=pack,steps=chart['steps'],hits=chart['hits'],checks=args.checks,
                     rom_sha256=hashlib.sha256((base/'adofai.sfc').read_bytes()).hexdigest())
            results.append(row);print(chart['code']+' PASS: '+', '.join(args.checks),flush=True)
    destination=ROOT/'build/official-verification.json';destination.write_text(json.dumps(results,indent=2))
    print('Verified',len(results),'worlds',flush=True)

if __name__=='__main__':main()
