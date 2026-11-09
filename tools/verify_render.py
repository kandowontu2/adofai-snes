"""Check loaded PPU graphics, circular track cache, target, and OBJ limits."""
import argparse,bisect,ctypes as C,hashlib,json,struct
from pathlib import Path
import numpy as np
from emulate import Emulator,ROOT
from input_helpers import configure,select_level,press

def inflate_chr(data,mode7=False):
    raw=bytearray();i=0
    while i<len(data):
        command=data[i];i+=1;count=(command&127)+1
        if command&128:raw.extend([data[i]]*count);i+=1
        else:raw.extend(data[i:i+count]);i+=count
    assert len(raw)%16==0
    if mode7:return bytes(raw)
    return b''.join(raw[i:i+16]+bytes(16) for i in range(0,len(raw),16))

def map_reader(data,height,shift=0):
    rows={};spans={}
    def tile(x,y):
        if y<0 or x<0 or y>=height:return 0
        row=struct.unpack_from('<H',data,y*2)[0]<<shift
        first,count=data[row:row+2];chunk=x//32
        if not first<=chunk<first+count:return 0
        pos=struct.unpack_from('<H',data,row+2+(chunk-first)*2)[0]<<shift
        if pos not in spans:
            values=[];p=pos
            while data[p]:
                count,value=struct.unpack_from('<BH',data,p);values.extend([value]*count);p+=3
            assert len(values)==32;spans[pos]=values
        return spans[pos][x%32]
    return tile

