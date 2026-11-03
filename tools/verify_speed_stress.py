"""Reproduce the dense-track, long-clock, and independent speed checks."""
import argparse,hashlib,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def run(*args):
    subprocess.run([sys.executable,str(ROOT/'tools'/args[0]),*args[1:]],cwd=ROOT,check=True)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--resume',action='store_true');args=ap.parse_args()
    for pack,level,speed,name in [('main',9,'2.0','fast-track-verification'),('jokes',3,'0.5','long-clock-verification')]:
        folder=ROOT/'build'/name;path=folder/'result.json'
        base=ROOT/'build/campaign' if pack=='main' else ROOT/f'build/packs/{pack}'
        current=False
        if args.resume and path.exists():
            result=json.loads(path.read_text())
            current=result['rom_sha256']==hashlib.sha256((base/'adofai.sfc').read_bytes()).hexdigest() and result['final']['state']==3 and result['final']['misses']==0
        if not current:
            run('emulate_campaign.py','--pack',pack,'--level',str(level),'--mode','perfect','--speed',speed,'--time-attack','--audio','--music-only','--out',str(folder))
        run('check_campaign_audio.py',str(folder))
    for pack,levels,speed in [('main',['1'],'0.5'),('main',['1'],'1.1'),('main',['1','9'],'2.0'),('jokes',['3'],'0.5')]:
        run('run_mesen_campaign.py','--pack',pack,'--levels',*levels,'--speed',speed,'--time-attack',*(['--resume'] if args.resume else []))
    print('Dense-track, timer-rollover, and independent speed checks passed.')

if __name__=='__main__':main()
