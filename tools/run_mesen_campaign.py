"""Replay official cartridge packs in the independent Mesen SNES core."""
import argparse,json,os,re,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
import hashlib,sys
sys.path.insert(0,str(ROOT/'tools'))
from official_catalog import PACKS
from verification_data import identity

def suite_digest():
    paths=sorted((ROOT/'tools').glob('verify*mesen.lua'))+[ROOT/'tools/mesen_failfast.lua',ROOT/'tools/run_mesen_campaign.py',ROOT/'tools/run_mesen_sequence.py']
    return hashlib.sha256(b''.join(p.name.encode()+p.read_bytes() for p in paths)).hexdigest()
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--mesen',type=Path,default=Path(r'C:\mesen2\Mesen.exe'))
    ap.add_argument('--prepare-only',action='store_true');ap.add_argument('--levels',type=int,nargs='+');ap.add_argument('--pack',default='main');ap.add_argument('--all',action='store_true');ap.add_argument('--checkpoints',action='store_true')
    ap.add_argument('--speed',type=float,default=1.0);ap.add_argument('--time-attack',action='store_true');ap.add_argument('--resume',action='store_true')
    ap.add_argument('--trace-frame',type=int);ap.add_argument('--graphics-dumps',action='store_true');ap.add_argument('--capture-steps',type=int,nargs='+');ap.add_argument('--capture-times',type=int,nargs='+',help='Also verify PPU output at these presented chart-clock frames');ap.add_argument('--autoplay',action='store_true');args=ap.parse_args()
    speed=round(args.speed*10);assert 5<=speed<=40 and abs(speed-args.speed*10)<1e-6
    assert not(args.checkpoints and args.time_attack)
    for pack in PACKS if args.all else [args.pack]:
      base=ROOT/'build/campaign' if pack=='main' else ROOT/f'build/packs/{pack}'
      labels={m[1]:int(m[0],16) for m in re.findall(r'al ([0-9A-Fa-f]+) \.([\w]+)',(base/'adofai.lbl').read_text())}
      if 'cell_hash_dirty' in labels:
        labels['m7_visual_step']=labels['cell_hash_dirty'];labels['m7_logical_step']=labels['cell_hash_bucket']
      levels=json.loads((base/'pack.json').read_text())['levels']
      for level in args.levels or range(1,len(levels)+1):
        suffix=f'-speed-{speed:02d}'+('-attack' if args.time_attack else '') if speed!=10 or args.time_attack else ''
        if args.autoplay:suffix+='-autoplay'
        if args.prepare_only:suffix+='-prepared'
        out=base/f'verification/mesen-{"checkpoints-" if args.checkpoints else ""}{level}{suffix}';out.mkdir(parents=True,exist_ok=True)
        global_id=levels[level-1]
        chart=json.loads((base/f'level{global_id}.json').read_text())
        if args.checkpoints and not chart['checkpoints']:continue
        digest=hashlib.sha256((base/'adofai.sfc').read_bytes()).hexdigest()
        loaded_identity=identity(base/'adofai.sfc')
        loaded_suite=suite_digest()
        report=out/'result.txt';manifest=out/'manifest.json'
        if args.resume and report.exists() and manifest.exists():
            previous=json.loads(manifest.read_text())
            if previous.get('suite_digest')==loaded_suite and previous.get('graphics_dumps')==args.graphics_dumps and previous.get('suite_version',0)>=2 and previous.get('passed') is True and previous['sha256']==digest and previous.get('msu_sha256')==loaded_identity['msu_sha256'] and report.read_text().endswith('PASS\n'):
                print(chart['code']+': PASS (current ROM already verified)',flush=True)
                continue
        # A resumed, verified replay owns its captures. Delete them only
        # when this invocation will actually replace them with a new replay.
        if args.graphics_dumps:
            for pattern in ('ppu-*.bin','screen-*.png','step-*.png'):
                for capture in out.glob(pattern):capture.unlink()
            for name in ('hold-orbits.txt','hold-planets.txt','screen-registers.txt','mode1-icon-jobs.txt','ppu-verification.json'):
                (out/name).unlink(missing_ok=True)
        names=('state','step','elapsed','combo','perfects','misses','selected_level','speed_tenths','time_attack','judgment_counts','score_lo','score_hi','finish_cs','nmi_audio_ticks','audio_ticks','speed_offset','joy')
        if 'pattern_vblank_overruns' in labels:names+=('pattern_vblank_overruns',)
        if chart.get('track_palette_versions'):
            names+=('display_state','display_chart_time','commits')
            names+=tuple(n for n in ('animation_time','animation_kind','animation_header','animation_cursor','animation_value','animation_index','chart_time','pattern_vblank_overruns','vblank_first_time','vblank_first_state','vblank_first_music','vblank_first_queue') if n in labels)
        if args.graphics_dumps:names+=('display_state','display_chart_time','display_cam_x','display_cam_y','commits','oam_pos')
        if args.graphics_dumps:names+=('frame_ready',)
        if args.graphics_dumps and 'sa1_arc_complete' in labels:
            names+=('trail_pos_x','trail_pos_y','trail_current','trail_previous','trail_pieces','trail_age','trail_orb','trail_stroke')
        names=tuple(dict.fromkeys(names))
        if args.checkpoints:names+=('checkpoint_floor','checkpoint_preroll','music_origin','checkpoints_used','display_state','cam_x','cam_y','angle','chart_time')
        cpconfig=''
        if args.checkpoints:cpconfig=',checkpoints={'+','.join('{trigger='+str(c['trigger'])+',floor='+str(c['floor'])+',origin='+str(c['origin_frame'])+'}' for c in chart['checkpoints'])+'}'
        actions=''
        if suffix or 'menu_depth' in labels:
            seq={90:'b'};f=96
            if args.time_attack:seq[f]='right';f+=4
            seq[f]='down';f+=4
            for _ in range(abs(speed-10)):seq[f]='right' if speed>10 else 'left';f+=4
            seq[f]='start';f+=8
            if 'menu_depth' in labels:
                from menu_sets import groups
                sets=groups(levels)
                group=next(i for i,(_,indices) in enumerate(sets) if level-1 in indices)
                if len(sets)>1:
                    for _ in range(group):seq[f]='down';f+=4
                    seq[f]='start';f+=8
                selection=sets[group][1].index(level-1)
            else:selection=level-1
            for _ in range(selection):seq[f]='down';f+=4
            seq[f+12]='start'
            actions=',menu_actions={'+','.join('['+str(k)+']="'+v+'"' for k,v in seq.items())+'}'
            if args.autoplay:actions+=f',autoplay_frame={f+8}'
        pitch=round(1536*speed/10)
        if json.loads((base/'pack.json').read_text()).get('fast_audio_rate') and speed>10:pitch=round(pitch/3)*3
        manual_notes=[n for n in chart['notes'][1:] if not(n['flags']&8) for _ in range(n.get('taps_needed',1))]
        scheduled=',pitch='+str(pitch)+',manual_times={'+','.join(str(n['frame']) for n in manual_notes)+'},manual_steps={'+','.join(str(n['step']) for n in manual_notes)+'}'
        if args.autoplay:scheduled+=',autoplay=true'
        if chart.get('neo_cosmos') and not args.autoplay:
            # Full manual replay uses down/up edges, not an autoplay toggle.
            events=[];held=0;key=0
            for i,note in enumerate(chart['notes'][1:],1):
                if note['flags']&8:continue
                previous=chart['notes'][i-1]
                if previous['flags']&16 and i>=2:previous=chart['notes'][i-2]
                if previous.get('hold_length',-1)>=0 and note.get('hold_length',-1)<0:
                    held=0
                else:
                    key=1 if key!=1 else 2
                    held=key
                events.append((note['frame'],held,note['step']))
            for region in chart.get('freeroam_regions',[]):
                route=region.get('demo_route',[])
                if not route:continue
                held=next(e[1] for e in reversed(events) if e[0]<=region['start'])
                held=held if held in (1,2) else 1
                for at,x,y,angle in route:
                    held=3-held
                    events.append((at,held,region['step']+1))
                events.append((route[-1][0]+3,0,region['step']+1))
            events.sort()
            scheduled+=',neo_events={'+','.join('{'+','.join(map(str,row))+'}' for row in events)+'}'
        scheduled+=',failfast_script='+json.dumps((ROOT/'tools/mesen_failfast.lua').as_posix())
        scheduled+=',input_script='+json.dumps((ROOT/'tools/verify_input_sampling_mesen.lua').as_posix())
        if chart.get('sa1_stream_format'):scheduled+=',stream_runtime=true'
        if chart.get('mode1_tracks'):scheduled+=',mode1_runtime=true'
        if args.graphics_dumps and chart.get('mode1_tracks'):scheduled+=',screen_script='+json.dumps((ROOT/'tools/verify_mode1_screen_mesen.lua').as_posix())
        if chart.get('mode1_tracks') and not args.checkpoints:
            scheduled+=',profile_ranges={{4,24}'+(',{120,180},{390,408}' if global_id==71 else '')+'}'
        if args.graphics_dumps:scheduled+=',graphics_dumps=true'
        if args.graphics_dumps and chart.get('neo_cosmos'):
            scheduled+=',midspin={script='+json.dumps((ROOT/'tools/verify_midspin_pose_mesen.lua').as_posix())+',entry='+str(labels['neo_far_prepare_hold'])+',addr={'+','.join(k+'='+str(labels[k]) for k in ('m7_visual_step','m7_logical_step'))+'},flags={'+','.join(str(n['flags']) for n in chart['notes'])+'}}'
        if args.graphics_dumps and chart.get('neo_math_questions'):
            from neo_math import POOLS,FONT_CHARS
            mfields=('neo_math_group','neo_math_label','neo_math_choices','sprite_x','sprite_y','oam_pos')
            pairs=','.join('['+json.dumps(k)+']={'+','.join('{'+','.join(json.dumps(str(v)) for v in (q+'=',a,b))+'}' for q,a,b in variants)+'}' for k,variants in POOLS.items())
            scheduled+=',math={script='+json.dumps((ROOT/'tools/verify_math_mesen.lua').as_posix())+',code='+json.dumps(chart['code'])+',font='+json.dumps((ROOT/'assets/graphics/mode7/math-font.chr').as_posix())+',chars='+json.dumps(FONT_CHARS)+',before='+str(labels['neo_math_before_label'])+',after='+str(labels['neo_math_after_label'])+',addr={'+','.join(k+'='+str(labels[k]) for k in mfields)+'},pools={'+pairs+'}}'
        if args.graphics_dumps:
            bank=0x800000 if 'SA1_FASTROM_MIRROR = 1' in (base/'addresses.inc').read_text() else 0
            scheduled+=',dma_script='+json.dumps((ROOT/'tools/verify_dma_window_mesen.lua').as_posix())+',dma_complete='+str(labels['mode7_cache_commit']+bank)
            if chart.get('mode1_tracks')==3:
                assert 'snapshot_prefetch_done' in labels and 'snapshot_prefetch_begin' in labels,'Missing atlas publication verification entry points'
            if 'snapshot_prefetch_done' in labels:scheduled+=',dma_prefetch_complete='+str(labels['snapshot_prefetch_done'])+',dma_prefetch_begin='+str(labels['snapshot_prefetch_begin'])
            if chart.get('mawaru_copy_world'):
                scheduled+=',copies={complete='+str(labels['neo_camera_copies_complete'])+',script='+json.dumps((ROOT/'tools/verify_copies_mesen.lua').as_posix())+'}'
        if args.graphics_dumps and chart.get('mode1_tracks'):
            holds=[(n['frame'],chart['notes'][i+1]['frame']) for i,n in enumerate(chart['notes'][:-1]) if n.get('hold_length',-1)>=0]
            captures=sorted({round(a+(b-a)*f) for a,b in holds[:3]+holds[-2:] for f in (.1,.5,.9)})
            scheduled+=',screen_captures={'+','.join(map(str,captures))+'}'
        if args.graphics_dumps and 'sa1_arc_complete' in labels:
            entries=('sa1_draw_arc','sa1_arc_complete','orbit_arc_x','orbit_arc_y','orbit_arc_tiles','orbit_arc_flips')
            fast='SA1_FASTROM_MIRROR = 1' in (base/'addresses.inc').read_text()
            scheduled+=',arc={'+','.join(n+'='+str(labels[n]+(0x800000 if fast and n.startswith('sa1_') else 0)) for n in entries)+',script='+json.dumps((ROOT/'tools/verify_sa1_arc_mesen.lua').as_posix())+'}'
        if args.graphics_dumps and 'sa1_spill_complete' in labels:
            fast='SA1_FASTROM_MIRROR = 1' in (base/'addresses.inc').read_text()
            bank=0x800000 if fast else 0
            scheduled+=',objects={entry='+str(labels['sa1_draw_spills']+bank)+',complete='+str(labels['sa1_spill_complete']+bank)+',script='+json.dumps((ROOT/'tools/verify_sa1_objects_mesen.lua').as_posix())+'}'
        if args.graphics_dumps and chart.get('mode1_tracks')==1:
            from animation_catchup import unpack_events
            import struct
            world=[]
            for t,k,i,v,payload in unpack_events((base/f'animation{global_id}.bin').read_bytes(),chart):
                if k in (1,2,3):world.append([t,k,i,v])
                elif k==28:world.append([t,k,*struct.unpack('<'+'H'*(len(payload)//2),payload)])
            initial=','.join('{'+str(n['x'])+','+str(n['y'])+'}' for n in chart['notes'])
            worldpath=out/'icon-world.lua'
            worldpath.write_text('return {initial={'+initial+'},events={'+','.join('{'+','.join(map(str,e))+'}' for e in world)+'}}')
            bank=0x800000 if 'SA1_FASTROM_MIRROR = 1' in (base/'addresses.inc').read_text() else 0
            data=','.join('{'+','.join(map(str,(n['flags'],n.get('hold_length',-1),int(n['ccw']),n.get('planets',2))))+'}' for n in chart['notes'])
            scheduled+=',icons={ready='+str(labels['mode1_icons_ready']+bank)+',complete='+str(labels['mode1_icons_complete']+bank)+',attack='+str(labels['time_attack'])+',checkpoint='+str(labels['checkpoint_record'])+',cam_x='+str(labels['cam_x'])+',cam_y='+str(labels['cam_y'])+',world='+json.dumps(worldpath.as_posix())+',notes={'+data+'},script='+json.dumps((ROOT/'tools/verify_mode1_icons_mesen.lua').as_posix())+'}'
        if args.trace_frame:scheduled+=',trace_frame='+str(args.trace_frame)
        if args.graphics_dumps and chart.get('neo_cosmos') and not args.checkpoints:
            import math
            from hold_path import sweep
            holdrows=[]
            for i,n in enumerate(chart['notes'][:-1]):
                if n.get('hold_length',-1)<0:continue
                end=chart['notes'][i+1];a=end['angle']*math.pi/128
                holdrows.append('['+str(i)+']={start='+str(n['frame'])+',finish='+str(end['frame'])+',angle='+str(n['angle'])+',sweep='+str(sweep(n)*128/math.pi)+',x='+str(round(24*math.cos(a)))+',y='+str(round(24*math.sin(a)))+'}')
            hnames=('state','step','chart_time','angle','neo_hold_phase','neo_hold_x','neo_hold_y','NOTE_X','NOTE_Y','palette_dirty','cam_x','cam_y','m7_radius','orbit_x','orbit_y')
            scheduled+=',holds={complete='+str(labels['neo_far_apply_ease']+3)+',script='+json.dumps((ROOT/'tools/verify_hold_orbit_mesen.lua').as_posix())+',addr={'+','.join(n+'='+str(labels[n]) for n in hnames)+'},notes={'+','.join(holdrows)+'}}'
        if args.capture_times:scheduled+=',capture_times={'+','.join('['+str(t)+']=true' for t in args.capture_times)+'}'
        if args.capture_steps:scheduled+=',capture_steps={'+','.join(map(str,args.capture_steps))+'}'
        if chart.get('track_palette_versions'):
            scheduled+=',palette_script='+json.dumps((ROOT/'tools/verify_palette_mesen.lua').as_posix())+',palette={'+','.join('{'+','.join(map(str,e))+'}' for e in chart['track_palette_versions'])+'}'
        config='return {addr={'+','.join(k+'='+str(labels[k]) for k in names)+'},times={'+','.join(str(n['frame']) for n in chart['notes'])+'},out='+json.dumps(out.as_posix())+',level='+str(level)+',steps='+str(chart['steps'])+',hits='+str(chart['hits'])+',speed='+str(speed)+',attack='+str(int(args.time_attack))+',finish_centis='+str(round(chart['notes'][-1]['time']*100*1536/pitch) if 'time' in chart['notes'][-1] else round(chart['notes'][-1]['frame']/60.0988118623*100*1536/pitch))+',frames='+str(round(chart['duration']*60.099*1536/pitch)+600+(len(chart['checkpoints'])*900 if args.checkpoints else 0))+cpconfig+actions+'}\n'
        config=config.rstrip()[:-1]+scheduled+'}\n'
        path=out/'config.lua';path.write_text(config)
        if args.prepare_only:continue
        env=os.environ.copy();env['ADOFAI_TEST_CONFIG']=str(path)
        script='verify_checkpoints_mesen.lua' if args.checkpoints else 'verify_campaign_mesen.lua'
        if report.exists():report.unlink()
        # Mesen's own default wall-clock limit is shorter than long songs
        # under concurrent verification. Keep both limits explicit.
        wall_limit=600 if args.checkpoints else 450
        result=subprocess.run([str(args.mesen),'--testrunner',f'--timeout={wall_limit}',str(base/'adofai.sfc'),str(ROOT/'tools'/script)],env=env,cwd=ROOT,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0,timeout=wall_limit+30,capture_output=True,text=True)
        (out/'emulator.log').write_text(result.stdout+result.stderr)
        report=out/'result.txt'
        if not report.exists():raise RuntimeError(f'Mesen exited {result.returncode} without a result; see {out / "emulator.log"}\n'+result.stdout[-2000:]+result.stderr[-2000:])
        text=report.read_text();print(chart['code']+': '+text.splitlines()[0],flush=True)
        assert identity(base/'adofai.sfc')==loaded_identity,'ROM or MSU data changed during Mesen verification'
        assert suite_digest()==loaded_suite,'Verification code changed during the replay'
        samples=re.search(r'palette_samples=(\d+)',text)
        overruns=re.search(r'vblank_overruns=(\d+)',text)
        (out/'manifest.json').write_text(json.dumps(dict(code=chart['code'],sha256=digest,**loaded_identity,suite_version=2,suite_digest=loaded_suite,graphics_dumps=args.graphics_dumps,passed=False,summary=text.splitlines()[0],speed=speed/10,time_attack=args.time_attack,track_palette_samples=int(samples[1]) if samples else 0,vblank_overruns=int(overruns[1]) if overruns else None),indent=2))
        assert result.returncode==0 and text.endswith('PASS\n'),text[-1000:]
        if overruns:assert int(overruns[1])==0,'Hardware upload crossed VBlank'
        if args.graphics_dumps and chart.get('mode1_tracks') and speed<=10:
            screen=out/'screen-registers.txt'
            assert screen.exists() and int(re.search(r'samples=(\d+)',screen.read_text())[1])>100,'Missing hardware screen coverage'
            if chart.get('mode1_tracks')==1:
                jobs=out/'mode1-icon-jobs.txt'
                assert jobs.exists() and int(jobs.read_text())>100,'Missing chart-derived symbol coverage'
            if not args.checkpoints:assert len(list(out.glob('screen-*.png')))>=9,'Missing moving-hold screenshots'
        if args.graphics_dumps and not args.checkpoints and any(n.get('hold_length',-1)>=0 for n in chart['notes']):
            for name in ('hold-orbits.txt','hold-planets.txt') if chart.get('mode1_tracks')==1 else ('hold-orbits.txt',):
                coverage=out/name
                assert coverage.exists(),f'Missing hold verification coverage: {coverage}'
                count=int(re.search(r'samples=(\d+)',coverage.read_text())[1])
                assert count>(100 if chart.get('mode1_tracks') else 0),f'Insufficient hold checks: {coverage}: {count}'
        if args.graphics_dumps and chart.get('neo_math_questions'):
            coverage=out/'math-labels.txt'
            assert coverage.exists() and int(re.search(r'samples=(\d+)',coverage.read_text())[1])>100,'Missing live math-label coverage'

        verified=json.loads(manifest.read_text());verified['passed']=True;manifest.write_text(json.dumps(verified,indent=2))

if __name__=='__main__':main()
