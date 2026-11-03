"""Real-controller checks for signed offsets and calibration startup phase."""
import argparse,ctypes as C,json,math,wave
from pathlib import Path
import numpy as np
from emulate import Emulator,ROOT
from input_helpers import configure,press,wait


def entry_sound(base,route='menu',core=None):
    em=Emulator(rom=base/'adofai.sfc',core=core)
    try:
        for _ in range(120):em.run()
        if route in ('after-pcm','after-brr'):
            configure(em,20 if route=='after-brr' else 10)
            press(em,1)
            press(em,3)
            for _ in range(300):em.run()
            press(em,3);wait(em,lambda:em.read('state')==4,30)
            press(em,2);wait(em,lambda:em.read('state')==0,30)
        elif route=='options':
            press(em,0)
            for _ in range(5):press(em,5)
        elif route=='retry':
            press(em,2)
            for _ in range(60):em.run()
        em.audio.clear()
        press(em,8 if route=='options' else 3 if route=='retry' else 2)
        assert em.read('state')==5
        for _ in range(round(1.7*em.av.timing.fps)):em.run()
        pcm=np.frombuffer(b''.join(em.audio),dtype='<i2').reshape(-1,2).astype(float)
        active=np.flatnonzero(np.max(np.abs(pcm),axis=1)>500)
        assert len(active),('Silent calibration',route,em.snapshot())
        onsets=active[np.r_[True,np.diff(active)>em.av.timing.sample_rate*.2]]/em.av.timing.sample_rate
        assert len(onsets)>=4 and onsets[0]<.08,('No immediate/repeating click',route,onsets)
        assert np.max(np.abs(np.diff(onsets)-.5))<.008,(route,onsets)
        return dict(passed=True,route=route,core=Path(core).parent.name if core else 'Snes9x',
                    audible_clicks_seconds=onsets.tolist(),audible_peak=int(np.max(np.abs(pcm))),**em.evidence())
    finally:em.close()


def presentation(base):
    """Observe the emitted clicks and published video without supplying taps."""
    import hashlib
    from PIL import Image,ImageDraw
    out=base/'verification/calibration-presentation';out.mkdir(parents=True,exist_ok=True)
    em=Emulator(rom=base/'adofai.sfc')
    try:
        for _ in range(120):em.run()
        press(em,2)
        em.audio.clear();angles=[];images=[];pixels=set()
        for frame in range(round(1.8*em.av.timing.fps)):
            em.run();angles.append(em.read('angle'))
            assert em.read('state')==5 and em.read('cal_count')==0
            if frame<27 and frame%3==0:
                em.capture(out/'capture.png')
                im=Image.open(out/'capture.png').convert('RGB');images.append(im)
                pixels.add(hashlib.sha256(im.crop((88,64,168,144)).tobytes()).hexdigest())
        wraps=[(i+1)/em.av.timing.fps for i in range(1,len(angles)) if angles[i]<angles[i-1]-200]
        assert len(wraps)>=3 and len(pixels)>=8,('Frozen calibration visual',wraps,len(pixels))
        assert all(1<=(b-a)%256<=11 for a,b in zip(angles,angles[1:])), 'Calibration visual jumped'
        pcm=np.frombuffer(b''.join(em.audio),dtype='<i2').reshape(-1,2).astype(float)
        active=np.flatnonzero(np.max(np.abs(pcm),axis=1)>500)
        onsets=active[np.r_[True,np.diff(active)>em.av.timing.sample_rate*.2]]/em.av.timing.sample_rate
        assert len(onsets)>=3
        differences=[min(abs(t-v) for v in wraps) for t in onsets]
        assert max(differences)<2/em.av.timing.fps,('Visual target disagrees with click',onsets,wraps,differences)
        sheet=Image.new('RGB',(768,720));draw=ImageDraw.Draw(sheet)
        for j,im in enumerate(images):
            x=j%3*256;y=j//3*240
            sheet.paste(im,(x,y+16));draw.text((x+4,y+2),f'No input: frame {j*3}',fill='white')
        sheet.save(out/'samples.png');em.save_audio(out/'clicks.wav')
        return dict(passed=True,unique_visuals=len(pixels),visual_crossings_seconds=wraps,
                    audible_clicks_seconds=onsets.tolist(),maximum_alignment_error_seconds=max(differences),**em.evidence())
    finally:em.close()


