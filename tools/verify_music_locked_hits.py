"""Verify whole-song audible output against the sample-aligned PCM reference."""
import argparse
import ctypes as C
import json
from pathlib import Path

import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, correlate, resample_poly, sosfiltfilt

from emulate import Emulator, ROOT
from input_helpers import press


def capture(base, out, mode):
    em = Emulator(rom=base/'adofai.sfc')
    try:
        for _ in range(120):
            em.run()
        press(em,1 if mode=='auto' else 9)
        press(em,3)
        em.audio.clear()
        audio_start = None
        pcm_backend = False
        samples = 0
        for frame in range(9000):
            before = len(em.audio)
            em.run([8] if mode=='manual' and frame%19==0 else [])
            samples += sum(len(b)//4 for b in em.audio[before:])
            assert C.c_uint16.from_address(em.ram+0x1fc36).value == 0, 'Second percussion source fired'
            if audio_start is None and em.read('music_active'):
                audio_start = samples/em.av.timing.sample_rate
                pcm_backend = bool(em.read('msu_pcm'))
            if em.read('state')==3:
                break
        assert em.read('state')==3 and em.read('step')>=em.read('last_note')
        em.save_audio(out/f'{mode}.wav')
        return dict(audio_start=audio_start,pcm=pcm_backend,mode=mode,**em.evidence())
    finally:
        em.close()


def check(base, reference, out):
    out.mkdir(parents=True,exist_ok=True)
    chart = json.loads((base/'level1.json').read_text())
    pcm = np.frombuffer(reference.read_bytes()[8:],dtype='<i2').reshape(-1,2).mean(axis=1)
    target_rate = 8000
    filt = butter(4,1800,fs=target_rate,output='sos')
    expected = sosfiltfilt(filt,resample_poly(pcm,target_rate,44100))
    results = []
    for mode in ('manual','auto'):
        result = capture(base,out,mode)
        rate, actual = wavfile.read(out/f'{mode}.wav')
        actual = sosfiltfilt(filt,resample_poly(actual.astype(float).mean(axis=1),target_rate,rate))
        speed = 1 if result['pcm'] else 32040/32000
        windows = []
        for note in chart['notes'][1:-1]:
            second = note['time']
            start = round(second*target_rate)
            template = expected[start:start+round(.12*target_rate)]
            center = round((result['audio_start']+second/speed)*target_rate)
            low = max(0,center-round(.18*target_rate))
            candidate = actual[low:center+round(.18*target_rate)+len(template)]
            score = correlate(candidate,template,'valid',method='fft')
            energy = np.r_[0,np.cumsum(candidate*candidate)]
            norms = energy[len(template):]-energy[:-len(template)]
            score /= np.sqrt(np.maximum(norms*np.dot(template,template),1))
            peak = int(np.argmax(score))
            value = float(score[peak])
            assert value > .95, (mode,note['step'],value)
            windows.append(dict(note=note['step'],correlation=value))
        result.update(windows=windows,second_percussion_commands=0,completed_song=True)
        results.append(result)
    report = dict(passed=True,cases=results,scope='Whole 1-X run, including the buildup and all later sections; rendered music compared to sample-aligned reference, no second hit source')
    (out/'result.json').write_text(json.dumps(report,indent=2))
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--base',type=Path,default=ROOT/'build/packs/sa1-scheduled-hits')
    parser.add_argument('--reference',type=Path,default=ROOT/'build/packs/sa1-scheduled-hits/sample-clock-pcm/adofai-1.pcm')
    args=parser.parse_args()
    result=check(args.base,args.reference,args.base/'verification/music-locked-hits')
    print('PASS full 1-X manual/autoplay:',[min(w['correlation'] for w in r['windows']) for r in result['cases']])
