"""Compare cartridge/WRAM note arrays against uncompressed chart source bytes."""
import argparse,ctypes as C,json
from emulate import Emulator,ROOT
from input_helpers import press

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--pack',required=True);ap.add_argument('--levels',nargs='+',type=int,required=True);args=ap.parse_args()
    base=ROOT/'build/packs'/args.pack;levels=json.loads((base/'pack.json').read_text())['levels'];rows=[]
    assert 'LARGE_CHART_BUILD = 1' in (base/'addresses.inc').read_text()
    for n in args.levels:
        chart=json.loads((base/f'level{n}.json').read_text());count=len(chart['notes']);blob=(base/f'chart{n}.bin').read_bytes()
        em=Emulator(rom=base/'adofai.sfc')
        try:
            for _ in range(120):em.run()
            for _ in range(levels.index(n)):press(em,5)
            press(em,1);press(em,3)
            for _ in range(300):
                em.run()
                if em.read('state')==1 and em.read('music_active'):break
            assert em.read('last_note')==chart['steps']
            for name,start,width,address in [('time',4,2,0x7e2000),('angle',6,1,0x7e4200),('flags',7,1,0x7e5300),('rate',8,2,0x7e6400),('progress',10,1,0x7e8600),('ccw',11,1,0x7e9700),('pause',12,2,0x40c800)]:
                memory=em.cache_ram if address>>16==0x40 else em.ram
                actual=C.string_at(memory+(address&65535),count*width)
                expected=blob[start*count:(start+width)*count]
                assert actual==expected,(n,name,next(i for i,(a,b) in enumerate(zip(actual,expected)) if a!=b))
            rows.append(dict(level=n,notes=count,checked_bytes=count*10))
            evidence=em.evidence()
        finally:em.close()
    report=dict(passed=True,**evidence,arrays=rows)
    (base/'verification/large-arrays.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))

if __name__=='__main__':main()