def metronome(base,start,display,initial=0):
    em=Emulator(rom=base/'adofai.sfc')
    try:
        for _ in range(120):em.run()
        if initial:configure(em,calibration=initial)
        press(em,2)
        assert em.read('state')==5
        period=125;bias=round((display+8)/em.av.timing.fps/.004)
        beat=start;count=0;errors=[];polls=[]
        audio_start=em.frames
        em.audio.clear()
        for _ in range(round((start+18)*.5*em.av.timing.fps)):
            # Predict the next input poll from the SPC clock, rather than
            # waiting to observe a tick and then pressing one frame late.
            now=em.read('nmi_audio_ticks')
            target=beat*period+bias
            buttons=[]
            if count<16 and now+1/(em.av.timing.fps*.004)>=target:
                buttons=[8];polls.append(dict(target=target,before=now));beat+=1
            em.run(buttons)
            new=em.read('cal_count')
            if new>count:
                assert new==count+1,(new,count)
                errors.append(em.read('cal_error',True));count=new
            if em.read('state')==6:break
        assert count==16 and len(polls)==16,(count,polls,em.snapshot())
        result=em.read('cal_recommend',True)
        assert abs(result-display)<=1,(start,display,result,errors)
        # Measure emitted click onsets, including the first click. This
        # catches a startup clock which disagrees with later beats.
        pcm=np.frombuffer(b''.join(em.audio),dtype='<i2').reshape(-1,2).astype(float)
        energy=np.max(np.abs(pcm),axis=1);active=np.flatnonzero(energy>500)
        onsets=active[np.r_[True,np.diff(active)>em.av.timing.sample_rate*.2]]
        times=onsets/em.av.timing.sample_rate
        intervals=np.diff(times)
        assert len(intervals)>=14 and np.max(np.abs(intervals-.5))<.008,(start,times.tolist())
        return dict(start_beat=start,initial_offset=initial,requested=display,recommended=result,taps=count,
                    tap_error_ticks=errors,click_intervals_seconds=intervals.tolist(),
                    first_click_seconds=float(times[0]),**em.evidence())
    finally:em.close()


def gameplay(base,display,speed):
    first=json.loads((base/'pack.json').read_text())['levels'][0]
    chart=json.loads((base/f'level{first}.json').read_text())
    notes=[n for n in chart['notes'][1:] if not n['flags']&8]
    em=Emulator(rom=base/'adofai.sfc')
    try:
        for _ in range(120):em.run()
        configure(em,speed,calibration=display)
        pitch=em.read('speed_pitch');playback=pitch/1536
        expected=(display+8)*playback
        actual=em.read('speed_offset',True)+em.read('speed_offset_frac')/65536
        assert abs(actual-expected)<1/65536,(display,speed,expected,actual)
        press(em,3);next_note=0;first=None;first_poll=None
        for frame in range(math.ceil((chart['duration']/playback+3)*em.av.timing.fps)):
            buttons=[]
            if em.read('state')==1:
                delta=((em.read('nmi_audio_ticks')-em.read('audio_ticks')+32768)&65535)-32768
                current=em.read('elapsed')+delta*.004*em.av.timing.fps*playback
                # Use the independently calculated offset, never the ROM's
                # own offset to generate its test input.
                if next_note<len(notes) and current+1>=notes[next_note]['frame']+expected:
                    buttons=[8 if next_note%2==0 else 0];next_note+=1
            before=em.read('combo');em.run(buttons)
            if buttons and first_poll is None:
                # Judge the NMI-captured input time, not the later CPU frame
                # that consumes it while a dense graphics batch is staged.
                import ctypes as C
                index=(em.read('tap_head')-2)&255
                stamp=C.c_uint16.from_address(em.ram+em.labels['tap_stamps']+index).value
                delta=((stamp-em.read('audio_ticks')+32768)&65535)-32768
                first_poll=(em.read('clock_song_frames')+em.read('clock_song_frac')/65536+
                            em.read('music_origin')+delta*.004*em.av.timing.fps*playback)
            if first is None and em.read('combo')>before:
                first=dict(elapsed=em.read('elapsed'),chart_time=em.read('chart_time'),target=notes[0]['frame'])
            if em.read('state') in (2,3):break
        final=em.snapshot()
        assert final['state']==3 and final['combo']==chart['hits'] and final['misses']==0,final
        assert final['tap_overruns']==0
        assert abs(first_poll-first['target']-expected)<4,(display,speed,first,first_poll,expected)
        first['input_frame']=first_poll
        return dict(display=display,speed=speed/10,effective_offset=actual,first_hit=first,combo=final['combo'],**em.evidence())
    finally:em.close()


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--pack',default='master');args=ap.parse_args()
    base=ROOT/'build/packs'/args.pack
    visual=presentation(base)
    entries=[entry_sound(base,route) for route in ('menu','options','after-pcm','after-brr','retry')]
    clicks=[metronome(base,start,display,initial=-28 if display==-30 else 28 if display==30 else 0) for display in (-30,-9,0,30)
            for start in (0,1,4,8) if start>0 or display>=0]
    for display in (-30,-9,0,30):
        values=[r['recommended'] for r in clicks if r['requested']==display]
        assert max(values)-min(values)<=1,(display,values)
    plays=[gameplay(base,display,speed) for speed in (5,10,20) for display in (-30,-9,-1,0,30)]
    report=dict(passed=True,core='Snes9x',presentation=visual,entry_sounds=entries,metronome=clicks,gameplay=plays,
                rom_sha256=clicks[0]['rom_sha256'],msu_sha256=clicks[0]['msu_sha256'])
    path=base/'verification/calibration.json';path.parent.mkdir(exist_ok=True,parents=True)
    path.write_text(json.dumps(report,indent=2))
    print('PASS: first/later clicks agree, all 16 taps counted, signed offsets at 0.5x/1.0x/2.0x',flush=True)


if __name__=='__main__':main()
