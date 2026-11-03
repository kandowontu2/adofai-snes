"""A real missed tap must preserve a complete, previously displayed scene."""
import argparse,ctypes as C,json
from collections import deque
from emulate import Emulator,ROOT
from input_helpers import configure,press

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--level',type=int,default=11)
    ap.add_argument('--speed',type=float,default=1.0);ap.add_argument('--stop-step',type=int,default=152)
    args=ap.parse_args();base=ROOT/'build/packs/master'
    out=base/f'verification/death-presentation-{args.level}-{round(args.speed*10)}';out.mkdir(parents=True,exist_ok=True)
    chart=json.loads((base/f'level{args.level}.json').read_text());notes=[n for n in chart['notes'][1:] if not(n['flags']&8) and n['step']<=args.stop_step]
    em=Emulator(rom=base/'adofai.sfc');next_input=0;recent=deque(maxlen=3);prior=None
    def scene():
        blob,w,h,pitch=em.video
        return C.string_at(em.core.retro_get_memory_data(3),32768),blob[32*pitch:160*pitch]
    try:
        for _ in range(120):em.run()
        if args.speed!=1:configure(em,round(args.speed*10),False)
        for _ in range(args.level-1):press(em,5)
        press(em,3)
        for frame in range(18000):
            buttons=[]
            if em.read('state')==1:
                delta=((em.read('nmi_audio_ticks')-em.read('audio_ticks')+32768)&65535)-32768
                current=em.read('elapsed')+delta*.004*em.av.timing.fps*em.read('speed_pitch')/1536
                pool=[8,9,10,4,6] if frame%2==0 else [0,1,11,5,7]
                while next_input<len(notes) and notes[next_input]['frame']+em.read('speed_offset',True)<=current+1 and len(buttons)<len(pool):
                    buttons.append(pool[len(buttons)]);next_input+=1
            em.run(buttons)
            if em.read('display_state')==1:recent.append(scene())
            if em.read('display_state')==2:
                frozen=scene()
                assert frozen in recent,('Death mixed unpublished graphics with the previous scene',em.snapshot())
                break
        else:raise AssertionError('Did not reach the intended failed tap')
        for _ in range(90):
            em.run();assert scene()==frozen,'Death scene changed after freezing'
        hud=C.string_at(em.ram+0x800,2048)[::2]
        assert b'RHYTHM LOST' in hud,'Failure HUD was not uploaded'
        em.capture(out/'frozen.png')
        result=dict(**em.evidence(),level=args.level,speed=args.speed,step=em.read('step'),
                    retains_completed_scene=True,frozen_frames=90,failure_text_visible=True)
        (out/'result.json').write_text(json.dumps(result,indent=2));print(result,flush=True)
    finally:em.close()

if __name__=='__main__':main()
