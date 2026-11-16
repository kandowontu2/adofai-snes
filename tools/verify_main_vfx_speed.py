"""Verify animated main worlds fall back to equal-cost scenery at 4x."""
import argparse,concurrent.futures,json,re,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from verification_data import identity
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--pack',required=True);a=p.parse_args()
base=ROOT/'build/packs'/a.pack;frozen=identity(base/'adofai.sfc')
(base/'verification/main-vfx').mkdir(parents=True,exist_ok=True)
def run(n,off,watch):
    suffix='-speed-40'+('-autoplay' if watch else '')+('-vfx-off' if off else '')+'-paired-vfx'
    log=base/f'verification/main-vfx/speed-{n}{suffix}.log'
    args=['--pack',base.name,'--levels',str(n),'--speed','4','--paired-vfx','--sampled-graphics','--resume']
    if off:args+=['--vfx-off']
    if watch:args+=['--autoplay']
    with log.open('w') as out:
        subprocess.run([sys.executable,'tools/run_mesen_campaign.py',*args],cwd=ROOT,stdout=out,stderr=subprocess.STDOUT,check=True)
        folder=base/f'verification/mesen-{n}{suffix}'
        subprocess.run([sys.executable,'tools/verify_mesen_ppu.py','--pack',base.name,'--level',str(n),'--folder',str(folder)],cwd=ROOT,stdout=out,stderr=subprocess.STDOUT,check=True)
    assert not (folder/'main-vfx-budget.txt').exists(),'Scenery animation ran above 1x'
    screen=(folder/'screen-registers.txt').read_text()
    return dict(level=n,vfx=not off,watch=watch,**{k:int(re.search(k+r'=(\d+)',screen)[1]) for k in ('max_frame_gap','missed_presentations','settled_missed')})
rows=[]
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as p:
    for f in concurrent.futures.as_completed([p.submit(run,n,o,w) for n in (2,8) for o in (False,True) for w in (False,True)]):
        row=f.result();rows.append(row);print(row,flush=True)
bad=[]
for n in (2,8):
    for w in (False,True):
        pair={r['vfx']:r for r in rows if r['level']==n and r['watch']==w}
        if any(pair[True][k]>pair[False][k] for k in ('max_frame_gap','missed_presentations','settled_missed')):bad.append([n,w])
assert identity(base/'adofai.sfc')==frozen
(base/'verification/main-vfx-speed.json').write_text(json.dumps(dict(passed=not bad,speed=4,cases=rows,regressions=bad,**frozen),indent=2))
assert not bad,bad
