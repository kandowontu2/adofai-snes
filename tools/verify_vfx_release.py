"""Measure both scenery modes and keep Neo Cosmos gameplay effects covered."""
import argparse,json,re,subprocess,sys
from pathlib import Path
from verification_data import identity
ROOT=Path(__file__).resolve().parents[1]

def verify(name):
    pack=ROOT/'build/packs'/name;frozen=identity(pack/'adofai.sfc')
    levels=json.loads((pack/'pack.json').read_text())['levels'];cases=[]
    def run(tool,*args):
        subprocess.run([sys.executable,str(ROOT/'tools'/tool),*map(str,args)],cwd=ROOT,check=True)
    run('verify_vfx_options_mesen.py','--pack',pack)
    for level,off,watch in [(252,False,True),(252,False,False),(252,True,True),(252,True,False),
                            (68,True,True),(73,True,True)]:
        local=levels.index(level)+1
        args=['--pack',name,'--levels',local,'--sampled-graphics','--resume']
        if off:args.append('--vfx-off')
        if watch:args.append('--autoplay')
        run('run_mesen_campaign.py',*args)
        suffix=('-autoplay' if watch else '')+('-vfx-off' if off else '')
        folder=pack/f'verification/mesen-{local}{suffix}'
        run('verify_mesen_ppu.py','--pack',name,'--level',local,'--folder',folder)
        result=json.loads((folder/'manifest.json').read_text())
        assert result['passed'] and all(result[k]==v for k,v in frozen.items())
        screen=(folder/'screen-registers.txt').read_text()
        cases.append(dict(id=level,vfx=not off,watch=watch,passed=True,
                          samples=int(re.search(r'samples=(\d+)',screen)[1]),
                          max_frame_gap=int(re.search(r'max_frame_gap=(\d+)',screen)[1])))
    assert identity(pack/'adofai.sfc')==frozen
    report=dict(passed=True,**frozen,cases=cases,
                note='Measured presentation gaps; passing is not a locked-60-fps claim.')
    (pack/'verification/chaos-performance.json').write_text(json.dumps(report,indent=2))
    (pack/'verification/vfx-verification.json').write_text(json.dumps(report,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--pack',required=True)
    verify(p.parse_args().pack)
