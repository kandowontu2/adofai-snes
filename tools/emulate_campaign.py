"""Replay official-world cartridge packs with real pad input."""
import argparse
import ctypes as C
import hashlib
import json
from pathlib import Path
from emulate import Emulator,ROOT
from input_helpers import configure,verify_checkpoint_results

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--level',type=int,default=1)
    ap.add_argument('--pack',default='main')
    ap.add_argument('--mode',choices=['boot','perfect','watch','practice','calibration'],default='watch')
    ap.add_argument('--frames',type=int);ap.add_argument('--audio',action='store_true');ap.add_argument('--out',type=Path)
    ap.add_argument('--bias-ticks',type=int,default=0)
    ap.add_argument('--calibration',type=int,choices=range(-30,31))
    ap.add_argument('--trace-audio',action='store_true')
    ap.add_argument('--music-only',action='store_true',help='Mute percussion voices in the emulator for independent song transport analysis')
    ap.add_argument('--speed',type=float,default=1.0);ap.add_argument('--time-attack',action='store_true')
    ap.add_argument('--fire-color',type=int);ap.add_argument('--ice-color',type=int)
    args=ap.parse_args();base=ROOT/'build/campaign' if args.pack=='main' else ROOT/f'build/packs/{args.pack}'
    speed=round(args.speed*10);assert 5<=speed<=20 and abs(args.speed*10-speed)<1e-6
    pack=json.loads((base/'pack.json').read_text());global_level=pack['levels'][args.level-1]
    out=args.out or base/f'verification/{args.mode}-{args.level}';out.mkdir(exist_ok=True,parents=True)
    chart=json.loads((base/f'level{global_level}.json').read_text())
    em=Emulator(rom=base/'adofai.sfc',mute_taps=args.music_only);trace=[];audio_trace=[];prior=None;cal_last=-1;next_input=0
    manual_notes=[n for n in chart['notes'][1:] if not(n['flags']&8)]
    try:
        for _ in range(120):em.run()
        if speed!=10 or args.time_attack or args.fire_color is not None or args.ice_color is not None or args.calibration is not None:
            configure(em,speed,args.time_attack,args.fire_color,args.ice_color,args.calibration)
        for _ in range(args.level-1):em.run([5]);em.run()
        em.capture(out/'title.png')
        if args.mode in ('watch','practice'):
            em.run([1 if args.mode=='watch' else 9]);em.run()
        if args.mode!='boot':em.run([2 if args.mode=='calibration' else 3])
        audio_frame_offset=em.frames
        playback=em.read('speed_pitch')/1536
        report_fps=em.av.timing.fps
        frames=args.frames or (2100 if args.mode=='calibration' else round(chart['duration']*chart.get('fps',60.0988118623)/playback)+360)
        for frame in range(frames):
            s=em.snapshot();buttons=[]
            if args.mode=='perfect' and s['state']==1:
                # Follow the musical clock, independently of how many queued
                # taps the renderer has processed. A real player can press
                # the next beat while the previous frame is still rendering.
                delta=((s['nmi_audio_ticks']-s['audio_ticks']+32768)&65535)-32768
                current=s['elapsed']+delta*.004*report_fps*playback
                pool=[8,9,10,4,6] if frame%2==0 else [0,1,11,5,7]
                while next_input<len(manual_notes) and manual_notes[next_input]['frame']+em.read('speed_offset',True)<=current+1 and len(buttons)<len(pool):
                    buttons.append(pool[len(buttons)]);next_input+=1
            if args.mode=='calibration' and s['state']==5:
                period=125
                ticks=s['audio_ticks'];nearest=(ticks-args.bias_ticks)//period
                phase=(ticks-args.bias_ticks)%period
                if ticks>=500 and phase<5 and nearest!=cal_last:
                    buttons=[8];cal_last=nearest
            em.run(buttons);now=em.snapshot();key=(now['state'],now['step'],now.get('cal_count'),now['music_active'])
            if args.trace_audio:
                audio_trace.append(dict(frame=frame,**{k:em.read(k) for k in ('nmi_audio_ticks','stream_ticks','audio_pending_packets','msu_data_busy','apu_busy')},
                                        produced=C.c_uint32.from_address(em.ram+em.labels['msu_stream_cursor']).value))
            if key!=prior or (frame%60==0 and now['music_active']):trace.append({'frame':frame,**now});prior=key
            if frame in (30,120,500,1200,2400,3600,5000,frames-1):em.capture(out/f'frame-{frame:05}.png')
            if frame%2000==0:print(frame,now,flush=True)
        checkpoint_text=None
        if em.read('state')==3 and not any(em.read(k) for k in ('autoplay','practice','time_attack')):
            checkpoint_text=verify_checkpoint_results(em)
        em.capture(out/'final.png')
        report={'level':global_level,'pack':args.pack,'local_level':args.level,'code':chart['code'],'asset_directory':str(base),
                'mode':args.mode,'final':em.snapshot(),'transitions':trace,
                **em.evidence(),
                'audio_frame_offset':audio_frame_offset,
                'fps':em.av.timing.fps,'sample_rate':em.av.timing.sample_rate,
                'speed_tenths':speed,'speed_pitch':em.read('speed_pitch'),'time_attack':bool(em.read('time_attack')),
                'calibration':em.read('calibration',True),'effective_offset':em.read('speed_offset',True)+em.read('speed_offset_frac')/65536,
                'judgments':[C.c_uint16.from_address(em.ram+em.labels['judgment_counts']+i*2).value for i in range(11)],
                'score':em.read('score_lo')+65536*em.read('score_hi'),'finish_centis':em.read('finish_cs'),
                'checkpoints_used':em.read('checkpoints_used'),'checkpoint_results_text':checkpoint_text}
        (out/'result.json').write_text(json.dumps(report,indent=2))
        if args.trace_audio:(out/'audio-trace.json').write_text(json.dumps(audio_trace))
        if args.audio:em.save_audio(out/'audio.wav')
        print('FINAL',report['final'],flush=True)
        if not args.frames and args.mode in ('perfect','watch','practice'):
            final=report['final'];assert final['state']==3 and final['step']==chart['steps'],final
            hits=chart.get('hits',chart['steps'])
            if args.mode=='practice':assert final['misses']==hits,final
            else:assert final['combo']==hits and final['misses']==0,final
    finally:em.close()
if __name__=='__main__':main()
