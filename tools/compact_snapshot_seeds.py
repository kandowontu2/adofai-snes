"""Omit unused atlas tails from snapshot restart seeds, preserving every pose."""
import json,struct
from pathlib import Path


def compact(data, *, wide=False):
    count=struct.unpack_from('<I',data)[0]//4
    offsets=list(struct.unpack_from('<'+str(count)+'I',data))
    assert offsets[0]==count*4 and offsets==sorted(offsets)
    offsets.append(len(data));result=bytearray(count*4)
    atlas_size=40960 if wide else 32768
    for i,(start,end) in enumerate(zip(offsets,offsets[1:])):
        seed=data[start:end]
        header=struct.unpack_from('<H',seed,2)[0]
        glyph_bytes=header&(0x7fff if wide else 0x3fff)
        clones=42 if header&0x8000 else 0
        atlas_at=4+clones+96+4096
        retained=(glyph_bytes+32+4095)&~4095
        assert 0<retained<=atlas_size and atlas_at+atlas_size+2<=len(seed)
        # All visible glyphs, palette, map, clone state, symbols and cursor
        # remain byte-for-byte identical. The omitted bytes are unused slots.
        shortened=seed[:atlas_at+retained]+seed[atlas_at+atlas_size:]
        assert shortened[:atlas_at+glyph_bytes+32]==seed[:atlas_at+glyph_bytes+32]
        struct.pack_into('<I',result,i*4,len(result));result+=shortened
    return bytes(result)


def patch_pack(folder):
    folder=Path(folder);levels=json.loads((folder/'pack.json').read_text())['levels'];saved=0
    for level in levels:
        path=folder/f'level{level}.json';chart=json.loads(path.read_text())
        if not chart.get('mode1_snapshot') or chart.get('compact_snapshot_seeds'):continue
        seed=folder/f'mode1_seeds{level}.bin';before=seed.read_bytes()
        after=compact(before,wide=bool(chart.get('wide_snapshot_atlas')))
        saved+=len(before)-len(after);seed.write_bytes(after)
        chart['compact_snapshot_seeds']=1;path.write_text(json.dumps(chart,indent=2))
    return saved
