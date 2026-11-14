"""Lossless OBJ offload for dense, unrotated inline Mode 7 scenes."""
import bisect,collections,struct
from animation_bulk import HEADER
from animation_catchup import unpack_events
from mode1_tracks import encode_tile,decode_tile


def compile_spills(chart, animation, patterns, initial_map, max_objects=80, lookahead=0):
    groups=collections.defaultdict(list)
    for event in unpack_events(animation,chart):groups[event[0]].append(event)
    writes=collections.defaultdict(list)
    for t,events in groups.items():
        for _,kind,slot,_,_ in events:
            if kind==4:writes[slot].append(t)
    coordinates=[tuple(p) for p in chart['cell_coordinates']]
    cell_ids={p:i for i,p in enumerate(coordinates)}
    tags=list(chart['pattern_initial']);loaded=list(tags);world=dict(initial_map)
    palette=[0]*96;palettes=collections.defaultdict(list)
    for t,i,v in chart['track_palette_versions']:palettes[t].append((i,v))
    views={int(t):v for t,v in chart['render_viewports'].items()}
    transforms={int(t):v for t,v in chart['render_transforms'].items()}
    view=views[0];transform=transforms[0];active={0}
    prior_raw=set();prior_cells=set();prior_payload=None;prior_glyphs=b''
    palette_slots=[None]*15;glyph_slots=[];source_slots={}
    out=bytearray();stats=collections.Counter();image_ids={b'':0}
    last_bg=[-1]*256;last_write=[-1]*256;repairs=[]
    checkpoint_windows=[(max(0,cp['origin_frame']-32),cp['origin_frame'])
                        for cp in chart.get('checkpoints',[])]
    def repair_time(earliest,needed):
        # Checkpoint bootstrap restores canonical pixels, not speculative
        # stream uploads. Reissue a crossing upload when it becomes needed
        # instead of letting bootstrap silently discard its only copy.
        if any(earliest<end and needed>=start for start,end in checkpoint_windows):
            return needed
        return earliest
    last=max(groups)
    for frame in range(last+1):
        events=groups.get(frame,[])
        for _,kind,i,v,p in events:
            if kind in (4,27):tags[i]=v
            elif kind==9:
                x,y,slot=struct.unpack('<HHB',p);world[x,y]=slot
            elif kind==14:active=set(p)
        for i,v in palettes.get(frame,[]):palette[i]=v
        view=views.get(frame,view);transform=transforms.get(frame,transform)
        x,y,w,h=view;cells=collections.defaultdict(list)
        for wy in range(y,y+h):
            for wx in range(x,x+w):
                slot=world.get((wx,wy),0)
                if slot:cells[slot].append((wx,wy))
        visible_raw={tags[slot] for slot in cells}
        changed=visible_raw-prior_raw;prior_raw=visible_raw
        dense=frame>0 and len(changed)>=chart.get("stream_spill_threshold",32)
        selected=[];swatches=set();used=0;rows=collections.Counter()
        if tuple(transform[:2])==(256,0):
            upcoming={}
            if lookahead:
                for slot in cells:
                    times=writes[slot];j=bisect.bisect_right(times,frame)
                    if j<len(times) and times[j]<=frame+lookahead:upcoming[slot]=times[j]
            candidates=[slot for slot,pts in cells.items()
                        if (dense and tags[slot] in changed) or slot in upcoming or prior_cells.intersection(pts)]
            candidates.sort(key=lambda slot:(tags[slot] not in changed,
                            upcoming.get(slot,65536),
                            not bool(prior_cells.intersection(cells[slot])),len(cells[slot]),slot))
            for slot in candidates:
                pts=cells[slot];raw=patterns[tags[slot]*64:(tags[slot]+1)*64]
                colors={palette[p-32] for p in raw if p}
                counts=collections.Counter(y for x,y in pts);trial=rows+counts
                if used+len(pts)>max_objects or len(swatches|colors)>15:continue
                # Bound adjacent rows for every possible sub-tile camera phase.
                # Leave twelve objects per coarse scanline bucket for gameplay.
                if any(trial[y]+trial[y+1]>20 or trial[y]+trial[y-1]>20 for y in counts):continue
                selected.append(slot);swatches|=colors;used+=len(pts);rows=trial
        colors=sorted(swatches);lookup={v:i+1 for i,v in enumerate(colors)}
        stable=chart.get('stream_spill_stable_trial',False)
        if stable:
            # Preserve color indices and unchanged glyph slots across frames.
            # Repacking them each time turns a small edit into a full upload.
            retained={v:i for i,v in enumerate(palette_slots) if v in swatches}
            free=[i for i,v in enumerate(palette_slots) if v not in swatches]
            # During fades the source CGRAM entries keep their meaning while
            # their RGB values change. Preserve those indices where possible,
            # so a palette change does not needlessly rewrite every OBJ glyph.
            votes=collections.defaultdict(collections.Counter)
            for slot in selected:
                raw=patterns[tags[slot]*64:(tags[slot]+1)*64]
                for p,count in collections.Counter(raw).items():
                    if p in source_slots:
                        votes[palette[p-32]][source_slots[p]]+=count*len(cells[slot])
            for color in colors:
                if color not in retained:
                    index=max(free,key=lambda i:(votes[color][i],-i))
                    free.remove(index);palette_slots[index]=color;retained[color]=index
            lookup={v:i+1 for v,i in retained.items()}
            source_slots={p:retained[palette[p-32]] for slot in selected
                          for p in patterns[tags[slot]*64:(tags[slot]+1)*64] if p}
        encoded=[]
        for slot in selected:
            raw=patterns[tags[slot]*64:(tags[slot]+1)*64]
            indexed=bytes(lookup[palette[p-32]] if p else 0 for p in raw)
            indices=list(range(1,16 if stable else len(colors)+1))
            glyph=encode_tile(indexed,indices)
            assert decode_tile(glyph,indices)==indexed
            encoded.append((slot,glyph))
        glyphs=[];glyph_ids={};objects=[];selected_cells=set()
        if stable and encoded:
            required={glyph for _,glyph in encoded}
            glyphs=list(glyph_slots)
            glyph_ids={glyph:i for i,glyph in enumerate(glyphs) if glyph in required}
            free=[i for i in range(len(glyphs)) if i not in glyph_ids.values()]
            for _,glyph in encoded:
                if glyph in glyph_ids:continue
                if free:
                    index=free.pop(0);glyphs[index]=glyph
                else:index=len(glyphs);glyphs.append(glyph)
                glyph_ids[glyph]=index
        for slot,glyph in encoded:
            if glyph not in glyph_ids:glyph_ids[glyph]=len(glyphs);glyphs.append(glyph)
            for wx,wy in cells[slot]:
                objects.append((wx*8,wy*8,glyph_ids[glyph]));selected_cells.add((wx,wy))
        selected=set(selected)
        if stable:glyph_slots=list(glyphs)
        for t,kind,i,v,p in events:
            if kind==14:continue
            if kind==9 and struct.unpack_from('<HH',p) in prior_cells|selected_cells:
                # The final write below supersedes this one within the same
                # atomic scene. Avoid dirtying and translating it twice.
                continue
            if kind==4:
                if i in selected:
                    continue
                loaded[i]=v
                at=max(0,frame-lookahead,last_bg[i]+1,last_write[i]+1) if lookahead else frame
                repairs.append((at,HEADER.pack(at,kind,i,v)+p))
                last_write[i]=at
                if at<frame:stats['early_source_writes']+=1
                continue
            out+=HEADER.pack(t,kind,i,v)+p
        for slot in sorted(set(cells)-selected):
            if loaded[slot]==tags[slot]:continue
            tag=tags[slot]
            at=repair_time(max(0,frame-40,last_bg[slot]+1,last_write[slot]+1),frame)
            repairs.append((at,HEADER.pack(at,4,slot,tag)+struct.pack('<HBB',65535,0,64)+patterns[tag*64:(tag+1)*64]))
            last_write[slot]=at
            loaded[slot]=tag;stats['repairs']+=1
            if at<frame:stats['early_repairs']+=1
        for slot in set(cells)-selected:last_bg[slot]=frame
        assert all(loaded[slot]==tags[slot] for slot in set(cells)-selected)
        # Legacy packets reassert the full mask. Incremental packets rely on
        # the runtime's first-snapshot seed repair, then only change cells
        # entering/leaving OBJ. Retained masked cells remain exactly zero.
        for xy in sorted(prior_cells|selected_cells,key=lambda p:(p[1],p[0])):
            if chart.get('stream_spill_incremental_trial') and xy in prior_cells&selected_cells:
                continue
            value=0 if xy in selected_cells else world.get(xy,0)
            out+=HEADER.pack(frame,9,cell_ids[xy],1)+struct.pack('<HHB',*xy,value)
        if selected or prior_cells or any(e[1]==14 for e in events):
            bg=bytes(sorted((active-selected)|{0}))
            out+=HEADER.pack(frame,14,0,len(bg))+bg
        objects.sort(key=lambda p:(p[1],p[0]))
        glyph_blob=b''.join(glyphs)
        palette_blob=struct.pack('<15H',*([v or 0 for v in palette_slots] if stable else colors+[0]*(15-len(colors))))
        cells_blob=b''.join(struct.pack('<hhH',*obj) for obj in objects)
        identity=palette_blob+cells_blob,glyph_blob
        if selected_cells or prior_cells:
            # Each packet is self-contained after an arbitrary checkpoint seed.
            changed_glyphs=True
            if glyph_blob not in image_ids:image_ids[glyph_blob]=len(image_ids)
            assert len(image_ids)<=65535
            body=struct.pack('<HH',len(glyphs),image_ids[glyph_blob])+palette_blob+cells_blob+glyph_blob
            origin_x,origin_y=transform[2]-128,transform[3]-104
            packed=bytearray();negative=[];line_counts=[0]*32
            for wx,wy,glyph in objects:
                sx,sy=wx-origin_x,wy-origin_y
                if not (-7<=sx<256 and 25<=sy<177):continue
                if sx<0:negative.append(len(packed))
                for line in range(sy//8,(sy+7)//8+1):line_counts[line]+=1
                packed+=bytes([sx&255,sy,glyph,0x21])
            body+=struct.pack('<hhHH',origin_x,origin_y,len(packed)//4,len(negative)*2)
            body+=bytes(line_counts)+b''.join(struct.pack('<H',n) for n in negative)+packed
            assert len(negative)*2<=64, 'Spill negative-X metadata exceeds runtime storage'
            assert 40+len(negative)*2+len(packed)<=512, 'Spill snapshot exceeds runtime storage'
            if chart.get('stream_spill_delta_trial') and glyph_blob:
                changed=[j for j,v in enumerate(glyph_blob) if j>=len(prior_glyphs) or prior_glyphs[j]!=v]
                start=(changed[0]//32)*32 if changed else 0
                end=((changed[-1]//32)+1)*32 if changed else len(glyph_blob)
                out+=HEADER.pack(frame,35,image_ids.get(prior_glyphs,65535),end-start)+struct.pack('<H',start)
            out+=HEADER.pack(frame,22,len(objects),len(body))+body
            prior_payload=identity;prior_glyphs=glyph_blob
            stats['packets']+=1;stats['glyph_bytes']+=len(glyph_blob) if changed_glyphs else 0
        prior_cells=selected_cells
        if selected:
            stats['frames']+=1;stats['max_objects']=max(stats['max_objects'],len(objects))
            stats['max_colors']=max(stats['max_colors'],len(colors))
    from animation_bulk import records
    rows=[(t,out[a:b]) for a,b,t,k,i,v in records(bytes(out)+HEADER.pack(65535,255,0,0)) if k!=255]
    rows.extend(repairs);rows.sort(key=lambda row:row[0])
    out=bytearray(b''.join(blob for _,blob in rows))+HEADER.pack(65535,255,0,0)
    chart['stream_spill_stats']=dict(stats)
    return bytes(out)


def prepare_spills(folder,level,chart,animation):
    from verify_render import map_reader
    import bisect
    timeline=(folder/f'timeline{level}.bin').read_bytes()
    read=map_reader((folder/f'track_map{level}.bin').read_bytes(),chart['map_height'],chart.get('map_offset_shift',0))
    initial={}
    for xy in chart['cell_coordinates']:
        value=read(*xy)
        if value&0x2000:
            i=(value&8191)|((value&49152)>>1);off=chart['visibility_offsets'][i]
            n=struct.unpack_from('<H',timeline,off)[0]
            rows=list(struct.iter_unpack('<HH',timeline[off+2:off+2+n*4]))
            value=rows[0][1] if rows[0][0]==0 else 0
        initial[tuple(xy)]=value
    return compile_spills(chart,animation,(folder/f'patterns{level}.bin').read_bytes(),initial,
                          max_objects=chart.get('stream_spill_object_limit',80))
