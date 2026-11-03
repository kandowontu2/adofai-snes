"""Compare captured SPC/DSP audio to the imported song at multiple times."""
import argparse
import json
import wave
from pathlib import Path
import numpy as np
from scipy.signal import butter, correlate, resample_poly, sosfiltfilt

def main():
    ap=argparse.ArgumentParser();ap.add_argument('folder',type=Path);args=ap.parse_args()
    folder=args.folder
    result=json.loads((folder/'result.json').read_text())
    first=next(x for x in result['transitions'] if x['step']==1)
    milestones=[x for x in result['transitions'] if x['step']>0 and x['state'] in (1,3)]
    clock=np.array([x['elapsed']/result['fps'] for x in milestones])
    video=np.array([(x['frame']+2)/result['fps'] for x in milestones])
    with wave.open(str(folder/'audio.wav'),'rb') as w:
        sr=w.getframerate(); a=np.frombuffer(w.readframes(w.getnframes()),dtype='<i2').reshape(-1,2).mean(axis=1)
    a=resample_poly(a,400,801) if sr==32040 else resample_poly(a,16000,sr)
    root=Path(__file__).resolve().parents[1]
    source=np.fromfile(root/'build/music.pcm',dtype='<i2').astype(float)
    # The DSP's Gaussian interpolation attenuates high frequencies. Compare
    # the shared 0..2.5 kHz band rather than treating that filter as corruption.
    filt=butter(4,2500,fs=16000,output='sos')
    source=sosfiltfilt(filt,source);a=sosfiltfilt(filt,a)
    rows=[]
    for second in [2,5,10,20,30,40,50,60,70,74]:
        ref=source[second*16000:second*16000+4000]
        expected=float(np.interp(second,clock,video))
        if second<clock[0]:expected=video[0]+second-clock[0]
        center=round(expected*16000); radius=2000
        candidate=a[center-radius:center+len(ref)+radius]
        r=correlate(candidate,ref,mode='valid',method='fft')
        sums=np.r_[0,np.cumsum(candidate*candidate)]
        energy=sums[len(ref):]-sums[:-len(ref)]
        scores=r/np.sqrt(np.maximum(energy*np.dot(ref,ref),1))
        peak=int(np.argmax(scores));lag=(peak-radius)/16000
        rows.append({'song_second':second,'correlation':round(float(scores[peak]),5),'offset_ms':round(lag*1000,3)})
    drift=rows[-1]['offset_ms']-rows[0]['offset_ms']
    report={'clock':'SPC700 timer','comparison_band_hz':2500,'windows':rows,'drift_ms':round(drift,3)}
    (folder/'audio-check.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))
    assert min(x['correlation'] for x in rows)>0.90,'Music mismatch, glitch, or stream underrun'
    assert abs(drift)<20,'Music/clock drift exceeds 20 ms'

if __name__=='__main__':main()
