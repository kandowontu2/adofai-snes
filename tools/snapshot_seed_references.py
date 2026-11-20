"""Reuse immutable screen packets at restart, retaining all native seed state.

Only loading changes: ordinary frame packets and their timestamps stay intact.
Version 4 seeds contain cursor/header/clones, a (length, offset) pose reference,
and the exact symbol list. A zero-length reference is the initial blank pose.
"""
import json
import struct
from pathlib import Path

from animation_bulk import HEADER, records
from snapshot_codec import decode,decode_split
from projected_tracks import snapshot_pose


def reference_seeds(seeds, index, stream, *, wide=False, map_top=32):
    header_bytes=96+(184-map_top)//8*64;map_offset=map_top*8
    count=struct.unpack_from('<I',seeds)[0]//4
    offsets=list(struct.unpack_from('<'+str(count)+'I',seeds));offsets.append(len(seeds))
    entries=list(struct.iter_unpack('<HHI',index))[:-1]
    result=bytearray(count*4);cursor=0;pointer=length=0;body=None;kind=0
    for i,(start,end) in enumerate(zip(offsets,offsets[1:])):
        seed=seeds[start:end];wanted,header=struct.unpack_from('<HH',seed)
        assert cursor<=wanted<=len(entries),('Seed cursor',i,cursor,wanted)
        while cursor<wanted:
            _,_,choice=entries[cursor];_,size,at=struct.unpack_from('<HHI',stream,choice)
            assert not size&0x8000,'Canonical seed packet must be complete'
            for a,b,t,k,_,v in records(stream[at:at+size]):
                if k!=42:continue
                pointer=struct.unpack_from('<I',stream,at+a+7)[0];length=v
                _,kind,glyphs,packed=HEADER.unpack_from(stream,pointer)
                assert kind in (41,44,45,46,47,48,49) and packed+14==length,(kind,packed,length)
                payload=stream[pointer+7:pointer+7+packed]
                if kind in (46,47,48,49):body=decode_split(payload,glyphs,header_bytes=header_bytes)
                elif kind==45:body=decode(payload,glyphs,header_bytes=header_bytes)
                elif kind==44:body=payload
                else:
                    palette,words,atlas=snapshot_pose(payload,glyphs,map_top=map_top)
                    body=palette+words+b''.join(atlas)
            cursor+=1
        clones=42 if header&0x8000 else 0
        at=4+clones;glyph_bytes=header&(0x7fe0 if wide else 0x3fff)
        symbols=at+96+1472+32+glyph_bytes
        assert symbols+2<=len(seed)
        assert symbols+2+struct.unpack_from('<H',seed,symbols)[0]==len(seed)
        if body is None:
            assert glyph_bytes==0 and not any(seed[at:symbols]),'Initial pose is not blank'
        else:
            assert len(body)==header_bytes+glyph_bytes+(32 if kind in (48,49) else 0)
            assert seed[at:at+96]==body[:96]
            assert seed[at+96:at+96+map_offset]==bytes(map_offset)
            assert seed[at+96+map_offset:at+96+1472]==body[96:header_bytes]
            if kind in (48,49):
                assert seed[at+96+1472:symbols]==body[header_bytes:]
            else:
                assert seed[at+96+1472:at+96+1472+32]==bytes(32)
                assert seed[at+96+1472+32:symbols]==body[header_bytes:]
            assert bool(header&(1 if wide else 0x4000))==(kind in (47,49))
        struct.pack_into('<I',result,i*4,len(result))
        result+=seed[:at]+struct.pack('<HI',length,pointer)+seed[symbols:]
    return bytes(result)


def patch_pack(folder):
    folder=Path(folder);saved=0
    for level in json.loads((folder/'pack.json').read_text())['levels']:
        path=folder/f'level{level}.json';chart=json.loads(path.read_text())
        if not chart.get('mode1_snapshot'):continue
        changed=False;variants=[('',chart)]
        if chart.get('vfx_off'):variants.append(('_vfx_off',chart['vfx_off']))
        for suffix,meta in variants:
            if meta.get('compact_snapshot_seeds')==4:continue
            assert meta.get('compact_snapshot_seeds')==3,'Compact and share packets before referencing seeds'
            name=folder/f'mode1_seeds{suffix}{level}.bin';old=name.read_bytes()
            new=reference_seeds(old,(folder/f'stream_index{suffix}{level}.bin').read_bytes(),
                (folder/f'stream_data{suffix}{level}.bin').read_bytes(),wide=bool(meta.get('wide_snapshot_atlas')),map_top=meta.get('snapshot_map_top',32))
            temporary=name.with_suffix('.bin.new');temporary.write_bytes(new);temporary.replace(name)
            meta['compact_snapshot_seeds']=4;meta['snapshot_seed_saved_bytes']=len(old)-len(new)
            saved+=len(old)-len(new);changed=True
        if changed:path.write_text(json.dumps(chart,indent=2))
    return saved
