"""Check real-controller fresh-start and checkpoint audio routing in small editions."""
import json
from emulate import Emulator,ROOT
from input_helpers import press,wait

def main():
    for edition in ('hybrid','compressed'):
        base=ROOT/f'build/packs/sa1-renderer-{edition}';rows=[]
        for n in (25,31,45,63):
            c=json.loads((base/f'level{n}.json').read_text());cp=c['checkpoints'][0]
            em=Emulator(rom=base/'adofai.sfc');next_tap=1;stage='reach';fresh=None
            try:
                for _ in range(120):em.run()
                for _ in range(n-1):press(em,5)
                press(em,3)
                for frame in range(round(c['duration']*61)+1200):
                    state=em.read('state');buttons=[]
                    if state==1:
                        if fresh is None and em.read('music_active'):
                            fresh=em.read('msu_pcm');assert fresh==int(edition=='hybrid')
                        if stage=='reach' and em.read('checkpoint_floor')==cp['floor'] and em.read('step')>=cp['trigger']:stage='die'
                        if stage=='reach':
                            delta=((em.read('nmi_audio_ticks')-em.read('audio_ticks')+32768)&65535)-32768
                            now=em.read('elapsed')+delta*.004*em.av.timing.fps
                            pool=[8,9,10,4,6] if frame%2==0 else [0,1,11,5,7]
                            while next_tap<=c['steps'] and c['notes'][next_tap]['frame']+em.read('speed_offset',True)<=now+1 and len(buttons)<len(pool):
                                if not c['notes'][next_tap]['flags']&8:buttons.append(pool[len(buttons)])
                                next_tap+=1
                    elif state==2:
                        assert stage=='die',em.snapshot()
                        for _ in range(8):em.run()
                        press(em,3);wait(em,lambda:em.read('state')==1)
                        assert em.read('checkpoints_used')==1 and em.read('msu_pcm')==0
                        assert em.read('checkpoint_preroll')==1
                        start=em.read('audio_ticks')
                        for _ in range(90):em.run()
                        assert em.read('audio_ticks')!=start
                        rows.append(dict(level=n,fresh_pcm=bool(fresh),retry_pcm=False,countdown=True,audio_clock_advances=True))
                        break
                    em.run(buttons)
                else:raise AssertionError('No checkpoint retry reached')
                evidence=em.evidence()
            finally:em.close()
        report=dict(passed=True,edition=edition,**evidence,routes=rows)
        (base/'verification/audio-routing.json').write_text(json.dumps(report,indent=2));print(report,flush=True)

if __name__=='__main__':main()
