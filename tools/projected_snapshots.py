"""Independent, pixel-exact Mode 1 frames; no atlas lease dependencies."""
import json,struct,collections
from functools import lru_cache
from pathlib import Path
from animation_bulk import HEADER,records
from animation_catchup import unpack_events
from sa1_stream import indexed_packets,rom_index,LIMIT,SNAPSHOT_LIMIT
from projected_tracks import raw_seeds
from snapshot_codec import encode_ordered_split as encode

def trim_hidden_scanlines(glyphs,frames,*,map_top=32,bottom=176):
    """Retain every displayed pixel, including the last y+1 raster line."""
    lookup={raw:i for i,raw in enumerate(glyphs)};cache={};seen=set()
    for refs,_ in frames:
        if id(refs) in seen:continue
        seen.add(id(refs))
        for cell,(glyph,bank) in list(refs.items()):
            first=map_top+(cell//32)*8
            rows=tuple(r for r in range(8) if map_top+1<=first+r<=bottom)
            if len(rows)==8:continue
            if not rows:del refs[cell];continue
            key=(glyph,bank&32,rows)
            if key not in cache:
                raw=glyphs[glyph];masked=bytearray(len(raw))
                for row in rows:
                    at=(7-row if bank&32 else row)*2
                    for plane in range(0,len(raw),16):
                        masked[plane+at:plane+at+2]=raw[plane+at:plane+at+2]
                masked=bytes(masked)
                if not any(masked):cache[key]=0
                else:
                    if masked not in lookup:lookup[masked]=len(glyphs);glyphs.append(masked)
                    cache[key]=lookup[masked]
            if cache[key]:refs[cell]=(cache[key],bank)
            else:del refs[cell]

@lru_cache(maxsize=131072)
def decoded_glyph(raw,palette,indexed):
    import numpy as np
    from mode1_tracks import decode_tile
    if not indexed:return np.frombuffer(decode_tile(raw,palette),dtype=np.uint8).reshape(8,8)
    tile=np.zeros((8,8),dtype=np.uint8)
    for plane in range(8):
        at=(plane//2)*16+plane%2
        row=np.frombuffer(raw[at:at+16:2],dtype=np.uint8)
        tile|=(((row[:,None]>>np.arange(7,-1,-1))&1)<<plane).astype(np.uint8)
    return tile


def frame_pixels(refs,palettes,glyphs,*,map_top=32):
    """Decode source indices independently of a frame's local atlas slots."""
    import numpy as np
    from mode1_tracks import decode_tile
    image=np.zeros((184,256),dtype=np.uint8)
    for cell,(glyph,bank) in refs.items():
        if not glyph:continue
        raw=glyphs[glyph]
        tile=decoded_glyph(raw,() if bank&64 else tuple(palettes[bank&15]),bool(bank&64))
        if bank&16:tile=tile[:,::-1]
        if bank&32:tile=tile[::-1,:]
        y,x=divmod(cell,32);image[map_top+y*8:map_top+y*8+8,x*8:x*8+8]=tile
    return image


def repack_frame(refs,palettes,glyphs,*,map_top=32,limit=640):
    """Share exact geometric glyphs across differently colored materials."""
    import collections
    import numpy as np
    from projected_tracks import encode_screen,share_flipped_glyphs
    image=frame_pixels(refs,palettes,glyphs,map_top=map_top)
    blocks=image[map_top:184].reshape(-1,8,32,8).transpose(0,2,1,3).reshape(-1,64)
    pairs=collections.Counter(frozenset(b)-{0} for b in blocks if len(set(b)-{0})==2)
    candidates=[]
    if palettes:
        dominant=[]
        for bank in palettes:
            pair=next((p for p,_ in pairs.most_common() if p<=set(bank)),())
            first=sorted(pair,key=lambda v:(v%2,v))
            dominant.append(first+[v for v in bank if v not in pair])
        candidates.extend((dominant,[sorted(bank) for bank in palettes],
                           [list(reversed(bank)) for bank in palettes]))
    candidates.append([])
    best=None
    for banks in candidates:
        local_glyphs=[bytes(32)]
        try:
            frame=encode_screen(image,[list(p) for p in banks],local_glyphs,
                {bytes(32):0},{},exact=True,map_top=map_top,prefer_shared=True)
        except ValueError:continue
        local_glyphs,local_frames=share_flipped_glyphs(local_glyphs,[frame])
        frame=local_frames[0];count=len({g for g,b in frame[0].values()}-{0})
        assert np.array_equal(frame_pixels(*frame,local_glyphs,map_top=map_top),image),'Atlas repack changed a source pixel'
        if best is None or count<best[0]:best=(count,local_glyphs,frame)
        if count<limit:break
    if best is None:return refs,palettes
    _,local,frame=best;lookup={raw:i for i,raw in enumerate(glyphs)};mapping={0:0}
    for i,raw in enumerate(local[1:],1):
        if raw not in lookup:lookup[raw]=len(glyphs);glyphs.append(raw)
        mapping[i]=lookup[raw]
    return {i:(mapping[g],bank) for i,(g,bank) in frame[0].items()},frame[1]

def pose_body(refs,palettes,glyphs,*,map_top=32,aligned=False):
    visible=sorted({g for g,b in refs.values()}-{0})
    indexed=any(bank&64 for _,bank in refs.values())
    words_count=(184-map_top)//8*32
    full=aligned and len(visible)==(320 if indexed else 640)
    slots={g:i+(0 if full else 1) for i,g in enumerate(visible)}
    words=[1023 if full and indexed else 0]*words_count
    for i,(g,bank) in refs.items():
        if g:words[i]=slots[g]|(((bank&48) if indexed else bank+2)<<10)
    palette=[v for b in range(6) for v in ([0]+list(palettes[b])+[0]*(15-len(palettes[b])) if b<len(palettes) else [0]*16)]
    if indexed:palette=list(range(32,128))
    body=bytes(palette)+struct.pack('<'+str(words_count)+'H',*words)
    if aligned and not full:body+=bytes(64 if indexed else 32)
    elif indexed and not aligned:body+=bytes(32)
    body+=b''.join(glyphs[g] for g in visible)
    return body,indexed,len(visible)


def align_frames(glyphs,frames,*,map_top):
    """Use 20 complete raster rows instead of 21 partially visible rows.

    The PPU scroll changes by the same one pixel. Displayed source pixels
    remain identical; the hidden guard scanline no longer costs 32 slots.
    """
    from projected_tracks import encode_screen,encode_indexed_screen,share_flipped_glyphs
    import numpy as np
    new=[bytes(32)];lookup={bytes(32):0};encodings={};converted={};result=[]
    for refs,palettes in frames:
        key=id(refs)
        if key not in converted:
            image=frame_pixels(refs,palettes,glyphs,map_top=map_top)
            image[:-1]=image[1:];image[-1]=0
            try:frame=encode_screen(image,[list(p) for p in palettes],new,lookup,encodings,map_top=map_top)
            except ValueError:frame=encode_indexed_screen(image,new,lookup,map_top=map_top)
            assert np.array_equal(frame_pixels(*frame,new,map_top=map_top),image)
            converted[key]=frame
        result.append(converted[key])
    return share_flipped_glyphs(new,result)

def write(source,output,level,glyphs,frames,*,preview=False,copy_world=None,postroll=120,extra_colors=(),actor_events=()):
    source=Path(source);output=Path(output);output.mkdir(parents=True,exist_ok=True)
    chart=json.loads((source/f'level{level}.json').read_text())
    map_top=chart.get('snapshot_map_top',32);words_count=(184-map_top)//8*32;header_bytes=96+words_count*2
    chart.setdefault('projection_native_palette_versions',chart.get('track_palette_versions',[]))
    last=chart['notes'][-1]['frame']
    assert preview or len(frames)==last+postroll+1,'A partial renderer test must not ship'
    events=[(t,k,i,v,p) for t,k,i,v,p in unpack_events((source/f'animation{level}.bin').read_bytes(),chart)
            if k not in (4,9,12,14,22,25,27,29,30,31,35,36)]
    if actor_events:
        events=[e for e in events if e[1] not in (6,10,15)]
        events.extend(actor_events)
    if extra_colors:
        events.extend(extra_colors)
        chart['track_palette_versions']=sorted(chart['track_palette_versions']+[[t,i,v] for t,k,i,v,p in extra_colors],key=lambda r:r[0])
    if copy_world:
        from projected_copies import actor_events,palette_events
        chart['mawaru_copy_world']=copy_world
        events.extend(actor_events(chart,copy_world))
        # The Source sampler already includes copies and their heading.
        # A second copy-only pass would overwrite the heading's colors.
        extra_colors=[] if chart.get('mawaru_headings') else palette_events(source,level,copy_world)
        events.extend(extra_colors)
        chart['track_palette_versions']=sorted(chart['track_palette_versions']+[[t,i,v] for t,k,i,v,p in extra_colors],key=lambda r:r[0])
    if any(r.get('decoration_hitboxes') for r in chart.get('freeroam_regions',[])):
        from decoration_hitboxes import palette_events
        colors=palette_events(source,level)
        events.extend(colors)
        chart['track_palette_versions']=sorted(chart['track_palette_versions']+[[t,i,v] for t,k,i,v,p in colors],key=lambda r:r[0])
    # Source caches can contain additional copy/foreground palette records
    # beyond their canonical animation file. Compile the complete palette
    # timeline, rather than assuming every metadata change is in that file.
    if 'track_palette_versions' in chart:
        events=[e for e in events if e[1]!=7]
        events.extend((t,7,i,v,b'') for t,i,v in chart['track_palette_versions'])
    from neo_fog import Fog
    fog=Fog(chart) if chart.get('mawaru_fog') else None
    aligned=chart.get('snapshot_aligned',False)
    if not aligned and any(len({g for g,b in refs.values()}-{0})>=640 for refs,_ in frames):
        glyphs,frames=align_frames(glyphs,frames,map_top=map_top)
        aligned=True
    wide=any(len({g for g,b in refs.values()}-{0})>(255 if any(b&64 for g,b in refs.values()) else 511)
             for refs,palettes in frames)
    peak=0;previous=None;snapshots=bytearray();indexed_frames=[];local_source=None;repacked={}
    for t,(refs,palettes) in enumerate(frames):
        indexed=any(bank&64 for _,bank in refs.values())
        visible=sorted({g for g,b in refs.values()}-{0})
        capacity=320 if indexed and wide else 256 if indexed else 640 if wide else 512
        if len(visible)>=capacity and not (aligned and len(visible)==capacity):
            key=id(refs)
            if key not in repacked:repacked[key]=repack_frame(refs,palettes,glyphs,map_top=map_top,limit=640 if wide else 512)
            refs,palettes=repacked[key];frames[t]=(refs,palettes)
            visible=sorted({g for g,b in refs.values()}-{0})
        peak=max(peak,len(visible))
        assert len(visible)<=(640 if wide else 512)-(0 if aligned else 1),('Snapshot atlas capacity',level,t,len(visible))
        indexed=any(bank&64 for _,bank in refs.values())
        if indexed:
            assert len(visible)<=(320 if wide else 256)-(0 if aligned else 1),('Indexed snapshot atlas capacity',level,t,len(visible))
            indexed_frames.append(t)
        full=aligned and len(visible)==capacity
        if full and not indexed:
            assert all(i in refs for i in range((176-map_top)*4)),('Nonblank slot zero needs a fully occupied viewport',level,t)
        slots={g:i+(0 if full else 1) for i,g in enumerate(visible)}
        # Mode 3 can address the immutable, all-zero tail of the HUD font.
        # Dense indexed frames can therefore use all 320 atlas slots.
        words=[1023 if full and indexed else 0]*words_count
        for i,(g,bank) in refs.items():
            if g:words[i]=slots[g]|(((bank&48) if indexed else bank+2)<<10)
        palette=[v for b in range(6) for v in ([0]+list(palettes[b])+[0]*(15-len(palettes[b])) if b<len(palettes) else [0]*16)]
        if indexed:palette=list(range(32,128))
        body=bytearray(bytes(palette)+struct.pack('<'+str(words_count)+'H',*words))
        if aligned and not full:body+=bytes(64 if indexed else 32)
        elif indexed and not aligned:body+=bytes(32)
        for g in visible:
            body+=glyphs[g]
        if (indexed,body)!=previous:
            packed=encode(bytes(body),indexed=indexed,header_bytes=header_bytes,slot_zero=aligned)
            chunks=(len(body)-header_bytes)//32
            if len(packed)+14>LIMIT and not indexed and aligned:
                from projected_tracks import encode_screen,share_flipped_glyphs
                pixels=frame_pixels(refs,palettes,glyphs,map_top=map_top)
                import numpy as np
                import random
                choices=[[],[sorted(bank) for bank in palettes],
                         [list(reversed(bank)) for bank in palettes]]
                for seed in range(8):
                    banks=[list(bank) for bank in palettes]
                    for bank in banks:random.Random(seed).shuffle(bank)
                    choices.append(banks)
                for banks in choices:
                    local_glyphs=[bytes(32)]
                    frame=encode_screen(pixels,banks,local_glyphs,{bytes(32):0},{},map_top=map_top,prefer_shared=True)
                    local_glyphs,local_frames=share_flipped_glyphs(local_glyphs,[frame])
                    assert np.array_equal(frame_pixels(*local_frames[0],local_glyphs,map_top=map_top),pixels)
                    local_body,local_indexed,count=pose_body(*local_frames[0],local_glyphs,map_top=map_top,aligned=True)
                    assert not local_indexed and count<=640
                    candidate=encode(local_body,header_bytes=header_bytes,slot_zero=True)
                    if len(candidate)<len(packed):
                        packed=candidate;chunks=(len(local_body)-header_bytes)//32
                    if len(packed)+14<=LIMIT:break
            # Global palette assignments can make a dense frame's exact
            # CHR unnecessarily expensive. Repack that same source image
            # locally before declaring a hardware buffer overflow.
            if len(packed)+14>LIMIT and not indexed and not aligned:
                from projected_tracks import Source,encode_screen,share_flipped_glyphs
                if local_source is None:local_source=Source(source,level,copy_world)
                pixels=local_source.screen(t)
                import numpy as np
                from mode1_tracks import decode_tile
                expected=np.zeros((184-map_top,256),dtype=np.uint8)
                for cell,(glyph,bank) in refs.items():
                    tile=np.frombuffer(decode_tile(glyphs[glyph],palettes[bank&15]),dtype=np.uint8).reshape(8,8)
                    if bank&16:tile=tile[:,::-1]
                    if bank&32:tile=tile[::-1,:]
                    y,x=divmod(cell,32);expected[y*8:y*8+8,x*8:x*8+8]=tile
                assert np.array_equal(expected,pixels[map_top:184]),('Local palette retry changed source pixels',level,t)
                local_glyphs=[bytes(32)]
                local_frame=encode_screen(pixels,[],local_glyphs,{bytes(32):0},{},map_top=map_top)
                local_glyphs,local_frames=share_flipped_glyphs(local_glyphs,[local_frame])
                local_body,local_indexed,count=pose_body(*local_frames[0],local_glyphs,map_top=map_top)
                assert not local_indexed
                if count<(640 if wide else 512):
                    candidate=encode(local_body,header_bytes=header_bytes)
                    if len(candidate)<len(packed):packed=candidate;chunks=count
            packet=HEADER.pack(t,(49 if indexed else 48) if aligned else (47 if indexed else 46),chunks,len(packed))+packed+HEADER.pack(65535,255,0,0)
            assert len(packet)<=SNAPSHOT_LIMIT,('Snapshot exceeds the immutable packet buffer',level,t,len(packet))
            events.append((t,42,0,len(packet),struct.pack('<I',len(snapshots))))
            snapshots+=packet
        previous=(indexed,body)
    if not preview and peak == 0:
        raise ValueError(f"{chart['code']}: no visible track pixels in the complete chart; "
                         "check for unsupported decoration-based track rendering")
    events.sort(key=lambda e:e[0])
    data=b''.join(HEADER.pack(t,k,i,v)+p for t,k,i,v,p in events)+HEADER.pack(65535,255,0,0)
    chart.update(mode1_tracks=3,mode1_projected=True,mode1_snapshot=True,mode1_glyph_count=640 if wide else 0,wide_snapshot_atlas=wide,
        sa1_stream_format=16 if copy_world else 14,sa1_inline_patterns=True,sa1_delta_patterns=False,sa1_row_dictionary=False,
        stream_row_offset=0,stream_direct_patterns_trial=False,stream_direct_spill_trial=False,
        stream_bulk_rows_trial=False,stream_merge_counts=[2,4,8],stream_obj_spill=False,
        catchup_disabled=True,early_vblank_trial=True,snapshot_frames=len(frames),snapshot_peak_glyphs=peak,
        snapshot_preview=preview,snapshot_postroll=postroll,snapshot_compression='lz4-split',
        indexed_color_frames=indexed_frames)
    chart['snapshot_aligned']=aligned
    for k in list(chart):
        if k.startswith('fallback_stream_'):chart.pop(k)
    chart.pop('mode1_icon_base',None)
    if chart.get('full_snapshot_source'):
        # Directory records retain their fixed legacy tag area; full poses
        # have no resident Mode 7 pattern leases to seed there.
        chart['pattern_initial']=[0]*256
    index,stream=indexed_packets(data,chart);stream=bytearray(stream);rom_index(index)
    # All catch-up choices share the same immutable pixels. The worker
    # remembers the latest due pose; the CPU downloads it just once after
    # applying native events, without reading intermediate screen images.
    payload_base=len(stream);seen=set()
    for _,_,choice in struct.iter_unpack('<HHI',index):
        for j in range(4):
            _,size,offset=struct.unpack_from('<HHI',stream,choice+j*8)
            while size:
                length=size&0x7fff
                if offset not in seen:
                    seen.add(offset)
                    for a,b,t,k,i,v in records(stream[offset:offset+length]):
                        if k==42:
                            pointer=struct.unpack_from('<I',stream,offset+a+7)[0]
                            struct.pack_into('<I',stream,offset+a+7,payload_base+pointer)
                if not size&0x8000:break
                offset+=length;size=struct.unpack_from('<H',stream,offset)[0];offset+=2
    stream+=snapshots
    chart['stream_packets']=len(index)//8
    for prefix,blob in [('stream_index',index),('stream_data',stream),('resident_stream',bytes(2)),('mode1_seeds',raw_seeds(index,stream,snapshot=True,clone_state=bool(copy_world),wide=wide,map_top=map_top))]:
        (output/f'{prefix}{level}.bin').write_bytes(blob)
    (output/f'level{level}.json').write_text(json.dumps(chart,indent=2))
    print(chart['code'],'frames',len(frames),'peak glyphs',peak,'stream bytes',len(stream),flush=True)


def compile(source,output,level,*,reuse_failed=False):
    from projected_tracks import compile_section,share_flipped_glyphs
    chart=json.loads((Path(source)/f'level{level}.json').read_text())
    actors=[]
    if chart.get('live_planet_proxies'):
        from decoration_tracks import actor_camera_events
        root=Path(__file__).resolve().parents[1]
        from pack_sources import load_source
        data=load_source(source,level)
        actors,versions=actor_camera_events(data,chart,chart['notes'][-1]['frame']+120)
        chart['actor_projection_versions']=versions
        (Path(source)/f'level{level}.json').write_text(json.dumps(chart,indent=2))
    from projected_copies import capture_world
    world=capture_world(source,level)
    colors=[] if chart.get('maze_decoration_tracks') or chart.get('decoration_tracks') or chart.get('mawaru_headings') else None
    failed=Path(output)/f'failed-projection{level}.pickle'
    if reuse_failed:
        import pickle
        assert failed.exists(),'No failed projection to re-encode'
        with failed.open('rb') as f:glyphs,frames,world,colors=pickle.load(f)
        assert len(frames)==chart['notes'][-1]['frame']+121,'Cached projection is incomplete'
    else:
        glyphs,frames=compile_section(source,level,0,chart['notes'][-1]['frame']+120,world,extra_colors=colors)
        glyphs,frames=share_flipped_glyphs(glyphs,frames)
    if not chart.get('snapshot_aligned'):
        trim_hidden_scanlines(glyphs,frames,map_top=chart.get('snapshot_map_top',32))
    glyphs,frames=share_flipped_glyphs(glyphs,frames)
    if not chart.get('snapshot_aligned') and any(len({g for g,b in refs.values()}-{0})>=640 for refs,_ in frames):
        glyphs,frames=align_frames(glyphs,frames,map_top=chart.get('snapshot_map_top',32))
        chart['snapshot_aligned']=True
        (Path(source)/f'level{level}.json').write_text(json.dumps(chart,indent=2))
    try:write(source,output,level,glyphs,frames,copy_world=world,extra_colors=colors or (),actor_events=actors)
    except Exception:
        # A failed encoder must not require repeating expensive geometry
        # rendering just to diagnose its packet. Retained only on failure.
        import pickle
        with (Path(output)/f'failed-projection{level}.pickle').open('wb') as f:
            pickle.dump((glyphs,frames,world,colors),f,protocol=5)
        raise
    (Path(output)/f'failed-projection{level}.pickle').unlink(missing_ok=True)


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--levels',type=int,nargs='+',required=True)
    parser.add_argument('--reuse-failed',action='store_true',help='Re-encode a frozen failed projection; requires independent pixel verification')
    args=parser.parse_args()
    for level in args.levels:compile(args.source,args.out,level,reuse_failed=args.reuse_failed)
