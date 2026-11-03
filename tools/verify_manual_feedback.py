"""Measure real pad-edge to SPC-command latency through a complete song."""
import argparse,json,ctypes as C
from pathlib import Path
from emulate import Emulator,ROOT
from input_helpers import press,configure

def check(base,level,speed):
    em=Emulator(rom=base/'adofai.sfc');lags=[];pending=[];last_tick=None
    try:
        for _ in range(120):em.run()
        configure(em,round(speed*10))
        for _ in range(level-1):press(em,5)
        press(em,9);press(em,3)
        command=lambda:C.c_uint16.from_address(em.ram+0x1fc36).value
        for frame in range(30000):
            tap=em.read('state')==1 and em.read('music_active') and frame%19==0
            if tap:pending.append(frame)
            before=command();em.run([8] if tap else [])
            for _ in range((command()-before)&65535):
                assert pending,'Duplicate/unrequested percussion command'
                lags.append(frame-pending.pop(0))
            if em.read('state')==3:break
        assert em.read('state')==3 and not pending and lags
        assert em.read('tap_overruns')==0
        assert max(lags)<=1,('Tap sound delayed by rendering',max(lags))
        return dict(passed=True,level=level,speed=speed,taps=len(lags),max_delay_frames=max(lags),
                    delayed_taps=sum(x>0 for x in lags),final=em.snapshot(),**em.evidence())
    finally:em.close()

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--pack',required=True);ap.add_argument('--level',type=int,required=True);ap.add_argument('--speed',type=float,default=1);args=ap.parse_args()
    base=ROOT/'build/packs'/args.pack;row=check(base,args.level,args.speed)
    out=base/'verification';out.mkdir(exist_ok=True)
    (out/f'manual-feedback-{args.level}-{round(args.speed*10)}.json').write_text(json.dumps(row,indent=2))
    print(json.dumps(row))
if __name__=='__main__':main()
