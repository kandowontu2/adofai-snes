"""Die and retry at every original checkpoint using real controller input."""
import argparse,ctypes as C,hashlib,json
from pathlib import Path
import numpy as np
from scipy.signal import butter,correlate,resample_poly,sosfiltfilt
from emulate import Emulator,ROOT
from campaign_assets import FPS,RATE
from check_campaign_audio import decode_brr
from official_catalog import PACKS
from input_helpers import verify_checkpoint_results,configure

def shared_audio_peaks(curves,playback=1):
    """Resolve repeated tones using one measured lag across all windows."""
    from scipy.ndimage import maximum_filter1d
    radius=round(.004*RATE*playback)
    # The timer is quantized. Find a common interval, not identical sample
    # phase: pointwise averaging can cancel otherwise matching waveforms.
    envelopes=[maximum_filter1d(scores,2*radius+1,mode='constant',cval=-1) for scores in curves]
    anchor=int(np.argmax(np.min(envelopes,axis=0)))
    return [max(0,anchor-radius)+int(np.argmax(scores[max(0,anchor-radius):anchor+radius+1])) for scores in curves]

def verify(pack,local,speed=10):
    base=ROOT/'build/campaign' if pack=='main' else ROOT/f'build/packs/{pack}'
    n=json.loads((base/'pack.json').read_text())['levels'][local-1];chart=json.loads((base/f'level{n}.json').read_text())
    if not chart['checkpoints']:return None
    out=base/(f'verification/checkpoints-{local}'+(f'-speed-{speed}' if speed!=10 else ''));out.mkdir(parents=True,exist_ok=True)
    em=Emulator(rom=base/'adofai.sfc',mute_taps=True);tests=[];fresh_clock=[];index=0;stage='reach';death_at=0;next_tap=1;tap_serial=0;retry_captured=False
    try:
        # Isolate music from the separately verified checkpoint hi-hat voice.
        em.frontend_values.update({b'snes9x_sndchan_5':b'disabled',b'snes9x_sndchan_volume_5':b'0'})
        em.options_dirty=True
        for _ in range(120):em.run()
        if speed!=10:configure(em,speed)
        playback=em.read('speed_pitch')/1536
        for _ in range(local-1):em.run([5]);em.run()
        em.run([3])
        for frame in range(round(chart['duration']*FPS)+len(chart['checkpoints'])*700+1500):
            state=em.read('state');step=em.read('step');buttons=[]
            cp=chart['checkpoints'][index] if index<len(chart['checkpoints']) else None
            if state==1:
                if stage=='reach' and cp and em.read('checkpoint_floor')==cp['floor'] and step>=cp['trigger']:
                    stage='die'
                if stage!='die' and not em.read('checkpoint_preroll'):
                    while next_tap<=chart['steps'] and chart['notes'][next_tap]['flags']&8:next_tap+=1
                    if next_tap<=chart['steps']:
                        target=chart['notes'][next_tap]['frame']+em.read('speed_offset',True)
                        delta=((em.read('nmi_audio_ticks')-em.read('audio_ticks')+32768)&65535)-32768
                        current=em.read('elapsed')+delta*.004*FPS*playback
                        pool=[8,9,10,4,6] if frame%2==0 else [0,1,11,5,7]
                        while next_tap<=chart['steps'] and chart['notes'][next_tap]['frame']+em.read('speed_offset',True)<=current+1 and len(buttons)<len(pool):
                            if not(chart['notes'][next_tap]['flags']&8):buttons.append(pool[len(buttons)]);tap_serial+=1
                            next_tap+=1
            elif state==2:
                if stage=='die' and em.read('display_state')==2:
                    death_at=em.frames;stage='frozen'
                    frozen=(em.read('cam_x'),em.read('cam_y'),em.read('angle'),em.read('chart_time'))
                elif stage=='frozen' and em.frames-death_at>=4:
                    current=(em.read('cam_x'),em.read('cam_y'),em.read('angle'),em.read('chart_time'))
                    assert current==frozen,('Death scene moved',current,frozen)
                    # The PPU still shows BG1, with the actual death-step planets.
                    assert em.read('display_state')==2
                    oam=np.frombuffer(C.string_at(em.ram+0x200,12),dtype=np.uint8).reshape(3,4)
                    if chart.get('mode7'):
                        assert all(t in (6,64,65,66,67) for t in oam[:2,2]),oam
                        objects=np.frombuffer(C.string_at(em.ram+0x200,512),dtype=np.uint8).reshape(128,4)
                        assert not np.any((objects[:,2]==8)&((objects[:,3]&14)==4)&(objects[:,1]<224)),objects
                    else:assert list(oam[:,2])==[6,6,8],oam
                    if index==0:em.capture(out/'death.png')
                    buttons=[3];stage='retry'
            elif state==3:break
            em.run(buttons)
            if stage=='retry' and em.read('state')==1:
                assert em.read('step')==cp['floor'],(cp,em.snapshot())
                assert em.read('music_origin')==cp['origin_frame']
                assert em.read('checkpoint_preroll')==1
                assert em.read('checkpoints_used')==index+1
                assert em.read('combo')==0 and em.read('misses')==0
                tests.append(dict(**cp,start_frame=em.frames,clock=[],end_frame=None))
                index+=1;stage='reach';next_tap=cp['floor']+1
            if tests and not retry_captured and em.read('display_state')==1 and em.read('music_active') and em.read('elapsed')>tests[0]['origin_frame']+5:
                em.capture(out/'retry.png');retry_captured=True
            if tests and tests[-1]['trigger']==tests[-1]['floor']+1 and em.read('frame_ready') and em.read('display_state')==1 and em.read('checkpoint_preroll') and em.read('music_active') and em.read('elapsed')>tests[-1]['origin_frame']+5:
                oam=np.frombuffer(C.string_at(em.ram+0x200,512),dtype=np.uint8).reshape(128,4)
                alpha=3
                if chart.get('visibility_floor_versions'):
                    for when,value in chart['visibility_floor_versions'][tests[-1]['trigger']]:
                        if when>em.read('chart_time'):break
                        alpha=value
                assert em.read('checkpoint_record')>0,('Activated checkpoint state lost',tests[-1])
                trigger=tests[-1]['trigger']
                nx=C.c_uint16.from_address(em.ram+0x2000+trigger*2).value
                ny=C.c_uint16.from_address(em.ram+(0x3800 if 'msu_pcm' in em.labels else 0x3000)+trigger*2).value
                dx=(nx-em.read('cam_x')+32768)%65536-32768
                dy=(ny-em.read('cam_y')+32768)%65536-32768
                if chart.get('mode7'):
                    scale=em.read('camera_inverse',True)/256
                    if em.sa1:
                        cosine=C.c_int16.from_address(em.cache_ram+0x1fcb0).value/256
                        sine=C.c_int16.from_address(em.cache_ram+0x1fcb2).value/256
                        dx,dy=128+(dx-128)*cosine-(dy-96)*sine-8,96+(dx-128)*sine+(dy-96)*cosine-8
                    else:dx=128+(dx-128)*scale-8;dy=96+(dy-96)*scale-8
                # Duplicate flags may target the same restart floor. The
                # original engine keeps the earlier active checkpoint record.
                record=em.read('checkpoint_record')-1
                active_trigger=C.c_uint16.from_address(em.ram+(0x1d800 if 'msu_pcm' in em.labels else 0x9000)+record).value
                if active_trigger==trigger and alpha and not(chart['notes'][trigger]['flags']&128) and 0<=dx<240 and 32<=dy<176:
                    assert np.any((oam[:,2]==76)&(oam[:,1]<192)),('Visible activated flag lost on rewind',tests[-1],
                        dict(dx=dx,dy=dy,flags=chart['notes'][trigger]['flags'],step=em.read('step'),chart_time=em.read('chart_time'),
                             alpha=alpha,active_oam=oam[oam[:,1]<224].tolist()))
            if not tests and em.read('state')==1 and em.read('music_active') and frame%10==0:
                pcm='msu_pcm' in em.labels and em.read('msu_pcm')
                fresh_clock.append((em.read('msu_elapsed_frames')/FPS if pcm else em.read('nmi_audio_ticks')*.004*playback,em.frames/FPS*playback))
            if tests and tests[-1]['end_frame'] is None:
                if em.read('state')==2:tests[-1]['end_frame']=em.frames
                elif em.read('state') in (1,3) and frame%10==0:
                    # Use the input-poll clock, not the last completed main
                    # update, which may be older during animated rendering.
                    pcm='msu_pcm' in em.labels and em.read('msu_pcm')
                    song_clock=em.read('msu_elapsed_frames')/FPS if pcm else em.read('nmi_audio_ticks')*.004*playback
                    tests[-1]['clock'].append((em.read('music_origin')/FPS+song_clock,em.frames/FPS*playback))
        assert index==len(chart['checkpoints']),(chart['code'],'Untested checkpoint',index,em.snapshot())
        assert em.read('state')==3,(chart['code'],'Resume failed',em.snapshot())
        counts=[C.c_uint16.from_address(em.ram+em.labels['judgment_counts']+2*i).value for i in range(11)]
        skipped=sum(sum(not(n['flags']&8) for n in chart['notes'][c['trigger']+1:c['floor']+1]) for c in chart['checkpoints'] if c['floor']>c['trigger'])
        assert sum(counts)==chart['hits']-skipped,('Checkpoint score rollback',chart['code'],counts,chart['hits'],skipped)
        tests[-1]['end_frame']=em.frames
        audio=np.frombuffer(b''.join(em.audio),dtype='<i2').reshape(-1,2).mean(axis=1)
        pcm='msu_pcm' in em.labels and em.read('msu_pcm')
        audio=resample_poly(audio,RATE,round(em.av.timing.sample_rate) if pcm else 32000)
        if playback!=1:audio=resample_poly(audio,em.read('speed_pitch'),1536)
        if pcm:
            original=np.fromfile(base/f'adofai-{n}.pcm',dtype='<i2',offset=8).reshape(-1,2).mean(axis=1)
            source=resample_poly(original,RATE,44100)
        else:
            fast=json.loads((base/'pack.json').read_text()).get('fast_audio_rate') if speed>10 else None
            suffix='-fast' if fast else ''
            source=decode_brr((base/f'level{n}{suffix}.brr').read_bytes())
            if fast:source=resample_poly(source,RATE,fast)
        filt=butter(4,2500,fs=RATE,output='sos');source=sosfiltfilt(filt,source);audio=sosfiltfilt(filt,audio)
        # Use a fresh start in this same ROM/core as the latency reference.
        # Libretro delivers queued audio blocks after the emulated PCM write;
        # that constant mixer latency belongs in calibration, not in retry's
        # song clock. A retry must not introduce an additional frame of lag.
        fresh=np.array(fresh_clock);fresh_curves=[];radius=RATE//8
        for delta in (.35,1.2,2.,5.3):
            if len(fresh)<2 or delta+.2>fresh[-1,0]:continue
            ref=source[round(delta*RATE):round(delta*RATE)+RATE//5]
            if np.std(ref)<32:continue
            expected=np.interp(delta,fresh[:,0],fresh[:,1])*(1 if pcm else em.av.timing.sample_rate/32000)
            center=round(expected*RATE);candidate=audio[center-radius:center+len(ref)+radius]
            corr=correlate(candidate,ref,mode='valid',method='fft')
            sums=np.r_[0,np.cumsum(candidate*candidate)];energy=sums[len(ref):]-sums[:-len(ref)]
            fresh_curves.append(corr/np.sqrt(np.maximum(energy*np.dot(ref,ref),1)))
        assert fresh_curves,('No fresh-start audio reference',chart['code'])
        fresh_peaks=shared_audio_peaks(fresh_curves,playback)
        assert min(scores[peak] for scores,peak in zip(fresh_curves,fresh_peaks))>.9
        fresh_latency=float(np.median([(p-radius)*1000/(RATE*playback) for p in fresh_peaks]))
        for test in tests:
            clock=np.array(test.pop('clock'));windows=[];curves=[]
            for delta in (.35,1.2,5.3):
                if len(clock)<2 or test['origin_frame']/FPS+delta+.2>clock[-1,0]:continue
                ref_start=test['block']*16+round(delta*RATE);ref=source[ref_start:ref_start+RATE//5]
                if np.std(ref)<32:continue
                # Checkpoint music ramps to full volume over 56 chart
                # frames, or jumps to full volume when the lead-in ends.
                # Compare the same envelope: an unfaded short reference can
                # correlate more strongly with a later repetition of a tone.
                fade_frames=(delta+np.arange(len(ref))/RATE)*FPS
                gain=np.minimum(fade_frames/56,1)
                # Preroll ends on corrected chart time, whereas the volume
                # ramp follows raw song time. Include the displayed offset
                # baseline when the short lead-in ends before the ramp.
                raw_ready=test['ready_frame']-test['origin_frame']+em.read('speed_offset',True)
                gain[fade_frames>=raw_ready]=1
                ref=ref*gain
                expected=np.interp(test['origin_frame']/FPS+delta,clock[:,0],clock[:,1])*(1 if pcm else em.av.timing.sample_rate/32000)
                center=round(expected*RATE);radius=RATE//8
                candidate=audio[center-radius:center+len(ref)+radius]
                corr=correlate(candidate,ref,mode='valid',method='fft')
                sums=np.r_[0,np.cumsum(candidate*candidate)];energy=sums[len(ref):]-sums[:-len(ref)]
                scores=corr/np.sqrt(np.maximum(energy*np.dot(ref,ref),1));curves.append(scores)
                windows.append(dict(after_restart_seconds=delta,reference_fade_frames=56))
            for window,scores,peak in zip(windows,curves,shared_audio_peaks(curves,playback) if curves else []):
                window.update(correlation=round(float(scores[peak]),5),offset_ms=round((peak-radius)*1000/(RATE*playback),3),
                              independent_peak_offset_ms=round((int(np.argmax(scores))-radius)*1000/(RATE*playback),3),shared_alignment=True)
            test['audio_windows']=windows
            assert windows,(chart['code'],'No audible checkpoint window',test)
            assert min(w['correlation'] for w in windows)>.9,(chart['code'],'Checkpoint audio mismatch',test)
            test['fresh_start_latency_ms']=round(fresh_latency,3)
            for w in windows:w['retry_added_offset_ms']=round(w['offset_ms']-fresh_latency,3)
            if pcm:
                assert max(abs(w['retry_added_offset_ms']) for w in windows)<10,(chart['code'],'Retry changed calibrated audio alignment',test)
            else:assert max(abs(w['offset_ms']) for w in windows)<30,(chart['code'],'Checkpoint beat offset',test)
        checkpoint_text=verify_checkpoint_results(em)
        result=dict(code=chart['code'],speed=speed/10,**em.evidence(),
                    checkpoints=tests,final=em.snapshot(),death_scene_frozen=True,judgments=counts,
                    checkpoints_used=em.read('checkpoints_used'),checkpoint_results_text=checkpoint_text)
        (out/'result.json').write_text(json.dumps(result,indent=2));em.capture(out/'clear.png')
        print(chart['code'],'PASS',len(tests),'checkpoint retries',flush=True)
        return result
    finally:em.close()

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--packs',nargs='+',default=list(PACKS));ap.add_argument('--levels',type=int,nargs='+');ap.add_argument('--speed',type=float,default=1.);args=ap.parse_args()
    for pack in args.packs:
        base=ROOT/'build/campaign' if pack=='main' else ROOT/f'build/packs/{pack}'
        levels=json.loads((base/'pack.json').read_text())['levels']
        for local in args.levels or range(1,len(levels)+1):verify(pack,local,round(args.speed*10))
if __name__=='__main__':main()
