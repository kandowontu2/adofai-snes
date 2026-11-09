"""Isolate the checkpoint hi-hats and check their musical-clock spacing."""
import argparse,ctypes as C,json
import numpy as np
from scipy.signal import find_peaks
from emulate import Emulator,ROOT
from input_helpers import configure,press,wait

def run(base,speed,muted,level_id=None):
    em=Emulator(rom=base/'adofai.sfc')
    try:
        if muted:
            em.frontend_values.update({b'snes9x_sndchan_5':b'disabled',b'snes9x_sndchan_volume_5':b'0'})
            em.options_dirty=True
        for _ in range(120):em.run()
        configure(em,speed)
        levels=json.loads((base/'pack.json').read_text())['levels']
        level=levels.index(level_id) if level_id is not None else next(i for i,n in enumerate(levels) if json.loads((base/f'level{n}.json').read_text())['checkpoints'])
        for _ in range(level):press(em,5)
        press(em,1);press(em,3)
        wait(em,lambda:em.read('checkpoint_floor')>0,20000)
        # Reach the checkpoint in autoplay, then deliberately stop tapping.
        C.c_uint16.from_address(em.ram+em.labels['autoplay']).value=0
        wait(em,lambda:em.read('state')==2,2000)
        press(em,3);wait(em,lambda:em.read('state')==1)
        pcm_active=bool(em.read('msu_pcm')) if 'msu_pcm' in em.labels else False
        expected_pcm=speed==10 and (base/f'adofai-{1000+levels[level]*32}.pcm').exists()
        assert pcm_active==expected_pcm,('Wrong audio backend',levels[level],speed,pcm_active,expected_pcm)
        em.audio.clear();events=[];volumes=[];left=em.read('checkpoint_clicks_left')
        assert left==4,(left,em.snapshot())
        target=em.read('checkpoint_click_next');beat=em.read('checkpoint_beat')
        for _ in range(1000):
            em.run()
            if em.read('checkpoint_preroll') and 'msu_volume' in em.labels:
                volumes.append(em.read('msu_volume'))
            new=em.read('checkpoint_clicks_left')
            if new!=left:
                assert new==left-1
                events.append(em.read('checkpoint_click_next')-beat);left=new
            if len(events)==4:
                for _ in range(12):em.run()
                break
        assert len(events)==4,(events,em.snapshot())
        assert all(0<=time-(target+i*beat)<=4 for i,time in enumerate(events)),(events,target,beat)
        assert not volumes or max(volumes)<=56,('Backing music was not ducked',volumes)
        pcm=np.frombuffer(b''.join(em.audio),dtype='<i2').astype(float)
        return pcm,dict(level=levels[level],pcm_active=pcm_active,countin_volume_max=max(volumes,default=0),events=events,target=target,beat=beat,sample_rate=em.av.timing.sample_rate,**em.evidence())
    finally:em.close()

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--pack',default='sa1-behavior-test')
    ap.add_argument('--levels',type=int,nargs='+');args=ap.parse_args()
    base=ROOT/'build/packs'/args.pack;rows=[]
    (base/'verification').mkdir(exist_ok=True)
    for level,speed in ((level,speed) for level in (args.levels or [None]) for speed in (10,20)):
        audible,a=run(base,speed,False,level);silent,b=run(base,speed,True,level)
        assert a['events']==b['events'] and audible.shape==silent.shape
        diff=audible-silent
        peak=float(np.max(np.abs(diff)))
        assert peak>500,('Hi-hat is inaudible',speed,peak)
        energy=np.max(np.abs(diff.reshape(-1,2)),axis=1)
        window=max(1,round(a['sample_rate']*.005))
        envelope=np.convolve(energy,np.ones(window)/window,mode='same')
        expected=a['beat']/60.0988*10/speed
        peaks,_=find_peaks(envelope,height=np.max(envelope)*.5,distance=round(a['sample_rate']*expected*.7),prominence=np.max(envelope)*.3)
        onsets=peaks/a['sample_rate']
        assert len(onsets)==4,('Wrong number of audible clicks',speed,onsets)
        assert np.max(np.abs(np.diff(onsets)-expected))<.012,(speed,onsets,expected)
        a['audible_onsets_seconds']=onsets.tolist()
        rows.append(dict(speed=speed/10,isolated_hat_peak=peak,**a))
        print(f'PASS: level {a["level"]}, {speed/10:g}x, four audible clicks',flush=True)
    (base/'verification/checkpoint-countdown.json').write_text(json.dumps(dict(passed=True,cases=rows),indent=2))
    print('PASS: four audible checkpoint hi-hats at 1x and 2x, unchanged music/gameplay clocks')

if __name__=='__main__':main()
