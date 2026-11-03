"""Package the tested ROM and a small, player-facing readme."""
import hashlib
import json
import shutil
import zipfile
from pathlib import Path
from PIL import Image

root=Path(__file__).resolve().parents[1]
out=root/'dist';out.mkdir(exist_ok=True)
rom=out/'adofai-level1-demo.sfc';shutil.copyfile(root/'build/adofai.sfc',rom)
readme='''ADOFAI SNES — 1-X demo

Open adofai-level1-demo.sfc in Mesen or Snes9x (NTSC).

TITLE:    A / Start = Play   X = Practice   Y = Watch
          Left / Right = timing offset
PLAY:     Tap A, B, X, Y, L, R, or D-pad when the planet lands.
          Start = Pause     Select = Restart
PAUSED:   Start = Resume    Select = Title
RESULTS:  A = Retry         Select = Title

Complete 167-step first level, original music converted to SNES BRR,
scrolling track, alternating fire/ice pivots, hit feedback, and slow finale.
No external audio files or expansion hardware are required.

Verified with full controller replays in Snes9x and Mesen:
167 combo / 167 PERFECT / 0 misses.
NTSC target; physical console testing has not been performed.
Settings and best combo are held for the current session only.

Original game/music: fizzd / 7th Beat Games.
https://fizzd.itch.io/a-dance-of-fire-and-ice
Personal fan-port prototype. Source/build instructions: ../README.md
'''
# Write UTF-8 text so the package works outside this workspace as well.
(out/'README.txt').write_text(readme,encoding='utf-8')
shot=root/'build/preview.png'
if shot.exists():shutil.copyfile(shot,out/'preview.png')
else:
    shot=root/'build/verification/perfect/frame-01200.png'
if shot.exists() and not (out/'preview.png').exists():
    im=Image.open(shot);im.resize((im.width*3,im.height*3),Image.Resampling.NEAREST).save(out/'preview.png')
if (root/'build/preview.gif').exists():shutil.copyfile(root/'build/preview.gif',out/'preview.gif')
digest=hashlib.sha256(rom.read_bytes()).hexdigest()
(out/'SHA256SUMS.txt').write_text(digest+'  '+rom.name+'\n')
with zipfile.ZipFile(out/'adofai-level1-demo.zip','w',compression=zipfile.ZIP_DEFLATED) as z:
    for name in ['adofai-level1-demo.sfc','README.txt','SHA256SUMS.txt','preview.png','preview.gif']:
        if (out/name).exists():z.write(out/name,name)
print('Packaged',rom,'\nSHA-256:',digest)
