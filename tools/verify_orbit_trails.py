"""Inspect rendered OBJ pixels for attached, circular streaks in a real replay."""
import argparse,ctypes as C,json,subprocess
from pathlib import Path
import numpy as np
from scipy.ndimage import label
from PIL import Image,ImageDraw
from emulate import Emulator,ROOT
from input_helpers import press

def tiles(raw):
    data=np.frombuffer(raw,dtype=np.uint8).reshape(256,32)
    result=np.zeros((256,8,8),dtype=np.uint8)
    for b in range(4):
        for y in range(8):
            for x in range(8):result[:,y,x]|=((data[:,(b//2)*16+y*2+b%2]>>(7-x))&1)<<b
    return result

def sprite_mask(row,high,index,patterns):
    x,y,tile,attr=map(int,row)
    bits=(int(high[index//4])>>(index%4*2))&3
    if bits&1:x-=256
    size=16 if bits&2 else 8
    bitmap=patterns[tile].copy() if size==8 else np.block([[patterns[tile],patterns[tile+1]],
                                                         [patterns[tile+16],patterns[tile+17]]])
    if attr&64:bitmap=bitmap[:,::-1]
    if attr&128:bitmap=bitmap[::-1]
    mask=np.zeros((256,384),bool)
    if y<224 and -16<=x<256:mask[y:y+size,x+32:x+32+size]=bitmap!=0
    return mask

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--level',type=int,default=46)
    ap.add_argument('--base',type=Path,default=ROOT/'build/packs/master');ap.add_argument('--seconds',type=int,default=90);ap.add_argument('--start-step',type=int,default=310)
    args=ap.parse_args();base=args.base.resolve();out=base/f'verification/orbit-trails-{args.level}';out.mkdir(parents=True,exist_ok=True)
    em=Emulator(rom=base/'adofai.sfc');samples=curves=components=0;error=0.;frames=[];frame_meta=[];patterns=None
    try:
        for _ in range(120):em.run()
        for _ in range(json.loads((base/'pack.json').read_text())['levels'].index(args.level)):press(em,5)
        press(em,1);press(em,3)
        for frame in range(round(args.seconds*em.av.timing.fps)):
            em.run()
            if em.read('state')!=1:continue
            assert em.read('camera_zoom')==em.read('camera_inverse')==256,'Zoom is still active'
            if em.read('step')>=args.start_step and len(frames)<240:
                em.capture(out/'capture.png');frames.append(Image.open(out/'capture.png').convert('RGB'))
                frame_meta.append((frame,em.read('step')))
            if not em.read('frame_ready'):continue
            if patterns is None:patterns=tiles(C.string_at(em.core.retro_get_memory_data(3)+0xc000,8192))
            oam=np.frombuffer(C.string_at(em.ram+0x200,544),dtype=np.uint8)
            objects=oam[:512].reshape(128,4);high=oam[512:]
            body={int(row[3])&14:sprite_mask(row,high,i,patterns) for i,row in enumerate(objects[:2]) if int(row[1])<224}
            trails={p:np.zeros((256,384),bool) for p in body}
            for i,row in enumerate(objects):
                p=int(row[3])&14
                if int(row[2])>=128 and int(row[1])<224 and p in trails:
                    trails[p]|=sprite_mask(row,high,i,patterns)
            for p,mask in trails.items():
                groups,n=label(mask,structure=np.ones((3,3)));attached=set(np.unique(groups[body[p]]))-{0}
                if len(attached)!=n:
                    em.capture(out/'detached.png')
                    raise AssertionError(('Detached trail pixels',frame,em.snapshot(),p,n,sorted(attached)))
                components+=n
            moving=int(objects[1,3])&14
            if int(objects[0,1])<224 and int(objects[1,1])<224 and trails[moving].any():
                px=int(objects[0,0])-(256 if high[0]&1 else 0)+8+32;py=int(objects[0,1])+8
                yy,xx=np.nonzero(trails[moving]);radial=np.abs(np.hypot(xx-px,yy-py)-24)
                error=max(error,float(radial.max()))
                assert radial.max()<2.6,('Streak cut across the circular orbit',frame,float(radial.max()),em.snapshot())
                curves+=1
            samples+=1
        assert samples>100 and curves>100 and components>100,(samples,curves,components)
        if frames:
            video=out/'motion.mp4'
            p=subprocess.Popen(['ffmpeg','-v','error','-y','-f','rawvideo','-pixel_format','rgb24','-video_size','256x224',
                                '-framerate',str(em.av.timing.fps),'-i','-','-an','-vf','scale=768:672:flags=neighbor','-c:v','libx264','-crf','16',
                                '-pix_fmt','yuv420p','-movflags','+faststart',str(video)],stdin=subprocess.PIPE)
            for im in frames:p.stdin.write(im.tobytes())
            p.stdin.close();assert p.wait()==0
            sheet=Image.new('RGB',(1024,480),(8,10,20));d=ImageDraw.Draw(sheet)
            for j,i in enumerate((72,76,78,80,82,84,88,92)):
                im=frames[i];x=j%4*256;y=j//4*240
                sheet.paste(im,(x,y+16));d.text((x+4,y+2),f'Frame {frame_meta[i][0]} / step {frame_meta[i][1]}',fill='white')
            sheet.save(out/'motion-samples.png')
        result=dict(**em.evidence(),level=args.level,native_scale=True,samples=samples,circular_samples=curves,
                    checked_components=components,detached_components=0,maximum_radial_error=round(error,3),
                    preview_fps=em.av.timing.fps,preview_frames=len(frames))
        (out/'result.json').write_text(json.dumps(result,indent=2));print(result,flush=True)
    finally:em.close()

if __name__=='__main__':main()
