"""Isolate the checkpoint hi-hats and check their musical-clock spacing."""
import argparse,ctypes as C,json
import numpy as np
from scipy.signal import find_peaks
from emulate import Emulator,ROOT
from input_helpers import configure,press,wait

def run(base,speed,muted):
    em=Emulator(rom=base/'adofai.sfc')
    try:
        if muted:
            em.frontend_values.update({b'snes9x_sndchan_5':b'disabled',b'snes9x_sndchan_volume_5':b'0'})
            em.options_dirty=True
        for _ in range(120):em.run()
        configure(em,speed)
        levels=json.loads((base/'pack.json').read_text())['levels']
        level=next(i for i,n in enumerate(levels) if json.loads((base/f'level{n}.json').read_text())['checkpoints'])
        for _ in range(level):press(em,5)
        press(em,1);press(em,3)
        wait(em,lambda:em.read('checkpoint_floor')>0,20000)
        # Reach the checkpoint in autoplay, then deliberately stop tapping.
        C.c_uint16.from_address(em.ram+em.labels['autoplay']).value=0
        wait(em,lambda:em.read('state')==2,2000)
        press(em,3);wait(em,lambda:em.read('state')==1)
        em.audio.clear();events=[];left=em.read('checkpoint_clicks_left')
        assert left==4,(left,em.snapshot())
        target=em.read('checkpoint_click_next');beat=em.read('checkpoint_beat')
        for _ in range(1000):
            em.run()
            new=em.read('checkpoint_clicks_left')
            if new!=left:
                assert new==left-1
                events.append(em.read('checkpoint_click_next')-beat);left=new
            if len(events)==4:
                for _ in range(12):em.run()
                break
        assert len(events)==4,(events,em.snapshot())
        assert all(0<=time-(target+i*beat)<=4 for i,time in enumerate(events)),(events,target,beat)
        pcm=np.frombuffer(b''.join(em.audio),dtype='<i2').astype(float)
        return pcm,dict(events=events,target=target,beat=beat,sample_rate=em.av.timing.sample_rate,**em.evidence())
    finally:em.close()

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--pack',default='sa1-behavior-test');args=ap.parse_args()
    base=ROOT/'build/packs'/args.pack;rows=[]
    for speed in (10,20):
        audible,a=run(base,speed,False);silent,b=run(base,speed,True)
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
        assert np.max(np.abs(np.diff(onsets)-expected))<.05,(speed,onsets,expected)
        a['audible_onsets_seconds']=onsets.tolist()
        rows.append(dict(speed=speed/10,isolated_hat_peak=peak,**a))
    (base/'verification/checkpoint-countdown.json').write_text(json.dumps(dict(passed=True,cases=rows),indent=2))
    print('PASS: four audible checkpoint hi-hats at 1x and 2x, unchanged music/gameplay clocks')

if __name__=='__main__':main()