def verify_mode7(em,base,chart,tile,timeline,frames,stride=20,complete=False):
    """Compare the hardware's separate map/pixel bytes to authored time."""
    patterns=(base/f'patterns{chart["id"]}.bin').read_bytes()
    nodes=[]
    for offset in chart['visibility_offsets'][:chart['visibility_cells']]:
        count=struct.unpack_from('<H',timeline,offset)[0]
        rows=[struct.unpack_from('<HH',timeline,offset+2+i*4) for i in range(count)]
        nodes.append(([r[0] for r in rows],[r[1] for r in rows]))
    def resolved(value,at):
        if not value&0x2000:return value
        times,values=nodes[(value&0x1fff)|((value&0xc000)>>1)]
        i=bisect.bisect_right(times,at)-1
        return values[i] if i>=0 else 0
    versions=[([r[0] for r in rows],[r[1] for r in rows]) for rows in chart['pattern_versions']]
    color_versions=[[(0,0)] for _ in range(96)]
    for at,index,value in chart.get('track_palette_versions',[]):color_versions[index].append((at,value))
    color_versions=[([p[0] for p in rows],[p[1] for p in rows]) for rows in color_versions]
    samples=0;published_samples=0;max_objects=0;trails=flashes=False;zooms=set();checked_chr=False;clipped_differences=0;atomic_peak=0;deferrals=[]
    startup_frames=0;music_started=False;max_display_age=0
    # Sample-bank loading precedes the song clock. Keep validating its
    # displayed frames, but do not subtract that bounded loading time from
    # the complete-song playback allowance.
    for frame in range(frames+(1800 if complete else 0)):
        if frame>=frames+startup_frames:break
        em.run()
        if complete and not music_started:
            if em.read('music_active'):music_started=True
            elif em.read('state') in (0,1):
                startup_frames+=1
                assert startup_frames<1800,'Song did not start within 30 seconds'
        if 'mode7_cache_prepare' in em.labels and em.read('state')==em.read('display_state')==1:
            atomic=C.c_uint16.from_address(em.cache_ram+0x1fc5a).value
            atomic_peak=max(atomic_peak,atomic)
            errors=C.c_uint16.from_address(em.cache_ram+0x1fc90).value
            if errors>len(deferrals):deferrals.append(dict(frame=frame,atomic=atomic,step=em.read('step')))
        if em.read('state')!=1 or em.read('display_state')!=1:continue
        # Correct pixels in an indefinitely retained old scene are not a pass.
        # This two-second bound catches hangs; it is not a 60 FPS guarantee.
        if em.read('music_active'):
            age=(em.read('chart_time')-em.read('display_chart_time')) & 65535
            max_display_age=max(max_display_age,age)
            assert age<120,('Track presentation stalled',frame,age,em.snapshot())
        ready=bool(em.read('frame_ready'))
        # The real OAM is immutable on held frames; main's staging buffer
        # may currently be under construction.
        oam=np.frombuffer(C.string_at(em.ram+0x200,512),dtype=np.uint8).reshape(128,4) if ready else None
        if not ready:
            oam=np.zeros((128,4),dtype=np.uint8);oam[:,1]=240
        markers=oam[(oam[:,2]==8)&((oam[:,3]&14)==4)&(oam[:,1]<224)]
        assert not len(markers),('Removed upcoming circle appeared',frame,markers.tolist())
        diamonds=oam[(oam[:,2]==78)&((oam[:,3]&14)==14)&(oam[:,1]<224)]
        assert not len(diamonds),('Removed double-hit diamonds appeared',frame,diamonds.tolist())
        ys=oam[:,1].astype(int);ys=ys[ys<224]
        counts=np.convolve(np.bincount(ys,minlength=240),np.ones(16,dtype=int))[:224]
        max_objects=max(max_objects,int(max(counts)))
        assert max(counts)<=17,('PPU scanline tile limit',frame,max(counts))
        badges=oam[(oam[:,2]>=192)&(oam[:,2]<=206)&((oam[:,3]&14)==14)&(oam[:,1]<224)]
        assert not len(badges),('Removed numbered pointers appeared',frame,badges.tolist())
        trails|=bool(np.any((oam[:,2]>=128)&(oam[:,1]<224)))
        flashes|=bool(np.any(np.isin(oam[:,2],[42,44,46])&~np.isin(oam[:,3]&14,[8,10,12])&(oam[:,1]<224)))
        zooms.add(em.read('camera_zoom',True))
        if not chart.get('mode7_zoom_enabled'):
            assert em.read('camera_zoom')==em.read('camera_inverse')==256,('Fixed-scale chart changed zoom',frame,em.snapshot())
        if checked_chr and frame%stride:continue
        displayed=em.read('display_chart_time')
        video=em.core.retro_get_memory_data(3)
        actual=np.frombuffer(C.string_at(video,32768),dtype=np.uint8)
        indices=[values[bisect.bisect_right(times,displayed)-1] for times,values in versions]
        expected=b''.join(patterns[i*64:i*64+64] for i in indices)
        ppu_patterns=actual[1::2].tobytes()
        current=C.c_uint16.from_address(em.cache_ram+0x1fca4).value if 'mode7_landing_time' in em.labels else em.read('chart_time')
        physical=list(C.string_at(em.cache_ram+0x1f100,256)) if 'mode7_cache_prepare' in em.labels else list(range(256))
        if ready and chart.get('track_palette_versions'):
            palette=[values[bisect.bisect_right(times,current)-1] for times,values in color_versions]
            assert C.string_at(em.ram+0x1fa20,192)==struct.pack('<96H',*palette),('Track palette shadow is stale',frame,current)
        current_indices=[values[bisect.bisect_right(times,current)-1] for times,values in versions]
        current_image=C.string_at(em.ram+0xc800,14336)+C.string_at(em.ram+em.labels.get('M7_CHR_HIGH',0x1c000),2048)
        if ready:
            assert current_image==b''.join(patterns[i*64:i*64+64] for i in current_indices),('Mode 7 pattern downloads fell behind',frame,[(i,a,b) for i,(a,b) in enumerate(zip(current_image,b''.join(patterns[j*64:j*64+64] for j in current_indices))) if a!=b][:24],em.snapshot())
            published_samples+=1
        checked_chr=True
        # The entire CPU cache must be current, including prefetch beyond
        # the screen. Test the hardware map over its actually visible area.
        x=em.read('map_last_x',True);y=em.read('map_last_y',True)
        cache=C.string_at(em.cache_ram+0x18000,16384)
        if ready and frame%200==0:
            states=C.string_at(em.ram+0x10000,chart['visibility_cells'])
            if chart.get('global_pattern_references'):
                counts=np.bincount(np.frombuffer(states,dtype=np.uint8),minlength=256)
                counts[0]=0
                actual_counts=np.frombuffer(C.string_at(em.cache_ram+0x1fe00,512),dtype='<u2')
                if not chart.get('compiled_reference_sets'):
                    assert np.array_equal(actual_counts,counts),('Incorrect live-pattern counts',frame)
                active=C.c_uint16.from_address(em.cache_ram+0x1fc70).value
                logical=list(C.string_at(em.cache_ram+0x16b00,active))
                assert len(logical)==len(set(logical)) and set(logical)==set(np.flatnonzero(counts))|{0},('Incorrect active-pattern set',frame,logical)
            for i,(times,values) in enumerate(nodes):
                at=bisect.bisect_right(times,current)-1
                assert states[i]==(values[at] if at>=0 else 0),('Stale global tile state',frame,i,states[i])
            for wy in range(y,y+em.read('m7_old_height')):
                for wx in range(x,x+em.read('m7_old_width')):
                    address=(wy&127)*128+(wx&127);value=tile(wx,wy)
                    expected=resolved(value,current)
                    assert cache[address]==expected,('Stale Mode 7 CPU cache',frame,wx,wy,cache[address],expected,em.snapshot())
        zoom=abs(em.read('display_zoom',True))/256
        center=chart.get('viewport_center_y',96);half=chart.get('viewport_bottom',160)-center
        cx=em.read('display_cam_x',True)+128;cy=em.read('display_cam_y',True)+center
        shift=next((v for f,v in reversed(chart.get('camera_raster_shift_versions',[])) if f<=displayed),0)
        cx//=1<<shift;cy//=1<<shift
        # Native pixels occupy x=0..255 and y=32..159. The first pixel of
        # the next HUD band (y=160) and x=256 must not enter the live set.
        left,right=cx-128,cx+127;top,bottom=cy-half,cy+half-1
        rotation_c,rotation_s=256,0
        if em.sa1:
            rotation_c=C.c_int16.from_address(em.cache_ram+0x1fcb4).value
            rotation_s=C.c_int16.from_address(em.cache_ram+0x1fcb6).value
            expected_rotation=next(((c,s) for f,c,s in reversed(chart.get('camera_sampling_versions',chart.get('camera_rotation_versions',[]))) if f<=displayed),(256,0))
            expected_zoom=next(((z,i) for f,z,i in reversed(chart.get('camera_zoom_versions',[])) if f<=displayed),(256,256)) if chart.get('mode7_zoom_enabled') else (256,256)
            assert (em.read('display_zoom'),em.read('display_inverse'))==expected_zoom,('Displayed zoom disagrees with chart',frame,displayed,expected_zoom)
            assert (rotation_c,rotation_s)==expected_rotation,('Camera matrix disagrees with chart',frame,displayed,rotation_c,rotation_s,expected_rotation)
            ex=(128*abs(rotation_c)+half*abs(rotation_s)+255)//256
            ey=(half*abs(rotation_c)+128*abs(rotation_s)+255)//256
            left,right=cx-ex,cx+ex-1;top,bottom=cy-ey,cy+ey-1
        used={}
        if zoom:
            for wy in range(top//8,bottom//8+1):
                for wx in range(left//8,right//8+1):
                    address=((wy-(top//8&~(63 if em.sa1 else 31)))*128+wx-(left//8&~63)) if 'mode7_cache_sparse_map' in em.labels else ((wy-top//8)*128+wx-left//8) if 'mode7_cache_local_map' in em.labels else (wy&127)*128+(wx&127)
                    if em.sa1:
                        # Hysteresis keeps a valid coarse origin across turns.
                        bx=C.c_int16.from_address(em.cache_ram+0x1fcc8).value
                        by=C.c_int16.from_address(em.cache_ram+0x1fcca).value
                        address=(wy-by)*128+wx-bx
                    expected=resolved(tile(wx,wy),displayed)
                    assert 0<=address<16384,('Visible map outside PPU cache',frame,displayed,wx,wy,bx,by,cx,cy,{n:em.read(n) for n in ('vblank_first_time','vblank_first_queue','vblank_first_state')},list(np.frombuffer(C.string_at(em.cache_ram+0x1fca0,64),dtype='<u2')),em.snapshot())
                    assert actual[address*2]==physical[expected],('Stale visible Mode 7 PPU map',frame,wx,wy,int(actual[address*2]),physical[expected],expected,displayed,em.snapshot())
                    used.setdefault(expected,[]).append((wx,wy))
        for slot in used:
            reference=patterns[indices[slot]*64:indices[slot]*64+64]
            ppu_slot=physical[slot]
            actual_pattern=ppu_patterns[ppu_slot*64:ppu_slot*64+64]
            if actual_pattern!=reference:
                # A boundary tile can differ exclusively outside the
                # playfield while unused prefetch is still queued. Compare
                # every pixel actually exposed by each instance of it.
                visible_equal=True
                for wx,wy in used[slot]:
                    x0,x1=max(0,left-wx*8),min(8,right-wx*8+1)
                    y0,y1=max(0,top-wy*8),min(8,bottom-wy*8+1)
                    for py in range(y0,y1):
                        if actual_pattern[py*8+x0:py*8+x1]!=reference[py*8+x0:py*8+x1]:visible_equal=False
                if visible_equal:
                    clipped_differences+=1;continue
                matches=[i for i in range(len(patterns)//64) if patterns[i*64:i*64+64]==actual_pattern]
                nearby=[r for r in chart['pattern_versions'][slot] if displayed-30<=r[0]<=current+30]
                heap_count=em.read('m7_pattern_count')
                heap=np.frombuffer(C.string_at(em.cache_ram+0x1f000,heap_count*2),dtype='<u2')
                deadlines=np.frombuffer(C.string_at(em.cache_ram+0x1f200,512),dtype='<u2')
                pending=[(int(s),int(deadlines[s])) for s in heap[:12]]
                em.capture(base/f'verification/render-failure-{chart["id"]}-{em.read("speed_tenths")}.png')
                raise AssertionError(('Visible Mode 7 PPU pattern missing',frame,slot,displayed,
                                      dict(expected_pattern=indices[slot],actual_patterns=matches,nearby_versions=nearby,cells=used[slot],viewport=[left,top,right,bottom],pending_count=heap_count,pending=pending,slot_deadline=int(deadlines[slot]),staged_slots=em.read('pattern_slot'),map_rows=em.read('m7_row_count')),em.snapshot()))
        samples+=1
    assert checked_chr and samples and trails and not flashes,(checked_chr,samples,trails,flashes)
    result=dict(code=chart['code'],**em.evidence(),
                mode7=True,max_display_age=max_display_age,cache_samples=samples,max_objects_per_line=max_objects,ppu_chr_match=True,ppu_pattern_scope='visible track; unused prefetch may be pending',trails=trails,tile_flashes=flashes,
                zoom_values=len(zooms),clipped_pattern_differences=clipped_differences,visible_pixel_bounds=[0,chart.get("viewport_top",32),255,chart.get("viewport_bottom",160)-1],map_deferrals=em.read('m7_map_deferrals'),pattern_peak_queued=em.read('pattern_peak_queued'),
                vblank_overruns=em.read('pattern_vblank_overruns'),speed=em.read('speed_tenths')/10,
                final_state=em.read('state'),combo=em.read('combo'),expected_hits=chart['hits'],published_samples=published_samples)
    if result['vblank_overruns']:
        result['first_vblank_overrun']={name:em.read(name) for name in ('vblank_first_time','vblank_first_queue','vblank_first_state')}
        if em.sa1:
            result['first_vblank_overrun'].update(zip(('rows','span','slots','limit'),struct.unpack('<4H',C.string_at(em.cache_ram+0x1fcde,8))))
    assert result['pattern_peak_queued']<=32 and result['vblank_overruns']==0,result
    if 'mode7_cache_prepare' in em.labels:
        result.update(versioned_ppu_cache=True,cache_capacity_errors=C.c_uint16.from_address(em.cache_ram+0x1fc50).value,
                      cache_wait_frames=C.c_uint16.from_address(em.cache_ram+0x1fc52).value,
                      maximum_new_visible_patterns=C.c_uint16.from_address(em.cache_ram+0x1fc54).value)
        result.update(atomic_peak=atomic_peak,transition_deferrals=deferrals)
        assert result['cache_capacity_errors']==0,result
    if complete:
        assert result['final_state']==3 and result['combo']==chart['hits'],('Render replay did not complete',result,em.snapshot())
        result['completed_song']=True
    result['startup_frames']=startup_frames
    result['every_frame']=stride==1
    (base/'verification').mkdir(exist_ok=True)
    suffix='' if em.read('speed_tenths')==10 else f'-speed-{em.read("speed_tenths")}'
    (base/f'verification/render-{chart["id"]}{suffix}.json').write_text(json.dumps(result,indent=2))
    print(result)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--pack',default='main');ap.add_argument('--level',type=int,default=1)
    ap.add_argument('--frames',type=int);ap.add_argument('--speed',type=float,default=1.)
    ap.add_argument('--every-frame',action='store_true');args=ap.parse_args()
    base=ROOT/'build/campaign' if args.pack=='main' else ROOT/f'build/packs/{args.pack}'
    (base/'verification').mkdir(exist_ok=True)
    pack=json.loads((base/'pack.json').read_text());n=pack['levels'][args.level-1]
    chart=json.loads((base/f'level{n}.json').read_text())
    timeline=(base/f'timeline{n}.bin').read_bytes()
    def visible(value,frame):
        if not(value&0x2000):return value
        offset=chart['visibility_offsets'][(value&0x1fff)|((value&0xc000)>>1)]
        count=struct.unpack_from('<H',timeline,offset)[0];value=0
        for index in range(count):
            when,v=struct.unpack_from('<HH',timeline,offset+2+index*4)
            if when>frame:break
            value=v
        return value
    tile=map_reader((base/f'track_map{n}.bin').read_bytes(),chart['map_height'],chart.get('map_offset_shift',0))
    chrdata=inflate_chr((base/f'track_chr{n}.bin').read_bytes())
    patterns=(base/f'patterns{n}.bin').read_bytes() if chart.get('pattern_versions') else None
    em=Emulator(rom=base/'adofai.sfc');samples=0;max_objects=0;checked_chr=False;trails=False;flashes=False
    try:
        for _ in range(120):em.run()
        if args.speed!=1.:configure(em,round(args.speed*10))
        select_level(em,n)
        press(em,1);press(em,3)
        if chart.get('mode7'):
            verify_mode7(em,base,chart,tile,timeline,args.frames or round(chart['duration']*60.099/args.speed)+180,1 if args.every_frame else 20,not args.frames)
            return
        for frame in range(args.frames or round(chart['duration']*60.099)+180):
            em.run()
            if em.read('state')!=1 or not em.read('frame_ready'):continue
            oam=np.frombuffer(C.string_at(em.ram+0x200,512),dtype=np.uint8).reshape(128,4)
            markers=oam[(oam[:,2]==8)&((oam[:,3]&14)==4)&(oam[:,1]<224)]
            assert not len(markers),('Removed upcoming circle appeared',frame,markers.tolist())
            ys=oam[:,1].astype(int);ys=ys[ys<224]
            counts=np.convolve(np.bincount(ys,minlength=240),np.ones(16,dtype=int))[:224]
            max_objects=max(max_objects,int(max(counts)))
            assert max(counts)<=17,('PPU scanline tile limit',frame,max(counts))
            badges=oam[(oam[:,2]>=192)&(oam[:,2]<=206)&((oam[:,3]&14)==14)&(oam[:,1]<224)]
            assert len(badges)==0,('Removed numbered pointers appeared',frame,badges.tolist())
            trails|=bool(np.any((oam[:,2]>=128)&(oam[:,1]<224)))
            flashes|=bool(np.any(np.isin(oam[:,2],[42,44,46])&~np.isin(oam[:,3]&14,[8,10,12])&(oam[:,1]<224)))
            if not checked_chr or (patterns and frame%20==0):
                video=em.core.retro_get_memory_data(3)
                assert video and em.core.retro_get_memory_size(3)>=65536
                expected_chr=chrdata
                if patterns:
                    displayed=em.read('display_chart_time');raw=[]
                    for versions in chart['pattern_versions']:
                        index=0
                        for when,value in versions:
                            if when>displayed:break
                            index=value
                        raw.append(patterns[index*16:index*16+16]+bytes(16))
                    expected_chr=b''.join(raw)
                actual_chr=C.string_at(video,len(expected_chr))
                different=[i for i in range(len(expected_chr)//32) if actual_chr[i*32:i*32+32]!=expected_chr[i*32:i*32+32]]
                assert not different,('PPU track cache differs from scheduled bitmaps',frame,different[:12],{k:em.read(k) for k in ('display_chart_time','pattern_peak_queued','pattern_vblank_overruns','pattern_queue_count','pattern_dma_index') if k in em.labels},em.snapshot())
                checked_chr=True
            if frame%20:continue
            x=em.read('map_last_x');y=em.read('map_last_y')
            view=np.frombuffer(C.string_at(em.ram+0x1000,2048),dtype='<u2').reshape(32,32)
            for wy in range(y,y+24):
                for wx in range(x,x+32):
                    actual=int(view[wy&31,wx&31]);expected=visible(tile(wx,wy),em.read('chart_time'))
                    assert actual==expected,('Stale track cache',frame,wx,wy,actual,expected,em.snapshot())
            samples+=1
        assert checked_chr and samples>0 and trails and flashes,(checked_chr,samples,trails,flashes)
        result=dict(code=chart['code'],**em.evidence(),
                    cache_samples=samples,max_objects_per_line=max_objects,ppu_chr_match=checked_chr,trails=trails,tile_flashes=flashes)
        if 'pattern_peak_queued' in em.labels:
            result.update(pattern_peak_queued=em.read('pattern_peak_queued'),vblank_overruns=em.read('pattern_vblank_overruns'),first_overrun={k:em.read(k) for k in ('vblank_first_time','vblank_first_state','vblank_first_music','vblank_first_queue')})
            assert result['pattern_peak_queued']<=40,result
            assert result['vblank_overruns']==0,result
        (base/'verification').mkdir(exist_ok=True)
        (base/f'verification/render-{args.level}.json').write_text(json.dumps(result,indent=2))
        print(result)
    finally:em.close()

if __name__=='__main__':main()
