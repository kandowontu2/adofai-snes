"""Capture a short, unmodified controller replay of the actual SNES ROM."""
import json
from pathlib import Path
from PIL import Image
from emulate import Emulator

root=Path(__file__).resolve().parents[1]
out=root/'build/preview-frames';out.mkdir(exist_ok=True)
notes=json.loads((root/'build/level.json').read_text())['notes']
em=Emulator();frames=[];started=False;capturing=False;count=0
try:
    for frame in range(3800):
        s=em.snapshot();buttons=[]
        if frame==120:buttons=[3];started=True
        if s['state']==1 and started:
            target=notes[min(s['step']+1,167)]['frame']
            if target<=s['elapsed']+1<=target+2:buttons=[8]
        em.run(buttons)
        if s['step']>=118:capturing=True
        if capturing:
            if count%3==0:
                p=out/f'{count:04d}.png';em.capture(p)
                im=Image.open(p).convert('RGB');frames.append(im.resize((512,448),Image.Resampling.NEAREST))
                if count==150:im.resize((768,672),Image.Resampling.NEAREST).save(root/'build/preview.png')
            count+=1
            if count>=360:break
    assert len(frames)==120
    frames[0].save(root/'build/preview.gif',save_all=True,append_images=frames[1:],duration=50,loop=0,optimize=True)
    print('Captured six seconds from the SNES ROM:',root/'build/preview.gif')
finally:em.close()
