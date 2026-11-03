"""Check a complete, unmuted emulator capture for exhausted mixer headroom."""
import argparse,json,wave
from pathlib import Path
import numpy as np
from verification_data import identity,file_sha256

def check(folder,pcm=False):
    folder=Path(folder)
    result=json.loads((folder/'result.json').read_text())
    current=identity(Path(result['asset_directory'])/'adofai.sfc')
    assert all(result[k]==v for k,v in current.items()),'Capture belongs to another build'
    assert result['muted_sound_channels']==[],'Capture must include percussion'
    assert result['final']['state']==3 and result['final']['misses']==0
    path=folder/'audio.wav'
    with wave.open(str(path)) as wav:
        assert wav.getsampwidth()==2
        samples=np.frombuffer(wav.readframes(wav.getnframes()),dtype='<i2')
    # The SPC master volume of 127 maps DSP saturation to these endpoints.
    # The external PCM mixer saturates at the host's signed 16-bit endpoints.
    low,high=(-32768,32767) if pcm else (-32512,32511)
    count=int(np.count_nonzero((samples<=low)|(samples>=high)))
    report=dict(**current,code=result['code'],speed=result['speed_tenths']/10,
        mixer='PCM + SPC' if pcm else 'SPC',audio_sha256=file_sha256(path),
        minimum=int(samples.min()),maximum=int(samples.max()),clipped_samples=count,
        samples=len(samples),passed=count==0)
    (folder/'mix-headroom.json').write_text(json.dumps(report,indent=2))
    print(report)
    assert report['passed'],'Mixed playback exhausts headroom'
    return report

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('folder',type=Path);ap.add_argument('--pcm',action='store_true')
    args=ap.parse_args();check(args.folder,args.pcm)
