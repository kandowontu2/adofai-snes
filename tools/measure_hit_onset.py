"""Measure audible SPC percussion onset relative to supplied controller frames."""
import argparse,json,ctypes as C
import numpy as np
from emulate import Emulator,ROOT
from input_helpers import press,wait

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--pack',default='sa1-renderer-compressed');ap.add_argument('--level',type=int,default=25);a=ap.parse_args()
    base=ROOT/'build/packs'/a.pack;em=Emulator(rom=base/'adofai.sfc');rows=[]
    try:
        for channel in (1,2):
            em.frontend_values[f'snes9x_sndchan_{channel}'.encode()]=b'disabled'
            em.frontend_values[f'snes9x_sndchan_volume_{channel}'.encode()]=b'0'
        em.options_dirty=True
        for _ in range(120):em.run()
        for _ in range(a.level-1):press(em,5)
        press(em,9);press(em,3);wait(em,lambda:em.read('music_active'),1000)
        for _ in range(240):em.run()
        count=lambda:C.c_uint16.from_address(em.ram+0x1fc36).value
        for trial in range(12):
            for _ in range(40+trial%3):em.run()
            em.audio.clear();before=count();em.run([8]);commands=count()-before
            for _ in range(8):em.run()
            pcm=np.frombuffer(b''.join(em.audio),dtype='<i2').reshape(-1,2).astype(float)
            envelope=np.max(np.abs(pcm),axis=1);peak=float(envelope.max());assert peak>100
            threshold=max(16,peak*.01);indices=np.flatnonzero(envelope>threshold)
            rows.append(dict(trial=trial,command_same_frame=commands==1,onset_ms=round(float(indices[0])*1000/em.av.timing.sample_rate,3),peak=peak))
        report=dict(**em.evidence(),level=a.level,core='Snes9x libretro',host_audio_buffer_included=False,input_reference='start of supplied controller frame',muted_channels=[1,2],samples=rows)
        path=base/'verification/hit-onset.json';path.write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
    finally:em.close()

if __name__=='__main__':main()
