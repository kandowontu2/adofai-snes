"""Capture actual zoom-scaled planet sprites and check their tile selections."""
import ctypes as C,json,argparse
from pathlib import Path
from emulate import Emulator,ROOT
from input_helpers import press

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--pack',required=True);a=ap.parse_args();base=ROOT/'build/packs'/a.pack;out=base/'verification/planet-zoom';out.mkdir(parents=True,exist_ok=True)
 em=Emulator(rom=base/'adofai.sfc');seen={}
 try:
  for _ in range(120):em.run()
  for _ in range(json.loads((base/'pack.json').read_text())['levels'].index(23)):press(em,5)
  press(em,1);press(em,3)
  for frame in range(10000):
   em.run()
   if em.read('state')==3:break
   if em.read('state')!=1 or not em.read('frame_ready'):continue
   r=em.read('m7_radius');inv=em.read('camera_inverse');expected=max(3,min(14,(7*inv+128)//256));assert r==expected,(r,expected,inv)
   o=C.string_at(em.ram+0x200,32)
   if o[1]>=177 or o[17]>=177:continue
   tiles=[o[i] for i in (2,6,10,14)]
   want=[10,14,40,42] if r<=10 else [44,46,70,78] if r<=12 else [96,98,100,102]
   if r>=9:assert tiles==want,(r,tiles,want)
   else:assert tiles[0]==[64,64,65,66,67,0,2,6,4][r],(r,tiles)
   if r not in seen:
    seen[r]=dict(frame=frame,inverse=inv,zoom=em.read('camera_zoom'),tiles=tiles)
    em.capture(out/f'radius-{r}.png')
  assert 4 in seen and 7 in seen and 14 in seen,seen
  (out/'result.json').write_text(json.dumps(dict(passed=True,sizes=seen,**em.evidence()),indent=2));print('PASS planet zoom',sorted(seen))
 finally:em.close()
if __name__=='__main__':main()
