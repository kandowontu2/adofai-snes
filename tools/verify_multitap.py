"""Exercise authored RJ-X double taps with real SNES controller edges."""
import argparse,ctypes as C,json
from pathlib import Path
from emulate import Emulator
from input_helpers import select_level,press,wait

def verify(rom):
    out=rom.parent/'verification';out.mkdir(exist_ok=True)
    chart=json.loads((rom.parent/'level19.json').read_text())
    doubles=[n['step'] for n in chart['notes'] if n.get('taps_needed',1)==2]
    assert len(doubles)==76 and doubles[0]==15
    results=[]
    for mode in ('single','held','simultaneous','sequential','same_button'):
        em=Emulator(rom=rom)
        try:
            for _ in range(120):em.run()
            select_level(em,19);press(em,1);press(em,3)
            wait(em,lambda:em.read('step')==14,1800)
            C.c_uint16.from_address(em.ram+em.labels['autoplay']).value=0
            target=chart['notes'][15]['frame']+em.read('speed_offset',True)
            for _ in range(100):
                delta=((em.read('nmi_audio_ticks')-em.read('audio_ticks')+32768)&65535)-32768
                if em.read('elapsed')+delta*.004*em.av.timing.fps+1>=target:break
                em.run()
            em.capture(out/f'multitap-{mode}-before.png')
            em.run([8,0] if mode=='simultaneous' else [8])
            if mode!='simultaneous':
                wait(em,lambda:em.read('note_taps')==1,5)
                assert em.read('step')==14 and em.read('combo')==14,em.snapshot()
            if mode=='sequential':em.run([0])
            if mode=='same_button':em.run();em.run([8])
            if mode in ('single','held'):
                for _ in range(30):em.run([8] if mode=='held' else [])
                assert em.read('state')==2 and em.read('step')==14 and em.read('misses')==1,em.snapshot()
                press(em,3)
                assert em.read('note_taps')==0,'Retry retained partial tap count'
            else:
                wait(em,lambda:em.read('step')==15,10)
                assert em.read('note_taps')==0 and em.read('combo')==15 and em.read('overload')==0,em.snapshot()
                em.capture(out/f'multitap-{mode}-after.png')
            results.append(dict(mode=mode,passed=True))
            evidence=em.evidence()
        finally:em.close()
    report=dict(passed=True,double_notes=len(doubles),cases=results,**evidence)
    (out/'multitap.json').write_text(json.dumps(report,indent=2));print(report)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--rom',type=Path,required=True)
    verify(ap.parse_args().rom.resolve())
