"""Capture the real master menu, tight tech pairs, and checkpoint results."""
import ctypes as C,hashlib,json,shutil,subprocess
from pathlib import Path
from PIL import Image
from emulate import Emulator,ROOT
from input_helpers import press
BASE=ROOT/'build/packs/master';OUT=BASE/'verification/preview'

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    em=Emulator(rom=BASE/'adofai.sfc')
    loaded_identity=dict(em.loaded_identity)
    try:
        for _ in range(120):em.run()
        for _ in range(40):press(em,5)
        em.capture(OUT/'menu.png')
        chart=json.loads((BASE/'level41.json').read_text())
        notes=[n for n in chart['notes'][1:] if not(n['flags']&8)]
        pairs=[a for a,b in zip(notes,notes[1:]) if b['frame']-a['frame']<=3 and 40<a['step']<90]
        target=pairs[0]['step']-2
        press(em,1);press(em,3)
        for _ in range(12000):
            em.run()
            if em.read('step')>=target:break
        assert em.read('step')>=target
        frames=[];best=-1
        for frame in range(240):
            em.run()
            em.capture(OUT/'capture.png')
            im=Image.open(OUT/'capture.png').convert('RGB').resize((768,672),Image.Resampling.NEAREST)
            frames.append(im)
            oam=C.string_at(em.ram+0x200,512)
            strokes=[oam[i+2] for i in range(0,512,4) if oam[i+2]>=128 and 32<=oam[i+1]<160]
            score=len(strokes)
            if score>best:im.save(OUT/'tech-pairs.png');best=score
        p=subprocess.Popen(['ffmpeg','-v','error','-y','-f','rawvideo','-pixel_format','rgb24','-video_size','768x672',
                            '-framerate',str(em.av.timing.fps),'-i','-','-an','-c:v','libx264','-crf','16',
                            '-pix_fmt','yuv420p','-movflags','+faststart',str(OUT/'tech-pairs.mp4')],stdin=subprocess.PIPE)
        for im in frames:p.stdin.write(im.tobytes())
        p.stdin.close();assert p.wait()==0
        capture_fps=em.av.timing.fps
    finally:em.close()
    em=Emulator(rom=BASE/'adofai.sfc')
    try:
        for _ in range(120):em.run()
        for _ in range(29):press(em,5)
        press(em,1);press(em,3)
        for _ in range(8000):
            em.run()
            if em.read('step')>=80 and em.read('frame_ready'):break
        else:raise AssertionError('CE-X color capture did not reach tile 80')
        em.run();em.capture(OUT/'ce-x-native.png')
        Image.open(OUT/'ce-x-native.png').resize((768,672),Image.Resampling.NEAREST).save(OUT/'ce-x-colors.png')
    finally:em.close()
    for folder in ('checkpoints-41','perfect-1'):
        result=json.loads((BASE/'verification'/folder/'result.json').read_text())
        assert all(result.get(k)==v for k,v in loaded_identity.items()),('Stale preview source',folder)
    shutil.copyfile(BASE/'verification/checkpoints-41/clear.png',OUT/'results-checkpoints.png')
    shutil.copyfile(BASE/'verification/perfect-1/final.png',OUT/'results-zero.png')
    from verification_data import identity
    assert identity(BASE/'adofai.sfc')==loaded_identity,'Dataset changed during preview capture'
    (OUT/'manifest.json').write_text(json.dumps(dict(**loaded_identity,
        tech_pair_step=target,capture_fps=capture_fps,images=['menu.png','tech-pairs.png','ce-x-colors.png','results-checkpoints.png','results-zero.png'],videos=['tech-pairs.mp4']),indent=2))
    print('Captured native master menu, circular streaks, every video frame, and checkpoint results.',flush=True)

if __name__=='__main__':main()
