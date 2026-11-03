"""Check physical pivots and capture the reported square/movement sections."""
import argparse,ctypes as C,json,subprocess
from PIL import Image,ImageDraw
from emulate import Emulator,ROOT
from input_helpers import press

def verify(base,n,target):
    chart=json.loads((base/f'level{n}.json').read_text())
    levels=json.loads((base/'pack.json').read_text())['levels']
    out=base/f'verification/motion-section-{n}';out.mkdir(parents=True,exist_ok=True)
    em=Emulator(rom=base/'adofai.sfc');samples=0;images=[];meta=[]
    try:
        for _ in range(120):em.run()
        for _ in range(levels.index(n)):press(em,5)
        press(em,1);press(em,3)
        for frame in range(round((chart['duration']+1)*em.av.timing.fps)):
            em.run();step=em.read('step')
            if em.read('state')!=1:continue
            if em.read('frame_ready'):
                note=chart['notes'][step]
                if not note['stick_to_floor']:
                    x=C.c_uint16.from_address(em.ram+0x2000+step*2).value
                    y=C.c_uint16.from_address(em.ram+0x3800+step*2).value
                    assert (x,y)==(note['x'],note['y']),('Decorative tile moved the physical pivot',n,step,(x,y),note)
                    samples+=1
            if step>=target and len(images)<180:
                em.capture(out/'capture.png');images.append(Image.open(out/'capture.png').convert('RGB'));meta.append(step)
            if len(images)==180:break
        assert len(images)==180,(n,em.snapshot())
        sheet=Image.new('RGB',(1024,480));draw=ImageDraw.Draw(sheet)
        for j,index in enumerate((0,8,16,24,32,40,48,56)):
            x=j%4*256;y=j//4*240
            sheet.paste(images[index],(x,y+16));draw.text((x+4,y+2),f'{chart["code"]} step {meta[index]}',fill='white')
        sheet.save(out/'samples.png')
        p=subprocess.Popen(['ffmpeg','-v','error','-y','-f','rawvideo','-pixel_format','rgb24','-video_size','256x224','-framerate',str(em.av.timing.fps),'-i','-','-an','-vf','scale=768:672:flags=neighbor','-c:v','libx264','-crf','16','-pix_fmt','yuv420p',str(out/'motion.mp4')],stdin=subprocess.PIPE)
        for im in images:p.stdin.write(im.tobytes())
        p.stdin.close();assert p.wait()==0
        result=dict(passed=True,level=n,code=chart['code'],physical_pivot_samples=samples,**em.evidence())
        (out/'result.json').write_text(json.dumps(result,indent=2));return result
    finally:em.close()

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--pack',default='master');args=ap.parse_args()
    base=ROOT/'build/packs'/args.pack
    rows=[verify(base,n,step) for n,step in ((24,419),(25,45),(26,490),(39,357))]
    (base/'verification/motion-sections.json').write_text(json.dumps(dict(passed=True,cases=rows,rom_sha256=rows[0]['rom_sha256'],msu_sha256=rows[0]['msu_sha256']),indent=2))
    print('PASS: square pivots stay on their physical path; affected charts captured')

if __name__=='__main__':main()
