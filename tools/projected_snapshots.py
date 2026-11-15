"""Independent, pixel-exact Mode 1 frames; no atlas lease dependencies."""
import json,struct,collections
from pathlib import Path
from animation_bulk import HEADER,records
from animation_catchup import unpack_events
from sa1_stream import indexed_packets,rom_index,LIMIT
from projected_tracks import raw_seeds
from snapshot_codec import encode_split as encode

def write(source,output,level,glyphs,frames,*,preview=False,copy_world=None,postroll=120,extra_colors=(),actor_events=()):
    source=Path(source);output=Path(output);output.mkdir(parents=True,exist_ok=True)
    chart=json.loads((source/f'level{level}.json').read_text())
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
        extra_colors=palette_events(source,level,copy_world)
        events.extend(extra_colors)
        chart['track_palette_versions']=sorted(chart['track_palette_versions']+[[t,i,v] for t,k,i,v,p in extra_colors],key=lambda r:r[0])
    if any(r.get('decoration_hitboxes') for r in chart.get('freeroam_regions',[])):
        from decoration_hitboxes import palette_events
        colors=palette_events(source,level)
        events.extend(colors)
        chart['track_palette_versions']=sorted(chart['track_palette_versions']+[[t,i,v] for t,k,i,v,p in colors],key=lambda r:r[0])
    from neo_fog import Fog
    fog=Fog(chart) if chart.get('mawaru_fog') else None
    wide=any(len({g for g,b in refs.values()}-{0})>511 for refs,palettes in frames)
    if wide:assert not any(b&64 for refs,palettes in frames for g,b in refs.values()),'Wide atlas cannot mix 8-bpp frames'
    peak=0;previous=None;snapshots=bytearray();indexed_frames=[]
    for t,(refs,palettes) in enumerate(frames):
        visible=sorted({g for g,b in refs.values()}-{0});peak=max(peak,len(visible))
        assert len(visible)<(640 if wide else 512),('Snapshot atlas capacity',level,t,len(visible))
        indexed=any(bank&64 for _,bank in refs.values())
        if indexed:
            assert len(visible)<=255,('Indexed snapshot atlas capacity',level,t,len(visible))
            indexed_frames.append(t)
        slots={g:i+1 for i,g in enumerate(visible)};words=[0]*608
        for i,(g,bank) in refs.items():
            if g:words[i]=slots[g]|(((bank&48) if indexed else bank+2)<<10)
        palette=[v for b in range(6) for v in ([0]+list(palettes[b])+[0]*(15-len(palettes[b])) if b<len(palettes) else [0]*16)]
        if indexed:palette=list(range(32,128))
        body=bytearray(bytes(palette)+struct.pack('<608H',*words))
        if indexed:body+=bytes(32)
        for g in visible:
            body+=glyphs[g]
        if (indexed,body)!=previous:
            packed=encode(bytes(body))
            chunks=1+len(visible)*2 if indexed else len(visible)
            packet=HEADER.pack(t,47 if indexed else 46,chunks,len(packed))+packed+HEADER.pack(65535,255,0,0)
            assert len(packet)<=LIMIT,('Snapshot exceeds the immutable packet buffer',level,t,len(packet))
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
    for prefix,blob in [('stream_index',index),('stream_data',stream),('resident_stream',bytes(2)),('mode1_seeds',raw_seeds(index,stream,snapshot=True,clone_state=bool(copy_world),wide=wide))]:
        (output/f'{prefix}{level}.bin').write_bytes(blob)
    (output/f'level{level}.json').write_text(json.dumps(chart,indent=2))
    print(chart['code'],'frames',len(frames),'peak glyphs',peak,'stream bytes',len(stream),flush=True)


def compile(source,output,level):
    from projected_tracks import compile_section,share_flipped_glyphs
    chart=json.loads((Path(source)/f'level{level}.json').read_text())
    from projected_copies import capture_world
    world=capture_world(source,level)
    glyphs,frames=compile_section(source,level,0,chart['notes'][-1]['frame']+120,world)
    glyphs,frames=share_flipped_glyphs(glyphs,frames)
    write(source,output,level,glyphs,frames,copy_world=world)


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--levels',type=int,nargs='+',required=True)
    args=parser.parse_args()
    for level in args.levels:compile(args.source,args.out,level)
