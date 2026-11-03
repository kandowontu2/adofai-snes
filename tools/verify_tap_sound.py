"""Listen for the SPC percussion voice during manual and autoplay taps."""
import argparse,json
import numpy as np
from emulate import Emulator,ROOT
from input_helpers import press,configure

def run(base,autoplay,speed):
    em=Emulator(rom=base/'adofai.sfc')
    try:
        for _ in range(120):em.run()
        configure(em,speed)
        if autoplay:press(em,1)
        press(em,3)
        initial=em.read('HIT_SOUND_COMMAND') if 'HIT_SOUND_COMMAND' in em.labels else None
        # HIT_SOUND_COMMAND is intentionally outside the shared BSS.
        import ctypes as C
        command=lambda:C.c_uint16.from_address(em.ram+0x1fc32).value
        before=command();changed=False;tap_frame=None
        audio_origin=em.frames
        em.audio.clear()
        for frame in range(1800):
            buttons=[]
            # An offbeat tap during the count-in isolates the drum from the
            # song and metronome; it need not be a successful landing.
            if not autoplay and em.read('music_active') and em.read('nmi_audio_ticks')>=75 and tap_frame is None:
                buttons=[8];tap_frame=frame
            em.run(buttons)
            if command()!=before:
                changed=True;tap_frame=frame if tap_frame is None else tap_frame
                if frame>tap_frame+8:break
            if changed and frame>tap_frame+8:break
        assert changed,(autoplay,speed,em.snapshot())
        pcm=np.frombuffer(b''.join(em.audio),dtype='<i2').reshape(-1,2).mean(axis=1)
        sr=em.av.timing.sample_rate
        start=max(0,round((tap_frame-1)/em.av.timing.fps*sr))
        clip=pcm[start:round((tap_frame+8)/em.av.timing.fps*sr)]
        assert len(clip) and np.max(np.abs(clip))>500,'Tap command produced no audible sound'
        # The actual SPC sample directory points both alternating voices to
        # the percussion sample, outside the music stream's ring buffer.
        spc=(base/'spc.bin').read_bytes()
        assert spc[0x508:0x50c]==bytes([0,10,0,10])
        return dict(autoplay=autoplay,speed=speed/10,audible_peak=int(np.max(np.abs(clip))),**em.evidence())
    finally:em.close()

def verify_isolation(base):
    streams=[];states=[]
    for muted in (False,True):
        em=Emulator(rom=base/'adofai.sfc',mute_taps=muted)
        try:
            for _ in range(120):em.run()
            press(em,3);em.audio.clear();tapped=False
            for _ in range(600):
                tap=not tapped and em.read('music_active') and em.read('nmi_audio_ticks')>=75
                em.run([8] if tap else [])
                tapped|=bool(tap)
                if tapped and em.read('nmi_audio_ticks')>=115:break
            assert tapped
            streams.append(np.frombuffer(b''.join(em.audio),dtype='<i2').astype(float))
            states.append({key:em.read(key) for key in ('state','step','elapsed','combo','nmi_audio_ticks')})
            if not muted:em.save_audio(base/'verification/tap-sample.wav')
            em.evidence()
        finally:em.close()
    assert states[0]==states[1] and streams[0].shape==streams[1].shape,'Channel isolation changed gameplay timing'
    difference=streams[0]-streams[1]
    assert np.max(np.abs(difference))>500,'Frontend failed to isolate the percussion voices'
    return dict(passed=True,percussion_peak=int(np.max(np.abs(difference))),music_rms=float(np.std(streams[1])),identical_gameplay_timing=True)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--pack',default='master');args=ap.parse_args()
    base=ROOT/'build/packs'/args.pack
    (base/'verification').mkdir(exist_ok=True)
    rows=[run(base,auto,speed) for auto in (False,True) for speed in (10,20)]
    out=base/'verification/tap-sounds.json'
    out.write_text(json.dumps(dict(passed=True,cases=rows,isolation=verify_isolation(base),rom_sha256=rows[0]['rom_sha256'],msu_sha256=rows[0]['msu_sha256']),indent=2))
    print('PASS: manual and autoplay percussion with PCM and BRR music')

if __name__=='__main__':main()
