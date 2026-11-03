"""Use real early/late controller taps to verify accepted-hit lighting gates."""
import argparse,ctypes as C,json
from pathlib import Path
from emulate import Emulator,ROOT
from input_helpers import press,wait

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--pack',default='master');args=ap.parse_args()
    base=ROOT/'build/packs'/args.pack
    first=json.loads((base/'pack.json').read_text())['levels'][0]
    chart=json.loads((base/f'level{first}.json').read_text());target=chart['notes'][1]['frame'];rows=[]
    for bias in (-2,2,None):
        em=Emulator(rom=base/'adofai.sfc')
        try:
            for _ in range(120):em.run()
            press(em,3)
            wait(em,lambda:em.read('state')==1 and em.read('chart_time')>=target+(bias or 2),600)
            assert em.read('step')==0,em.snapshot()
            if bias is None or bias>0:
                assert em.read('display_chart_time')<target,'Unhit floor lit on the music clock'
            if bias is not None:
                press(em,8)
                wait(em,lambda:em.read('step')>=1 and em.read('display_chart_time')>=target,20)
                assert em.read('state')==1 and em.read('combo')==1,em.snapshot()
                now=em.read('display_chart_time');palette=[0]*96
                for f,i,v in chart['track_palette_versions']:
                    if f<=now:palette[i]=v
                actual=list((C.c_uint16*96).from_address(em.ram+0x1fa20))
                assert actual==palette,'Accepted-hit material was not published'
            else:
                wait(em,lambda:em.read('state')==2,30)
                assert em.read('display_chart_time')<target,'Miss lit an unhit floor'
            rows.append(dict(bias=bias,step=em.read('step'),display_time=em.read('display_chart_time')))
            evidence=em.evidence()
        finally:em.close()
    report=dict(passed=True,**evidence,cases=rows)
    (base/'verification/hit-lighting.json').write_text(json.dumps(report,indent=2));print(report)

if __name__=='__main__':main()
