"""Replay official cartridge packs in the independent Mesen SNES core."""
import argparse,json,os,re,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
import hashlib,sys
sys.path.insert(0,str(ROOT/'tools'))
from official_catalog import PACKS
from verification_data import identity
from pack_sources import load_source

def suite_digest():
    oracle_modules=('mesen_failfast.lua','run_mesen_campaign.py','run_mesen_sequence.py',
        'menu_sets.py','controller_events.py','pack_sources.py','input_event_assets.py',
        'verify_mesen_ppu.py','projected_tracks.py','mode1_tracks.py','decoration_tracks.py',
        'gameplay_decorations.py','decoration_hitboxes.py','decoration_actors.py',
        'projected_copies.py','neo_fog.py','neo_headings.py','hold_path.py',
        'planet_scale.py','viewport_cells.py')
    paths=sorted((ROOT/'tools').glob('verify*mesen.lua'))+[ROOT/'tools'/name for name in oracle_modules]
    return hashlib.sha256(b''.join(p.name.encode()+p.read_bytes() for p in paths)).hexdigest()
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--mesen',type=Path,default=Path(r'C:\mesen2\Mesen.exe'))
    ap.add_argument('--prepare-only',action='store_true');ap.add_argument('--levels',type=int,nargs='+');ap.add_argument('--pack',default='main');ap.add_argument('--all',action='store_true');ap.add_argument('--checkpoints',action='store_true')
    ap.add_argument('--speed',type=float,default=1.0);ap.add_argument('--time-attack',action='store_true');ap.add_argument('--resume',action='store_true')
    ap.add_argument('--vfx-off',action='store_true',help='Disable optional scenery through the real options menu')
    ap.add_argument('--trace-frame',type=int);ap.add_argument('--graphics-dumps',action='store_true');ap.add_argument('--sampled-graphics',action='store_true',help='Sample hardware pixels every 240 commits; full DMA-byte checks remain a separate stress test');ap.add_argument('--capture-steps',type=int,nargs='+');ap.add_argument('--capture-times',type=int,nargs='+',help='Also verify PPU output at these presented chart-clock frames');ap.add_argument('--autoplay',action='store_true');args=ap.parse_args()
    if args.sampled_graphics:args.graphics_dumps=True
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
        if args.vfx_off:suffix+='-vfx-off'
        if args.prepare_only:suffix+='-prepared'
        out=base/f'verification/mesen-{"checkpoints-" if args.checkpoints else ""}{level}{suffix}';out.mkdir(parents=True,exist_ok=True)
        global_id=levels[level-1]
        chart=json.loads((base/f'level{global_id}.json').read_text())
        if args.vfx_off and chart.get('vfx_off'):
            alternate=chart['vfx_off']
            chart=json.loads((base/alternate['verification_source']/f'level{global_id}.json').read_text())
            chart.update(alternate)
        if args.checkpoints and not chart['checkpoints']:continue
        digest=hashlib.sha256((base/'adofai.sfc').read_bytes()).hexdigest()
        loaded_identity=identity(base/'adofai.sfc')
        loaded_suite=suite_digest()
        report=out/'result.txt';manifest=out/'manifest.json'
        if args.resume and report.exists() and manifest.exists():
            previous=json.loads(manifest.read_text())
            if previous.get('suite_digest')==loaded_suite and previous.get('graphics_dumps')==args.graphics_dumps and previous.get('sampled_graphics',False)==args.sampled_graphics and previous.get('suite_version',0)>=2 and previous.get('passed') is True and previous['sha256']==digest and previous.get('msu_sha256')==loaded_identity['msu_sha256'] and report.read_text().endswith('PASS\n'):
                print(chart['code']+': PASS (current ROM already verified)',flush=True)
                continue
        # A resumed, verified replay owns its captures. Delete them only
        # when this invocation will actually replace them with a new replay.
        if args.graphics_dumps:
            for pattern in ('ppu-*.bin','screen-*.png','step-*.png'):
                for capture in out.glob(pattern):capture.unlink()
            for name in ('hold-orbits.txt','hold-planets.txt','hold-coverage.txt','screen-registers.txt','screen-capture-times.csv','mode1-icon-jobs.txt','ppu-verification.json'):
                (out/name).unlink(missing_ok=True)
        names=('state','step','elapsed','combo','perfects','misses','selected_level','speed_tenths','time_attack','judgment_counts','score_lo','score_hi','finish_cs','nmi_audio_ticks','audio_ticks','speed_offset','joy')
        if global_id in (280,284):
            names+=('clock_song_frames','clock_song_frac','speed_offset_frac','music_origin','speed_scale')
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
            seq={90:'select' if labels.get('MENU_OPTIONS_SELECT') else 'b'};f=96
            if args.time_attack:seq[f]='right';f+=4
            seq[f]='down';f+=4
            for _ in range(abs(speed-10)):seq[f]='right' if speed>10 else 'left';f+=4
            if args.vfx_off != (labels.get('vfx_default_value',1)==0):
                for _ in range(5):seq[f]='down';f+=4
                seq[f]='right';f+=4
            seq[f]='start';f+=8
            if 'menu_depth' in labels:
                from menu_sets import groups_for_pack
                sets=groups_for_pack(base)
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
        scheduled+=',viewport_top='+str(chart.get('viewport_top',chart.get('snapshot_map_top',32)))+',viewport_bottom='+str(chart.get('viewport_bottom',176))
        scheduled+=',snapshot_aligned='+str(bool(chart.get('snapshot_aligned'))).lower()
        scheduled+=',progress_row=26'
        if 'vfx_enabled' in labels:
            scheduled+=',vfx={address='+str(labels['vfx_enabled'])+',expected='+str(0 if args.vfx_off else 1)+'}'
        if not args.autoplay and 'INPUT_EVENT_BUILD = 1' in (base/'addresses.inc').read_text():
            from input_event_assets import schedule as input_schedule
            source=load_source(base,global_id)
            filters=input_schedule(source,chart)
            if filters:scheduled+=',input_filters={'+','.join('{'+','.join(map(str,row))+'}' for row in filters)+'}'
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
            from controller_events import chords
            events=chords(events)
            scheduled+=',neo_events={'+','.join('{'+','.join(map(str,row))+'}' for row in events)+'}'
        scheduled+=',failfast_script='+json.dumps((ROOT/'tools/mesen_failfast.lua').as_posix())
        scheduled+=',input_script='+json.dumps((ROOT/'tools/verify_input_sampling_mesen.lua').as_posix())
        if chart.get('sa1_stream_format'):scheduled+=',stream_runtime=true'
        if chart.get('mode1_tracks'):scheduled+=',mode1_runtime=true'
        if args.graphics_dumps and chart.get('mode1_tracks'):scheduled+=',screen_script='+json.dumps((ROOT/'tools/verify_mode1_screen_mesen.lua').as_posix())
        if chart.get('mode1_tracks') and not args.checkpoints:
            scheduled+=',profile_ranges={{4,24}'+(',{120,180},{390,408}' if global_id==71 else '')+',{0,'+str(len(chart['notes'])-1)+'}}'
        if args.graphics_dumps:scheduled+=',graphics_dumps=true,capture_period='+str(240 if args.sampled_graphics else 30)
        if args.graphics_dumps and chart.get('neo_cosmos'):
            scheduled+=',midspin={script='+json.dumps((ROOT/'tools/verify_midspin_pose_mesen.lua').as_posix())+',entry='+str(labels['neo_far_prepare_hold'])+',addr={'+','.join(k+'='+str(labels[k]) for k in ('m7_visual_step','m7_logical_step','chart_time'))+'},flags={'+','.join(str(n['flags']) for n in chart['notes'])+'},times={'+','.join(str(n['frame']) for n in chart['notes'])+'}}'
        if args.graphics_dumps and chart.get('neo_math_questions'):
            from neo_math import POOLS,FONT_CHARS
            mfields=('neo_math_group','neo_math_label','neo_math_choices','sprite_x','sprite_y','oam_pos')
            pairs=','.join('['+json.dumps(k)+']={'+','.join('{'+','.join(json.dumps(str(v)) for v in (q+'=',a,b))+'}' for q,a,b in variants)+'}' for k,variants in POOLS.items())
            scheduled+=',math={script='+json.dumps((ROOT/'tools/verify_math_mesen.lua').as_posix())+',code='+json.dumps(chart['code'])+',font='+json.dumps((ROOT/'assets/graphics/mode7/math-font.chr').as_posix())+',chars='+json.dumps(FONT_CHARS)+',before='+str(labels['neo_math_before_label'])+',after='+str(labels['neo_math_after_label'])+',addr={'+','.join(k+'='+str(labels[k]) for k in mfields)+'},pools={'+pairs+'}}'
        if args.graphics_dumps and not args.sampled_graphics:
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
            # Snapshot charts are also used by songs without holds. Give
            # those charts real screenshot coverage across the whole song.
            if len(captures)<9:
                captures=sorted(set(captures)|{round(chart['notes'][-1]['frame']*i/10) for i in range(1,10)})
            captures=sorted(set(captures)|set(args.capture_times or []))
            scheduled+=',screen_captures={'+','.join(map(str,captures))+'}'
        if args.graphics_dumps and 'sa1_arc_complete' in labels:
            entries=('sa1_draw_arc','sa1_arc_complete','orbit_arc_x','orbit_arc_y','orbit_arc_tiles','orbit_arc_flips')
            fast='SA1_FASTROM_MIRROR = 1' in (base/'addresses.inc').read_text()
            scheduled+=',arc={'+','.join(n+'='+str(labels[n]+(0x800000 if fast and n.startswith('sa1_') else 0)) for n in entries)+',script='+json.dumps((ROOT/'tools/verify_sa1_arc_mesen.lua').as_posix())+'}'
        if args.graphics_dumps and 'sa1_spill_complete' in labels:
            fast='SA1_FASTROM_MIRROR = 1' in (base/'addresses.inc').read_text()
            bank=0x800000 if fast else 0
            scheduled+=',objects={entry='+str(labels['sa1_draw_spills']+bank)+',complete='+str(labels['sa1_spill_complete']+bank)+',script='+json.dumps((ROOT/'tools/verify_sa1_objects_mesen.lua').as_posix())+'}'
        if args.graphics_dumps and chart.get('mode1_tracks')==3 and 'EXTENDED_CHART_BUILD = 1' in (base/'addresses.inc').read_text():
            bank=0x800000 if 'SA1_FASTROM_MIRROR = 1' in (base/'addresses.inc').read_text() else 0
            data=','.join('{'+','.join(map(str,(n['flags'],n.get('hold_length',-1),int(n['ccw']),n.get('planets',2))))+'}' for n in chart['notes'])
            scheduled+=',snapshot_icons={ready='+str(labels['mode1_icons_ready']+bank)+',complete='+str(labels['mode1_icons_complete']+bank)+',sparse_complete='+str(labels['snapshot_sparse_complete']+bank)+',attack='+str(labels['time_attack'])+',checkpoint='+str(labels['checkpoint_record'])+',notes={'+data+'},script='+json.dumps((ROOT/'tools/verify_snapshot_icons_mesen.lua').as_posix())+'}'
        if args.graphics_dumps and 'SYMBOL_SCALE_BUILD = 1' in (base/'addresses.inc').read_text():
            scheduled+=',symbol_scale_inverse='+str(labels['camera_inverse'])
            scheduled+=',symbol_scale={loaded='+str(labels['SYMBOL_SCALE_LOADED']&0x3ffff)+',pending='+str(labels['SYMBOL_SCALE_PENDING']&0x3ffff)+',vram='+str(labels['SYMBOL_SCALE_VRAM']&0x3ffff)+',irq='+str(labels['EARLY_IRQ_RUNNING']&0x3ffff)+',frames='+json.dumps((base/'symbol_scale_frames.bin').as_posix())+',script='+json.dumps((ROOT/'tools/verify_symbol_scale_mesen.lua').as_posix())+'}'
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
        if args.graphics_dumps and chart.get('neo_cosmos') and any(n.get('planets')==3 for n in chart['notes']):
            if 'neo_twirl_complete' in labels:
                scheduled+=',twirl_stream={entry='+str(labels['neo_far_twirl_orbit'])+',complete='+str(labels['neo_twirl_complete'])+',script='+json.dumps((ROOT/'tools/verify_twirl_stream_mesen.lua').as_posix())+'}'
            bank=0x800000 if 'SA1_FASTROM_MIRROR = 1' in (base/'addresses.inc').read_text() else 0
            controls=','.join(str(int(n['ccw'])+(2 if n['planets']==3 else 0)) for n in chart['notes'])
            twirls=[]
            for i,n in enumerate(chart['notes'][1:-1],1):
                if n['planets']!=3 or chart['notes'][i-1]['planets']!=3 or not n['flags']&4:continue
                duration=chart['notes'][i+1]['frame']-n['frame']
                if duration<=0:continue
                free=n.get('freeroam',False)
                tween=60/chart['bpm']*n['speed']*.375*60.0988118623 if free else duration/2
                twirls.append('['+str(i+1)+']={start='+str(n['frame'])+',tween='+str(tween)+',first='+str(.5 if free else 1)+'}')
            scheduled+=',triplet={entry='+str(labels['mode7_draw_orb']+bank)+',x='+str(labels['sprite_x'])+',y='+str(labels['sprite_y'])+',attr='+str(labels['sprite_attr'])+',free='+str(labels['neo_free_mode'])+',reversed='+str(labels['neo_free_reversed'])+',now='+str(labels['chart_time'])+',fx='+str(labels['floor_x'])+',fy='+str(labels['floor_y'])+',continuity='+str(global_id==256).lower()+',twirls={'+','.join(twirls)+'},controls={'+controls+'},script='+json.dumps((ROOT/'tools/verify_triplet_mesen.lua').as_posix())+'}'
            if 'neo_preview_circle' in labels:
                import math
                native=load_source(base,global_id)
                rows=[]
                for i,n in enumerate(chart['notes']):
                    if not i or n['planets']!=3 or chart['notes'][i-1]['planets']==3:continue
                    floor=native['floors'][i];angle=floor['entryangle']-math.pi/2
                    apex=angle+(-math.pi/3 if n['ccw'] else math.pi/3)
                    radius=24*floor.get('radiusScale',1)
                    row=[round(radius*f(a)) for a in (angle,apex) for f in (math.cos,math.sin)]
                    rows.append('['+str(i)+']={'+','.join(map(str,row))+'}')
                pnames=('render_i','sprite_x','sprite_y','sprite_attr','cam_x','cam_y','project_limit_x','project_limit_y')
                scheduled+=',preview={circle='+str(labels['neo_preview_circle'])+',dash='+str(labels['neo_preview_dash'])+',source_x='+str(labels['SYMBOL_X'])+',source_y='+str(labels['SYMBOL_Y'])+',addr={'+','.join(n+'='+str(labels[n]) for n in pnames)+'},entries={'+','.join(rows)+'},script='+json.dumps((ROOT/'tools/verify_planet_preview_mesen.lua').as_posix())+'}'
        if args.graphics_dumps and chart.get('neo_cosmos') and not args.checkpoints:
            import math
            from hold_path import sweep
            native=load_source(base,global_id)
            holdrows=[]
            for i,n in enumerate(chart['notes'][:-1]):
                if n.get('hold_length',-1)<0:continue
                end=chart['notes'][i+1]
                # Derive the exit independently from the native floor, not
                # from NOTE_ANGLE (which contains multiplanet spacing).
                a=native['floors'][i]['exitangle']-math.pi/2
                radius=24*native['floors'][i+1].get('radiusScale',1)
                holdrows.append('['+str(i)+']={start='+str(n['frame'])+',finish='+str(end['frame'])+',planets='+str(n.get('planets',2))+',angle='+str(n['angle'])+',sweep='+str(sweep(n)*128/math.pi)+',x='+str(round(-radius*math.cos(a)))+',y='+str(round(-radius*math.sin(a)))+'}')
            hnames=('state','step','chart_time','angle','neo_hold_phase','neo_hold_x','neo_hold_y','NOTE_X','NOTE_Y','palette_dirty','cam_x','cam_y','m7_radius','orbit_x','orbit_y','CAMERA_SCRIPT_X','CAMERA_SCRIPT_Y','neo_free_mode')
            hnames+=('neo_orb_roles',)
            from planet_scale import schedule as planet_scale_schedule
            scale_rows=planet_scale_schedule(native,chart) if native.get('planet_scale_import') else []
            scale_lua='{'+','.join('{'+','.join(map(str,row))+'}' for row in scale_rows)+'}'
            for name in ('CAMERA_SCRIPT_X','CAMERA_SCRIPT_Y'):
                labels[name]=int(re.search(r'^'+name+r'=\$([0-9A-Fa-f]+)',(ROOT/'src/campaign.s').read_text(),re.M)[1],16)
            free_rows=[]
            for region in chart.get('freeroam_regions',[]):
                i=region['step'];end=chart['notes'][i+1]
                a=native['floors'][i+1]['entryangle']-math.pi/2
                free_rows.append('['+str(i)+']={finish='+str(region['end'])+',angle='+str((round(a*128/math.pi)+128)&255)+',rate='+str(abs(chart['notes'][i]['rate'])*(-1 if end['ccw'] else 1))+'}')
            bank=0x800000 if 'SA1_FASTROM_MIRROR = 1' in (base/'addresses.inc').read_text() else 0
            scheduled+=',holds={scales='+scale_lua+',native_anchor='+str('ROM_NATIVE_ADDR =' in (base/'addresses.inc').read_text()).lower()+',projected='+str(bool(chart.get('mode1_projected'))).lower()+',complete='+str(labels['neo_far_apply_ease']+3)+',free_complete='+str(labels['neo_free_orbit']+4+bank)+',free={'+','.join(free_rows)+'},script='+json.dumps((ROOT/'tools/verify_hold_orbit_mesen.lua').as_posix())+',addr={'+','.join(n+'='+str(labels[n]) for n in hnames)+'},notes={'+','.join(holdrows)+'}}'
        if args.capture_times:scheduled+=',capture_times={'+','.join('['+str(t)+']=true' for t in args.capture_times)+'}'
        if chart.get('mode1_snapshot') and 'SNAPSHOT_ONLY_COORDS = 1' in (base/'addresses.inc').read_text():
            address=json.loads((base/'placements.json').read_text())[f'visibility_index{global_id}']
            scheduled+=',sparse={address='+str(address)+',script='+json.dumps((ROOT/'tools/verify_snapshot_coordinates_mesen.lua').as_posix())+'}'
        if args.capture_steps:scheduled+=',capture_steps={'+','.join(map(str,args.capture_steps))+'}'
        if chart.get('track_palette_versions'):
            scheduled+=',palette_script='+json.dumps((ROOT/'tools/verify_palette_mesen.lua').as_posix())+',palette={'+','.join('{'+','.join(map(str,e))+'}' for e in chart['track_palette_versions'])+'}'
        actions+=',wide_atlas='+str(bool(chart.get('wide_snapshot_atlas'))).lower()
        actions+=',indexed_color_support='+('true' if chart.get('indexed_color_frames') else 'false')
        frame_limit=round(chart['duration']*60.099*1536/pitch)+600+(len(chart['checkpoints'])*900 if args.checkpoints else 0)
        config='return {addr={'+','.join(k+'='+str(labels[k]) for k in names)+'},times={'+','.join(str(n['frame']) for n in chart['notes'])+'},out='+json.dumps(out.as_posix())+',level='+str(level)+',steps='+str(chart['steps'])+',hits='+str(chart['hits'])+',speed='+str(speed)+',attack='+str(int(args.time_attack))+',finish_centis='+str(round(chart['notes'][-1]['time']*100*1536/pitch) if 'time' in chart['notes'][-1] else round(chart['notes'][-1]['frame']/60.0988118623*100*1536/pitch))+',frames='+str(frame_limit)+cpconfig+actions+'}\n'
        if 'native_animation_receive_done' in labels:
            coordinate_bank=0x800000 if 'SA1_FASTROM_MIRROR = 1' in (base/'addresses.inc').read_text() else 0
            scheduled+=',coordinates={script='+json.dumps((ROOT/'tools/verify_coordinates_mesen.lua').as_posix())+',done='+str(labels['native_animation_receive_done']+coordinate_bank)+',first=0x42B21E,last=0x42B220,x='+str(labels['NOTE_X'])+',y='+str(labels['NOTE_Y'])+',source_x='+str(labels.get('SYMBOL_X',0x410000))+',source_y='+str(labels.get('SYMBOL_Y',0x412200))+',limit='+str(labels.get('MAX_NOTE_CAPACITY',4352)*2)+'}'
        config=config.rstrip()[:-1]+scheduled+'}\n'
        path=out/'config.lua';path.write_text(config)
        if args.prepare_only:continue
        env=os.environ.copy();env['ADOFAI_TEST_CONFIG']=str(path)
        script='verify_checkpoints_mesen.lua' if args.checkpoints else 'verify_campaign_mesen.lua'
        if report.exists():report.unlink()
        # Pixel/input probes can run slower than real time on a busy host.
        # Scale the external process allowance with the replay length; the
        # independent in-game frame limit and every assertion remain intact.
        wall_limit=max(600 if args.checkpoints else 450,round(frame_limit/60.099*3)+60)
        result=subprocess.run([str(args.mesen),'--testrunner',f'--timeout={wall_limit}',str(base/'adofai.sfc'),str(ROOT/'tools'/script)],env=env,cwd=ROOT,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0,timeout=wall_limit+30,capture_output=True,text=True)
        (out/'emulator.log').write_text(result.stdout+result.stderr)
        report=out/'result.txt'
        if not report.exists():raise RuntimeError(f'Mesen exited {result.returncode} without a result; see {out / "emulator.log"}\n'+result.stdout[-2000:]+result.stderr[-2000:])
        text=report.read_text();print(chart['code']+': '+text.splitlines()[0],flush=True)
        assert identity(base/'adofai.sfc')==loaded_identity,'ROM or MSU data changed during Mesen verification'
        assert suite_digest()==loaded_suite,'Verification code changed during the replay'
        samples=re.search(r'palette_samples=(\d+)',text)
        overruns=re.search(r'vblank_overruns=(\d+)',text)
        (out/'manifest.json').write_text(json.dumps(dict(code=chart['code'],sha256=digest,**loaded_identity,suite_version=2,suite_digest=loaded_suite,graphics_dumps=args.graphics_dumps,sampled_graphics=args.sampled_graphics,passed=False,summary=text.splitlines()[0],speed=speed/10,time_attack=args.time_attack,vfx_off=args.vfx_off,track_palette_samples=int(samples[1]) if samples else 0,vblank_overruns=int(overruns[1]) if overruns else None),indent=2))
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
                spans=[(n['step'],chart['notes'][i+1]['frame']-n['frame']) for i,n in enumerate(chart['notes'][:-1]) if n.get('hold_length',-1)>=0]
                minimum=min(100,max(1,sum(duration for _,duration in spans)//6)) if chart.get('mode1_tracks') else 1
                assert count>=minimum,f'Insufficient hold checks: {coverage}: {count} < {minimum}'
                if name=='hold-orbits.txt':
                    checked=dict((int(a),int(b)) for a,b in re.findall(r'(\d+)=(\d+)',(out/'hold-coverage.txt').read_text()))
                    assert all(checked.get(step,0)>0 for step,duration in spans if duration>=12),'An observable hold was never checked'
        if args.graphics_dumps and chart.get('neo_math_questions'):
            coverage=out/'math-labels.txt'
            assert coverage.exists() and int(re.search(r'samples=(\d+)',coverage.read_text())[1])>100,'Missing live math-label coverage'

        verified=json.loads(manifest.read_text());verified['passed']=True;manifest.write_text(json.dumps(verified,indent=2))

if __name__=='__main__':main()
