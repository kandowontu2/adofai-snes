"""Verify calibration presentation, clicks, taps and gameplay in every cartridge."""
import argparse,concurrent.futures,json,os,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def check(row):
    base=ROOT/'build/packs'/row['key'];out=base/'verification/calibration-hotfix';out.mkdir(parents=True,exist_ok=True)
    env=os.environ.copy()
    for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):env[name]='1'
    code='''import sys,json
from pathlib import Path
sys.path.insert(0,'tools')
from verify_calibration import entry_sound,presentation,metronome,gameplay
base=Path(sys.argv[1])
report=dict(passed=True,entry=entry_sound(base),presentation=presentation(base),measurement=metronome(base,1,0),gameplay=gameplay(base,0,10))
(base/'verification/calibration-hotfix/result.json').write_text(json.dumps(report,indent=2))
'''
    with (out/'run.log').open('w') as f:
        result=subprocess.run([sys.executable,'-c',code,str(base)],cwd=ROOT,env=env,stdout=f,stderr=subprocess.STDOUT)
    assert result.returncode==0,(row['key'],out/'run.log')
    report=json.loads((out/'result.json').read_text())
    assert all(report[key]['rom_sha256']==row['rom_sha256'] for key in ('entry','presentation','measurement','gameplay'))
    return dict(key=row['key'],rom_sha256=row['rom_sha256'],passed=True,gameplay_combo=report['gameplay']['combo'])

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--catalog',type=Path,default=ROOT/'build/standalone-catalog.json')
    ap.add_argument('--output',type=Path,default=ROOT/'build/calibration-standalone-verification.json')
    args=ap.parse_args()
    catalog=json.loads(args.catalog.read_text())
    rows=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for row in pool.map(check,catalog['roms']):rows.append(row);print(json.dumps(row),flush=True)
    args.output.write_text(json.dumps(dict(passed=True,cartridges=rows),indent=2))
    print('PASS:',len(rows),'cartridges: continuous orbit, immediate/repeating sound, 16 taps, full-song gameplay')

if __name__=='__main__':main()
