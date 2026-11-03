"""Verify scheduled chart percussion with real ROM, unrelated manual taps and calibration."""
import argparse,json,ctypes as C
from pathlib import Path
from emulate import Emulator,ROOT
from input_helpers import press,configure
from hit_sound_assets import selections
from hit_timing import lead_frames

def check(base,level=None,calibration=0,speed=1,mode='manual',limit=64):
 levels=json.loads((base/'pack.json').read_text())['levels'];level=level or (25 if 25 in levels else levels[0])
 chart=json.loads((base/f'level{level}.json').read_text())
 sounds=selections(chart,json.loads((ROOT/'assets/private/hitsound-levels.json').read_text())[str(level)])
 notes=[n for n,(sound,vol) in zip(chart['notes'][1:],sounds[1:]) if not n['flags']&8 and sound!='None' and vol]
 em=Emulator(rom=base/'adofai.sfc');rows=[]
 def word(at):return C.c_uint16.from_address(em.ram+at).value
 try:
  for _ in range(120):em.run()
  configure(em,round(speed*10),calibration=calibration)
  for _ in range(levels.index(level)):press(em,5)
  press(em,1 if mode=='auto' else 9);press(em,3)
  before=word(0x1fc36)
  for frame in range(16000):
   em.run([8] if mode=='manual' and frame%19==0 else [])
   after=word(0x1fc36)
   for _ in range((after-before)&65535):
    note=notes[len(rows)];phase=word(0x1fc0e)+lead_frames(level,bool(em.read('msu_pcm')))-note['frame']
    rows.append(dict(step=note['step'],phase_frames=phase))
    assert -.01<=phase<=max(2,2*speed),(level,mode,calibration,rows[-1])
   before=after
   if notes and len(rows)>=min(limit,len(notes)):break
   if not notes and em.read('step')>=min(limit,chart['steps']):break
  assert len(rows)>=min(limit,len(notes)),(level,em.snapshot(),rows)
  if not notes:assert em.read('step')>=min(limit,chart['steps']),(level,em.snapshot())
  return dict(passed=True,level=level,mode=mode,calibration=calibration,speed=speed,pcm=bool(em.read('msu_pcm')),hits=len(rows),max_delay_frames=max((r['phase_frames'] for r in rows),default=0),**em.evidence())
 finally:em.close()

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--pack',required=True);ap.add_argument('--level',type=int);a=ap.parse_args();base=ROOT/'build/packs'/a.pack
 rows=[check(base,a.level,c,mode=m) for m in ('manual','silent','auto') for c in (-8,0,8)]
 rows.append(check(base,a.level,0,2,'manual'))
 p=base/'verification/scheduled-hits.json';p.parent.mkdir(exist_ok=True);p.write_text(json.dumps(dict(passed=True,cases=rows),indent=2));print(json.dumps(rows),flush=True)
if __name__=='__main__':main()
