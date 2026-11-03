"""Compare captured SPC/DSP audio to the imported song at multiple times."""
import argparse
import json
import wave
from pathlib import Path
import numpy as np
from verification_data import data_sha256
from scipy.signal import butter, correlate, resample_poly, sosfiltfilt, find_peaks
from campaign_assets import RATE

def music_filter(assetdir,pitch):
    """Use the original full music comparison band, including bass."""
    high=min(2500,round(4000*1536/pitch))
    return butter(4,high,fs=RATE,output='sos'),0,high

def decode_brr(data):
    # Decode the actual lossy cartridge stream; transport checks must not
    # confuse the encoder's quantization with a dropped or repeated packet.
    out=np.empty(len(data)//9*16,dtype=np.int16);p=q=j=0
    for b in range(0,len(data),9):
        header=data[b];shift=header>>4;f=(header>>2)&3
        for byte in data[b+1:b+9]:
            for v in (byte>>4,byte&15):
                if v>=8:v-=16
                pred=0
                if f==1:pred=p+((-p)>>4)
                if f==2:pred=p*2+((-p*3)>>5)-q+(q>>4)
                if f==3:pred=p*2+((-p*13)>>6)-q+((q*3)>>4)
                r=max(-32768,min(32767,((v<<shift)>>1)+pred))
                r=(((r*2+32768)&65535)-32768)>>1
                out[j]=r*2;j+=1;q=p;p=r
    return out.astype(float)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('folder',type=Path);args=ap.parse_args()
    folder=args.folder
    result=json.loads((folder/'result.json').read_text())
    pcm=bool(result['final'].get('msu_pcm'))
    milestones=[x for x in result['transitions'] if x['state'] in (1,3) and x.get('music_active',1)]
    clock=np.array([x['elapsed']/result['fps'] for x in milestones])
    if pcm:clock=np.array([x['msu_elapsed_frames']/result['fps'] for x in milestones])
    elif 'nmi_audio_ticks' in milestones[0]:
        raw=np.array([x['nmi_audio_ticks'] for x in milestones],dtype=np.int64)
        wraps=np.r_[0,np.cumsum(np.diff(raw)<-32768)]
        clock=(raw+wraps*65536)*.004*result.get('speed_pitch',1536)/1536
    video=np.array([(x['frame']+1+result['audio_frame_offset'])/result['fps'] for x in milestones])
    with wave.open(str(folder/'audio.wav'),'rb') as w:
        sr=w.getframerate(); a=np.frombuffer(w.readframes(w.getnframes()),dtype='<i2').reshape(-1,2).mean(axis=1)
    # BRR pitch and SPC timers share the APU crystal. Convert to nominal APU
    # seconds, so Snes9x's 32040-Hz clock does not skew each reference window.
    # Snes9x switches its output mixer to 44.1 kHz whenever MSU is present,
    # including BRR fallback. That output rate is not the SPC crystal rate.
    msu=bool(result['final'].get('msu_present'))
    apu_speed=1 if pcm else (32040/32000 if msu else sr/32000)
    if msu and not pcm:a=resample_poly(a,RATE*801,sr*800)
    else:a=resample_poly(a,RATE,sr if pcm else 32000)
    pitch=result.get('speed_pitch',1536)
    if pitch!=1536:a=resample_poly(a,pitch,1536)
    root=Path(__file__).resolve().parents[1]
    assetdir=Path(result.get('asset_directory',root/'build/campaign'))
    assert result.get('msu_sha256')==data_sha256(assetdir),'MSU data changed since the captured replay'
    spc=assetdir/'spc.bin'
    if spc.exists() and spc.read_bytes()[0x408:0x40c]==bytes([0,10,0,10]):
        assert result.get('muted_sound_channels')==[3,4],'Use --music-only to audit the song independently of the added percussion'
    if pcm:
        original=np.fromfile(assetdir/f'adofai-{result["level"]}.pcm',dtype='<i2',offset=8).reshape(-1,2).mean(axis=1)
        source=resample_poly(original,RATE,44100)
    else:
        pack=json.loads((assetdir/'pack.json').read_text())
        fast=pack.get('fast_audio_rate') if result['speed_tenths']>10 else None
        suffix='-fast' if fast else ''
        source=decode_brr((assetdir/f'level{result["level"]}{suffix}.brr').read_bytes())
        if fast:source=resample_poly(source,RATE,fast)
    # The DSP's Gaussian interpolation attenuates high frequencies. Compare
    # the shared 0..2.5 kHz band rather than treating that filter as corruption.
    # Frontend channel mute isolates the song from the intentional added
    # percussion. The ROM, controller replay and DSP timing are unchanged.
    filt,low,band=music_filter(assetdir,pitch)
    source=sosfiltfilt(filt,source);a=sosfiltfilt(filt,a)
    rows=[];silent=[];past_end=[]
    for second in [2,5]+list(range(10,int(clock[-1]),10)):
        ref=source[second*RATE:second*RATE+RATE*2]
        if len(ref)!=RATE*2:
            past_end.append(second);continue
        # Below -60 dBFS, the DSP's integer volume/interpolation rounding
        # dominates normalized correlation. Report these quiet tail windows.
        if np.std(ref)<32:
            silent.append(second);continue
        expected=float(np.interp(second,clock,video))
        if second<clock[0]:expected=video[0]+(second-clock[0])*1536/pitch/apu_speed
        expected*=apu_speed*pitch/1536
        center=round(expected*RATE); radius=RATE//8
        candidate=a[center-radius:center+len(ref)+radius]
        r=correlate(candidate,ref,mode='valid',method='fft')
        sums=np.r_[0,np.cumsum(candidate*candidate)]
        energy=sums[len(ref):]-sums[:-len(ref)]
        scores=r/np.sqrt(np.maximum(energy*np.dot(ref,ref),1))
        peak=int(np.argmax(scores));lag=(peak-radius)/RATE*1536/pitch
        peaks=find_peaks(scores)[0]
        ambiguous=any(abs(int(p)-peak)>RATE*.008*pitch/1536 and scores[p]>scores[peak]-.001 for p in peaks)
        rows.append({'song_second':second,'correlation':round(float(scores[peak]),5),'offset_ms':round(lag*1000,3),'ambiguous_periodicity':ambiguous})
    unique=[x for x in rows if not x['ambiguous_periodicity']]
    assert len(unique)>=2,'Need at least two unambiguous waveform windows to measure drift'
    drift=unique[-1]['offset_ms']-unique[0]['offset_ms']
    report={'clock':'NTSC NMI' if pcm else 'SPC700 timer','reference':'MSU PCM' if pcm else 'decoded cartridge BRR','rom_sha256':result['rom_sha256'],'msu_sha256':result.get('msu_sha256'),'past_reference_end_windows':past_end,
            'comparison_band_hz':band,'comparison_low_hz':low,'muted_sound_channels':result.get('muted_sound_channels',[]),'comparison_window_seconds':2,'speed_pitch':pitch,'quiet_threshold_pcm_rms':32,'quiet_windows':silent,'windows':rows,'drift_ms':round(drift,3)}
    (folder/'audio-check.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))
    assert min(x['correlation'] for x in rows)>0.90,'Music mismatch, glitch, or stream underrun'
    assert abs(drift)<20,'Music/clock drift exceeds 20 ms'

if __name__=='__main__':main()
