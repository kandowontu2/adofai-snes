"""Sequential MSU animation events and fast checkpoint state snapshots."""
import bisect,collections,struct

def full_cell_coordinates(out,chart):
    """Recover world coordinates from the sparse map, including cached builds."""
    cells=chart['visibility_cells'];coordinates=[None]*cells
    data=(out/f'track_map{chart["id"]}.bin').read_bytes();shift=chart.get('map_offset_shift',0)
    for y in range(chart['map_height']):
        row=struct.unpack_from('<H',data,y*2)[0]<<shift
        first,count=data[row:row+2]
        for chunk in range(count):
            pos=struct.unpack_from('<H',data,row+2+chunk*2)[0]<<shift;x=(first+chunk)*32
            while data[pos]:
                length,value=struct.unpack_from('<BH',data,pos);pos+=3
                if value&0x2000:
                    index=(value&0x1fff)|((value&0xc000)>>1)
                    assert length==1,('A dynamic cell must have a unique world coordinate',index,length)
                    coordinates[index]=[x,y]
                x+=length
    assert all(v is not None for v in coordinates)
    return coordinates

def coordinate_index(chart, *, wrapped=False):
    coordinates=chart.get('cell_coordinates',[])
    if wrapped:
        values=[((y&127)<<7)|(x&127) for x,y in coordinates]
        return struct.pack('<'+'H'*len(values),*values) if values else bytes(2)
    values=[p[0] for p in coordinates]+[p[1] for p in coordinates]
    return struct.pack('<'+'H'*len(values),*values) if values else bytes(4)

def spatial_cells(out,chart):
    """Put dynamic cells in world-row order without rerasterizing their pixels."""
    if chart.get('spatial_cell_order')==1:return
    coords=full_cell_coordinates(out,chart);count=len(coords)
    order=sorted(range(count),key=lambda i:(coords[i][1],coords[i][0]))
    remap={old:new for new,old in enumerate(order)}
    offsets=chart['visibility_offsets']
    chart['visibility_offsets']=[offsets[i] for i in order]+offsets[count:]
    chart['cell_coordinates']=[coords[i] for i in order]
    path=out/f'track_map{chart["id"]}.bin';data=bytearray(path.read_bytes());seen=set();shift=chart.get('map_offset_shift',0)
    for y in range(chart['map_height']):
        row=struct.unpack_from('<H',data,y*2)[0]<<shift
        for chunk in range(data[row+1]):
            pos=struct.unpack_from('<H',data,row+2+chunk*2)[0]<<shift
            if pos in seen:continue
            seen.add(pos)
            while data[pos]:
                value=struct.unpack_from('<H',data,pos+1)[0]
                if value&0x2000:
                    index=remap[(value&0x1fff)|((value&0xc000)>>1)]
                    struct.pack_into('<H',data,pos+1,0x2000|(index&8191)|((index&24576)<<1))
                pos+=3
    path.write_bytes(data);chart['spatial_cell_order']=1

