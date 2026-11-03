"""Measure delivered visual frames and capture real ROM presentation samples."""
import argparse,json,math,ctypes as C
from pathlib import Path
from PIL import Image
from emulate import Emulator,ROOT
from input_helpers import press,configure

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--base',type=Path,default=ROOT/'build/packs/master')
    ap.add_argument('--level',type=int,default=11)
    ap.add_argument('--seconds',type=int,default=90)
    ap.add_argument('--start-step',type=int)
    ap.add_argument('--measure-from-step',type=int,default=0)
    ap.add_argument('--measure-to-step',type=int)
    ap.add_argument('--out',type=Path)
    ap.add_argument('--speed',type=float,default=1.)
    args=ap.parse_args();base=args.base.resolve()
    out=args.out or base/f'verification/presentation-{args.level}';out.mkdir(parents=True,exist_ok=True)
    chart=json.loads((base/f'level{args.level}.json').read_text())
    target=args.start_step if args.start_step is not None else {1:30,11:145,41:65,46:310,53:60,60:60,61:600}.get(args.level,50)
    em=Emulator(rom=base/'adofai.sfc')
    frames=[];samples=[];gaps=[];gap=0;last=None;zooms=[];started=False;busy_phases={};worker_phases={};cache_states={};measured_frames=0;long_gaps=[]
    try:
        for _ in range(120):em.run()
        if args.speed!=1:configure(em,round(args.speed*10))
        levels=json.loads((base/'pack.json').read_text())['levels']
        for _ in range(levels.index(args.level)):press(em,5)
        press(em,1);press(em,3)
        for frame in range(round(args.seconds*em.av.timing.fps)):
            em.run()
            if em.read('state')!=1:continue
            if em.read('music_active') and em.read('step')>=args.measure_from_step and (args.measure_to_step is None or em.read('step')<=args.measure_to_step):
                measured_frames+=1
                if not em.read('frame_ready'):
                    phase=em.read('profile_phase');busy_phases[phase]=busy_phases.get(phase,0)+1
                    if em.sa1:
                        worker=C.c_uint16.from_address(em.cache_ram+0x30).value
                        worker_phases[worker]=worker_phases.get(worker,0)+1
                        key=tuple(C.c_uint16.from_address(em.cache_ram+at).value for at in (0xA,4,6))
                        cache_states[str(key)]=cache_states.get(str(key),0)+1
                commit=em.read('commits');gap+=1
                if last is not None and commit!=last:
                    if gap>30:long_gaps.append(dict(frames=gap,step=em.read('step'),chart_time=em.read('chart_time'),frame=frame))
                    gaps.append(gap);gap=0
                last=commit
                zooms.append(em.read('display_zoom',True))
            if em.read('step')>=target:started=True
            if started and len(samples)<240:
                samples.append({'frame':frame,'step':em.read('step'),'chart_time':em.read('chart_time'),
                                'commits':em.read('commits'),'zoom':em.read('display_zoom',True)})
                if len(samples)%3==0:
                    em.capture(out/'capture.png')
                    im=Image.open(out/'capture.png').convert('RGB').resize((768,672),Image.Resampling.NEAREST)
                    frames.append(im)
                    if len(samples) in (60,120,180):im.save(out/f'frame-{len(samples):03}.png')
            if em.read('step')==chart['steps']:break
        if frames:frames[0].save(out/'motion.gif',save_all=True,append_images=frames[1:],duration=50,loop=0)
        result=dict(**em.evidence(),code=chart['code'],speed=args.speed,visual_fps=round(em.av.timing.fps*len(gaps)/measured_frames,2),
                    delivered_frames=len(gaps),measured_ntsc_frames=measured_frames,
                    longest_gap=max([gap,*gaps]),p95_gap=sorted([gap,*gaps])[math.floor(.95*len(gaps))],
                    zoom_range=[min(zooms)/256,max(zooms)/256],busy_phases=busy_phases,worker_phases=worker_phases,cache_states=cache_states,samples=samples,
                    measure_from_step=args.measure_from_step,measure_to_step=args.measure_to_step,long_gaps=long_gaps)
        (out/'result.json').write_text(json.dumps(result,indent=2))
        print(json.dumps({k:v for k,v in result.items() if k!='samples'}),flush=True)
    finally:em.close()

if __name__=='__main__':main()
