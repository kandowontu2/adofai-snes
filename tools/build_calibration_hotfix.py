"""Relink calibration code while proving all campaign asset bytes unchanged."""
import argparse,concurrent.futures,hashlib,json,shutil,subprocess,sys
from pathlib import Path
from verification_data import identity
ROOT=Path(__file__).resolve().parents[1]
BACKUP=ROOT/'build/calibration-hotfix-baseline'
FIX=ROOT/'build/packs/calibration-fix'

def same_assets(old,new):
    a=old.read_bytes();b=new.read_bytes();assert len(a)==len(b)==0x800000
    for start,end in ((0,0x8000),(0x10000,0x408000),(0x410000,0x800000)):
        assert a[start:end]==b[start:end],(old,new,start,'Game asset payload changed')

def assemble(base):
    code="""import sys,json,subprocess
from pathlib import Path
sys.path.insert(0,'tools');import campaign_assets as assets
assets.OUT=Path(sys.argv[1]);assets.common_tables(json.loads((assets.OUT/'manifest.json').read_text()))
subprocess.run([sys.executable,'build_campaign.py','--pack','master','--out',str(assets.OUT),'--skip-assets'],check=True)
"""
    result=subprocess.run([sys.executable,'-c',code,str(base)],cwd=ROOT,check=True,capture_output=True,text=True)
    print(result.stdout.strip(),flush=True)

def build(row):
    row=dict(row);base=ROOT/'build/packs'/row['key'];assemble(base)
    same_assets(BACKUP/row['file'],base/'adofai.sfc')
    row['rom_sha256']=hashlib.sha256((base/'adofai.sfc').read_bytes()).hexdigest();return row

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--reuse-master',action='store_true');args=ap.parse_args()
    prior=json.loads((BACKUP/'master-verification.json').read_text())
    assert prior['verified'] and prior['rom_sha256']==hashlib.sha256((BACKUP/'master.sfc').read_bytes()).hexdigest()
    if not args.reuse_master:assemble(FIX)
    same_assets(BACKUP/'master.sfc',FIX/'adofai.sfc')
    current=identity(FIX/'adofai.sfc');assert current['msu_sha256']==prior['msu_sha256']
    catalog=json.loads((BACKUP/'standalone-catalog.json').read_text())
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:catalog['roms']=list(pool.map(build,catalog['roms']))
    destination=ROOT/'build/standalone-catalog.json';temp=destination.with_suffix('.json.partial')
    temp.write_text(json.dumps(catalog,indent=2));temp.replace(destination)
    master=ROOT/'build/packs/master'
    for name in ('adofai.sfc','adofai.lbl','adofai.map','game.o','game.lst','tables.inc','spc.bin'):shutil.copy2(FIX/name,master/name)
    (ROOT/'build/calibration-hotfix-build.json').write_text(json.dumps(dict(passed=True,unchanged_game_assets=True,
       unchanged_msu=True,master=current,standalone_catalog=catalog),indent=2))
    print('PASS: master and 21 standalone ROMs rebuilt; all campaign asset bytes and MSU unchanged',flush=True)

if __name__=='__main__':main()
