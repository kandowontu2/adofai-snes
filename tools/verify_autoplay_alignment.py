"""Measure autoplay hit phase on the raw song clock, independent of calibration."""
import argparse,json,ctypes as C
import numpy as np
from emulate import Emulator,ROOT
from input_helpers import press,configure

def check(base,calibration):
    levels=json.loads((base/'pack.json').read_text())['levels'];level=25 if 25 in levels else levels[0]
    chart=json.loads((base/f'level{level}.json').read_text());notes=[n for n in chart['notes'][1:] if not n['flags']&8]
    em=Emulator(rom=base/'adofai.sfc');rows=[];index=0
    try:
        for _ in range(120):em.run()
        configure(em,10,calibration=calibration)
        levels=json.loads((base/'pack.json').read_text())['levels']
        for _ in range(levels.index(level)):press(em,5)
        press(em,1);press(em,3)
        # Silent authored hit sounds issue no SPC command; landings still
        # need the same music-clock phase check.
        counter=lambda:em.read('combo')
        before=counter()
        for frame in range(3000):
            em.run();after=counter()
            for _ in range((after-before)&65535):
                delta=((em.read('nmi_audio_ticks')-em.read('audio_ticks')+32768)&65535)-32768
                raw=em.read('elapsed')+delta*.004*em.av.timing.fps
                rows.append(dict(step=notes[index]['step'],raw_phase_frames=round(raw-notes[index]['frame'],3)))
                index+=1
            before=after
            if index>=24:break
        assert len(rows)>=24
        return dict(calibration=calibration,median_frames=float(np.median([r['raw_phase_frames'] for r in rows])),max_frames=max(r['raw_phase_frames'] for r in rows),hits=rows,**em.evidence())
    finally:em.close()

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--pack',required=True);ap.add_argument('--baseline',action='store_true');a=ap.parse_args()
    base=ROOT/'build/packs'/a.pack;rows=[check(base,c) for c in (-8,0,8)]
    if not a.baseline:
        assert max(abs(r['median_frames']) for r in rows)<=1,rows
        assert max(r['median_frames'] for r in rows)-min(r['median_frames'] for r in rows)<=1,rows
    out=base/'verification';out.mkdir(exist_ok=True)
    (out/'autoplay-alignment.json').write_text(json.dumps(dict(passed=not a.baseline,baseline=a.baseline,cases=rows),indent=2))
    print([(r['calibration'],r['median_frames'],r['max_frames']) for r in rows],flush=True)

if __name__=='__main__':main()
