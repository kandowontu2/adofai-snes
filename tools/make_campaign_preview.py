"""Capture the current cartridge's options, angular track, and moving streaks."""
from pathlib import Path
import shutil
import hashlib,json
from PIL import Image
from emulate import Emulator
from input_helpers import configure,press

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'build/campaign/verification'

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    em=Emulator(rom=ROOT/'build/campaign/adofai.sfc')
    try:
        for _ in range(120):em.run()
        em.capture(OUT/'menu.png')
        configure(em,12,True,3,5)
        press(em,0)
        for _ in range(8):em.run()
        em.capture(OUT/'options.png')
    finally:em.close()
    em=Emulator(rom=ROOT/'build/campaign/adofai.sfc');frames=[]
    try:
        for _ in range(120):em.run()
        for _ in range(8):press(em,5)
        press(em,1)
        press(em,3)
        for _ in range(2400):
            em.run()
            if em.read('step')>=60:break
        assert em.read('step')>=60
        for frame in range(240):
            em.run()
            if frame%3==0:
                path=OUT/'preview-frame.png';em.capture(path)
                im=Image.open(path).convert('RGB').resize((768,672),Image.Resampling.NEAREST)
                frames.append(im)
                if frame==60:im.save(OUT/'official-preview.png')
        frames[0].save(OUT/'effects.gif',save_all=True,append_images=frames[1:],duration=50,loop=0,optimize=True)
    finally:em.close()
    shutil.copyfile(OUT/'perfect-1/final.png',OUT/'results.png')
    em=Emulator(rom=ROOT/'build/packs/crown/adofai.sfc');frames=[]
    try:
        for _ in range(120):em.run()
        press(em,5);press(em,5);press(em,1);press(em,3)
        for _ in range(5000):
            em.run()
            if em.read('step')>=200:break
        assert em.read('step')>=200
        for frame in range(240):
            em.run()
            if frame%3==0:
                path=OUT/'preview-frame.png';em.capture(path)
                im=Image.open(path).convert('RGB').resize((768,672),Image.Resampling.NEAREST);frames.append(im)
                if frame==90:im.save(OUT/'visibility.png')
        frames[0].save(OUT/'visibility.gif',save_all=True,append_images=frames[1:],duration=50,loop=0,optimize=True)
    finally:em.close()
    (OUT/'preview.json').write_text(json.dumps(dict(rom_sha256=hashlib.sha256((ROOT/'build/campaign/adofai.sfc').read_bytes()).hexdigest(),
        images=['official-preview.png','effects.gif','options.png','results.png','menu.png','visibility.png','visibility.gif'],
        visibility_rom_sha256=hashlib.sha256((ROOT/'build/packs/crown/adofai.sfc').read_bytes()).hexdigest()),indent=2))
    print('Captured options, results, track outlines, and four seconds of continuous streaks.')

if __name__=='__main__':main()
