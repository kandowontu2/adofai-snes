"""Pixel-exact OBJ overflow for rotated Mode 7 pattern-pressure frames.

The PPU sampler is shared with viewport validation. Only cells exceeding the
BG atlas are removed; their sampled pixels are emitted as screen-space OBJ.
"""
import collections
import struct
import numpy as np
from viewport_cells import sampled_pixels
from mode1_tracks import encode_tile,decode_tile


def split(chart,tiles,history):
    events=collections.defaultdict(dict)
    for xy,rows in history.items():
        for f,p in rows:events[f][xy]=p
    cameras={f:(x,y) for f,x,y in chart['camera_follow_versions']}
    rotations={f:(c,s) for f,c,s in chart.get('camera_sampling_versions',chart.get('camera_rotation_versions',[]))}
    palette_writes=collections.defaultdict(list)
    for f,i,v in chart['track_palette_versions']:palette_writes[f].append((32+i,v))
    live={};palette={};camera=cameras[0];rotation=(256,0);prior={};result={};frames=[];was_active=False
    for f in sorted(set(events)|set(cameras)|set(rotations)|set(palette_writes)):
        if f>=chart['notes'][-1]['frame']:break
        live.update(events.get(f,{}));camera=cameras.get(f,camera);rotation=rotations.get(f,rotation)
        palette.update(palette_writes.get(f,[]))
        by_pattern=collections.defaultdict(list)
        for xy,p in live.items():
            if p:by_pattern[p].append(xy)
        selected=set();selected_order=[];colors=set()
        # Smallest screen footprints first. Pattern sharing already retained
        # every possible pixel-exact BG alias before reaching this path.
        previous_bg=set(prior.values())-{0}
        for p in sorted(by_pattern,key=lambda p:(p in previous_bg,len(by_pattern[p]),(p*2654435761)&0xffffffff)):
            # Retain thirty-one free BG slots so a new scene can preload without
            # overwriting the still-displayed scene's patterns.
            if len(by_pattern)-len(selected)<=192:break
            swatches={palette[v] for v in tiles[p] if v}
            if len(colors|swatches)>15:continue
            selected.add(p);selected_order.append(p);colors|=swatches
        assert len(by_pattern)-len(selected)<=255,('Projected spill color capacity',chart['code'],f)
        masked={xy for p in selected for xy in by_pattern[p]}
        if selected:
            top=chart.get('viewport_top',32);bottom=chart.get('viewport_bottom',176)
            px,py=sampled_pixels(*camera,*rotation,chart.get('viewport_center_y',104),bottom,top)
            while True:
                colors={palette[v] for p in selected for v in tiles[p] if v}
                canvas=np.zeros((256,256),dtype=np.uint8);swatches=sorted(colors);lookup={v:i+1 for i,v in enumerate(swatches)}
                for wx,wy in masked:
                    ys,xs=np.where((px//8==wx)&(py//8==wy));raw=tiles[live[wx,wy]]
                    for y,x in zip(ys,xs):
                        value=raw[int(px[y,x]&7)+8*int(py[y,x]&7)]
                        if value:canvas[y+top+1,x]=lookup[palette[value]]
                objects=[];glyphs=[];ids={};lines=[0]*32
                for y in range(24,184,8):
                    for x in range(0,256,8):
                        pixels=canvas[y:y+8,x:x+8].tobytes()
                        if not any(pixels):continue
                        glyph=encode_tile(pixels,list(range(1,len(swatches)+1)))
                        assert decode_tile(glyph,list(range(1,len(swatches)+1)))==pixels
                        if glyph not in ids:ids[glyph]=len(glyphs);glyphs.append(glyph)
                        objects.append([x,y,ids[glyph]]);lines[y//8]+=1
                if len(masked)<=120 and len(objects)<=112 and len(glyphs)<=128 and max(lines)<=20:break
                assert len(by_pattern)-len(selected)<255,('Projected spill OAM capacity',chart['code'],f,len(objects),max(lines))
                selected.remove(selected_order.pop())
                masked={xy for p in selected for xy in by_pattern[p]}
            frames.append(dict(frame=f,origin=list(camera),cells=sorted(masked),palette=swatches,
                               glyphs=b''.join(glyphs).hex(),objects=objects))
        elif was_active:
            frames.append(dict(frame=f,origin=list(camera),cells=[],palette=[],glyphs='',objects=[]))
        current={xy:(0 if xy in masked else p) for xy,p in live.items() if p}
        for xy in prior.keys()|current.keys():
            p=current.get(xy,0)
            if p!=prior.get(xy,0):result.setdefault(xy,[]).append((f,p))
        prior=current;was_active=bool(selected)
    chart['projected_spill_frames']=frames
    chart['projected_spill_compact']=True
    return result


def stable_glyphs(frames):
    """Retain OBJ atlas positions across frames, with no pixel resampling."""
    result=[];first=0
    while first<len(frames):
        end=first
        while end<len(frames) and frames[end]['objects']:end+=1
        if first==end:result.append(frames[first]);first+=1;continue
        capacity=max(len(bytes.fromhex(f['glyphs']))//32 for f in frames[first:end])
        cache=[bytes(32)]*capacity
        for original in frames[first:end]:
            frame=dict(original);raw=bytes.fromhex(frame['glyphs']);required=[raw[i:i+32] for i in range(0,len(raw),32)]
            retained={g:cache.index(g) for g in required if g in cache}
            missing=list(dict.fromkeys(g for g in required if g not in retained))
            free=[i for i in range(capacity) if i not in retained.values()]
            if missing:
                count=len(missing)
                start=min(range(len(free)-count+1),key=lambda j:free[j+count-1]-free[j])
                for i,g in zip(free[start:start+count],missing):cache[i]=g;retained[g]=i
            frame['glyphs']=b''.join(cache).hex()
            frame['objects']=[[x,y,retained[required[g]]] for x,y,g in frame['objects']]
            result.append(frame)
        first=end
    return result


def append_packets(chart,animation):
    """Use the existing atomic OBJ packet ABI; canonical BG is already masked."""
    from animation_bulk import HEADER,records
    rows=[(t,animation[a:b]) for a,b,t,k,i,v in records(animation) if k!=255]
    images={b'':0};previous=b''
    for frame in stable_glyphs(chart.get('projected_spill_frames',[])):
        f=frame['frame'];glyphs=bytes.fromhex(frame['glyphs']);objects=frame['objects'];cells=frame['cells']
        if glyphs not in images:images[glyphs]=len(images)
        palette=frame['palette']+[0]*(15-len(frame['palette']))
        body=struct.pack('<HH15H',len(glyphs)//32,images[glyphs],*palette)
        compact=chart.get('projected_spill_compact',False)
        body+=b''.join(struct.pack('<hh',x*8,y*8) if compact else struct.pack('<hhH',x*8,y*8,0) for x,y in cells)+glyphs
        lines=[0]*32
        for x,y,g in objects:lines[y//8]+=1
        body+=struct.pack('<hhHH',*frame['origin'],len(objects),0)+bytes(lines)
        body+=b''.join(bytes([x,y,g,0x21]) for x,y,g in objects)
        if glyphs:
            changed=[j for j,v in enumerate(glyphs) if j>=len(previous) or v!=previous[j]]
            start=(changed[0]//32)*32 if changed else 0
            end=((changed[-1]//32)+1)*32 if changed else len(glyphs)
            rows.append((f,HEADER.pack(f,35,images.get(previous,65535),end-start)+struct.pack('<H',start)))
        rows.append((f,HEADER.pack(f,22,len(cells)|(0x8000 if compact else 0),len(body))+body))
        previous=glyphs
    rows.sort(key=lambda row:row[0])
    return b''.join(v for _,v in rows)+HEADER.pack(65535,255,0,0)