def generate(out,chart,timeline,patterns):
    n=chart['id'];count=len(chart['notes']);cells=chart.get('visibility_cells',0);mode7=chart.get('mode7',False)
    assert cells<=26112,('MSU cell-state capacity',chart['code'],cells)
    if mode7 and not chart.get('projection_source_only'):
        # Runtime checkpoint reloads reserve FE00..FEFF as temporary,
        # unique identities for snapshot pixels whose source IDs are absent.
        assert len(patterns)//64<=0xFE00,('Reserved checkpoint pattern IDs',chart['code'])
    events=[]
    compiled_refs=bool(mode7 and chart.get('compiled_reference_sets'))
    if n==60 and chart.get('bitmap_prefetch_versions'):
        for frame,bitmap,deadline,end in chart['bitmap_prefetch_versions']:
            events.append((frame,24,bitmap,deadline,struct.pack('<H',end)+patterns[bitmap*64:bitmap*64+64]))
    if chart.get('global_pattern_references'):events.append((0,12,0,2 if compiled_refs else 1,b''))
    if mode7 and (not chart.get('cell_coordinates') or isinstance(chart['cell_coordinates'][0],int)):
        chart['cell_coordinates']=full_cell_coordinates(out,chart)
    if mode7:spatial_cells(out,chart)
    def node(index,kind,target):
        offset=chart['visibility_offsets'][index];length=struct.unpack_from('<H',timeline,offset)[0]
        for j in range(length):
            frame,value=struct.unpack_from('<HH',timeline,offset+2+4*j)
            events.append((frame,kind,target,value,b''))
    for i in range(cells):node(i,0,i)
    for i,versions in enumerate(chart.get('visibility_floor_versions',[])):
        for frame,value in versions:events.append((frame,1,i,value,b''))
    if chart.get('moving_tiles'):
        for axis in range(2):
            for i in range(count):
                if chart['notes'][i].get('stick_to_floor',True):
                    node(cells+count*(axis+1)+i,2+axis,i)
    for slot,versions in enumerate([] if chart.get('projection_source_only') else chart.get('pattern_versions',[])):
        for frame,value in versions:
            size=64 if mode7 else 16
            events.append((frame,4,slot,value,patterns[value*size:value*size+size]))
    if chart.get('mode7_zoom_enabled'):
        for frame,z,inv in chart['camera_zoom_versions']:
            events.append((frame,6,z&65535,inv&65535,b''))
        for frame,c,s in chart['camera_projection_versions']:
            events.append((frame,15,c&65535,s&65535,b''))
    for frame,shift in chart.get('camera_raster_shift_versions',[]):
        events.append((frame,16,shift,0,b''))
    for frame,x,y in chart.get('raster_origin_versions',[]):
        events.append((frame,23,x,y,b''))
    for frame,index,value in chart.get('track_palette_versions',[]):
        events.append((frame,7,index,value,b''))
    for frame,x,y in chart.get('camera_follow_versions',[]):
        events.append((frame,10,x&65535,y&65535,b''))
    for frame,c,s in chart.get('camera_sampling_versions',chart.get('camera_rotation_versions',[])):
        events.append((frame,11,c&65535,s&65535,b''))
    last_phase=None
    for frame,phase in chart.get('camera_rotation_phase_versions',[]):
        if phase!=last_phase:events.append((frame,13,phase,0,b''));last_phase=phase
    if mode7:
        # Event icons obey the original floor opacity, independently of the
        # raster's spatial clipping. Do not scan hidden symbols each frame.
        symbol_ids=[i for i,note in enumerate(chart['notes'])
                    if note.get('flags',0)&119 and not note.get('flags',0)&128]
        symbol_changes=collections.defaultdict(dict)
        for i in symbol_ids:
            for frame,alpha in chart['visibility_floor_versions'][i]:
                symbol_changes[frame][i]=bool(alpha)
        alive=set(symbol_ids);previous=None
        for frame,updates in sorted(symbol_changes.items()):
            for i,shown in updates.items():
                if shown:alive.add(i)
                else:alive.discard(i)
            value=tuple(sorted(alive))
            if value!=previous:
                payload=struct.pack('<'+'H'*len(value),*value)
                events.append((frame,28,0,len(payload),payload));previous=value
    if mode7:
        references=collections.defaultdict(list)
        releases=collections.defaultdict(list)
        active=collections.Counter();state=[0]*cells
        cell_events=collections.defaultdict(list)
        for frame,kind,index,value,data in events:
            if kind==0:cell_events[frame].append((index,value))
        previous_slots=None
        for frame,updates in sorted(cell_events.items()):
            touched=set()
            for index,value in updates:
                old=state[index]
                if old:active[old]-=1;touched.add(old)
                if value:active[value]+=1;touched.add(value)
                state[index]=value
            for slot in touched:
                if not active[slot]:releases[slot].append(frame)
            if compiled_refs:
                slots=bytes([0]+sorted(slot for slot,num in active.items() if num>0))
                if slots!=previous_slots:
                    events.append((frame,14,0,len(slots),slots))
                    previous_slots=slots
        for frame,kind,index,value,data in events:
            if kind==0 and value:references[value].append(frame)
        for rows in references.values():rows.sort()
        for i,(frame,kind,index,value,data) in enumerate(events):
            if kind==4:
                rows=references[index];at=bisect.bisect_left(rows,frame)
                deadline=rows[at] if at<len(rows) else 65534
                rows=releases[index];at=bisect.bisect_right(rows,frame)-1
                release=rows[at] if at>=0 else 0
                events[i]=(frame,kind,index,value,struct.pack('<HH',deadline,release)+data)
    # Clear departing cells before inserting arriving cells. World coordinates
    # alias in the 128x128 hardware map after large camera translations.
    events.sort(key=lambda e:(e[0],-2 if e[1]==12 else -1 if e[1]==4 else e[1],bool(e[3]) if e[1]==0 else False,e[2],e[3]));blob=bytearray();positions=[]
    cursor=0
    while cursor<len(events):
        frame,kind,index,value,data=events[cursor];end=cursor+1
        if kind==0:
            while end<len(events) and end-cursor<128 and events[end][0]==frame and events[end][1]==0 and events[end][2]==index+end-cursor:
                if mode7:
                    x,y=chart['cell_coordinates'][index];nx,ny=chart['cell_coordinates'][events[end][2]]
                    if ny!=y or nx!=x+end-cursor:break
                end+=1
        elif kind==7:
            while end<len(events) and events[end][0]==frame and events[end][1]==7:end+=1
        if kind==7 and end-cursor>=3:
            positions.extend([len(blob)]*(end-cursor))
            blob+=struct.pack('<HBHH',frame,8,0,end-cursor)
            blob+=b''.join(struct.pack('<BH',e[2],e[3]) for e in events[cursor:end])
        elif kind==0 and end-cursor>=3:
            positions.extend([len(blob)]*(end-cursor))
            blob+=struct.pack('<HBHH',frame,9 if mode7 else 5,index,end-cursor)
            if mode7:blob+=struct.pack('<HH',*chart['cell_coordinates'][index])+bytes(e[3] for e in events[cursor:end])
            else:blob+=struct.pack('<'+'H'*(end-cursor),*(e[3] for e in events[cursor:end]))
        else:
            end=cursor+1;positions.append(len(blob));blob+=struct.pack('<HBHH',frame,kind,index,value)+data
        cursor=end
    positions.append(len(blob));blob+=struct.pack('<HBHH',65535,255,0,0)
    if mode7 and n in (66,71):
        # Long moving hold paths otherwise send each short map row as a
        # separate CPU job. Preserve order and checkpoint entry positions.
        from animation_map_batch import batch
        blob,mapping=batch(blob,chart)
        positions=[mapping[p] for p in positions]
        chart['map_batch_format']=1
    (out/f'animation{n}.bin').write_bytes(blob)
    state=[0]*cells;alpha=[3]*count;xs=[x['x']+(x.get('position_track_offset',[0,0])[0] if not x.get('stick_to_floor',True) else 0) for x in chart['notes']];ys=[x['y']+(x.get('position_track_offset',[0,0])[1] if not x.get('stick_to_floor',True) else 0) for x in chart['notes']];chr_slots=[0]*(256 if mode7 else 1024);cursor=0;zoom=inverse=256;palette=[0]*96;camera_x=camera_y=256;rotation_c=256;rotation_s=rotation_phase=0;projection_c=256;projection_s=0;raster_shift=0
    origin_x=origin_y=0
    for at,i,cp in sorted((max(0,c['origin_frame']-32),i,c) for i,c in enumerate(chart['checkpoints'])):
        while cursor<len(events) and events[cursor][0]<=at:
            frame,kind,index,value,data=events[cursor]
            if kind==0:state[index]=value
            elif kind==1:alpha[index]=value
            elif kind==2:xs[index]=value
            elif kind==3:ys[index]=value
            elif kind==4:chr_slots[index]=value
            elif kind==6:zoom,inverse=index,value
            elif kind==15:projection_c,projection_s=index,value
            elif kind==16:raster_shift=index
            elif kind==7:palette[index]=value
            elif kind==10:camera_x,camera_y=index,value
            elif kind==11:rotation_c,rotation_s=index,value
            elif kind==13:rotation_phase=index
            elif kind==23:origin_x,origin_y=index,value
            cursor+=1
        words=lambda values:struct.pack('<'+'H'*len(values),*values)
        # Static worlds need no mutable CHR image. Cached worlds store the
        # currently prefetched slots, so a retry needs one linear DMA read.
        image=(b''.join(patterns[p*64:p*64+64] for p in chr_slots) if mode7 else b''.join(patterns[p*16:p*16+16]+bytes(16) for p in chr_slots)) if chart.get('pattern_versions') else b''
        phase=bool(chart.get('reuse_motion_phase'))
        snapshot=((b'ADS9' if phase else b'ADS8' if chart.get('adaptive_raster') else b'ADS7' if chart.get('mode7_zoom_enabled') else b'ADS6' if chart.get('camera_rotation_versions') else b'ADS5') if mode7 else b'ADS1')+struct.pack('<IHHH',positions[cursor],cells,count,len(image))
        camera_extra=(words([rotation_c,rotation_s,rotation_phase,zoom,inverse,
                            projection_c if chart.get('mode7_zoom_enabled') else rotation_c,
                            projection_s if chart.get('mode7_zoom_enabled') else rotation_s,
                            raster_shift,origin_x,origin_y]) if phase else
                      words([rotation_c,rotation_s,rotation_phase,zoom,inverse,projection_c,projection_s]+([raster_shift] if chart.get('adaptive_raster') else [])) if chart.get('mode7_zoom_enabled') else
                      words([rotation_c,rotation_s,rotation_phase]) if chart.get('camera_rotation_versions') else b'')
        snapshot+=(struct.pack('<HH',camera_x,camera_y)+camera_extra+words(palette)+bytes(state) if mode7 else words(state))+words(xs)+words(ys)+bytes(alpha)+image
        (out/f'animation{n}-checkpoint-{i}.bin').write_bytes(snapshot)
    chart['animation_bytes']=len(blob)
    chart['animation_streamed']=True
    chart['animation_format']=(14 if chart.get('reuse_motion_phase') else 13 if chart.get('adaptive_raster') else 12 if chart.get('mode7_zoom_enabled') else 11 if chart.get('camera_rotation_versions') else 10) if mode7 else 2
