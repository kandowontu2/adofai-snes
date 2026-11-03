"""Install the verified master AR-X stream into its standalone cartridge.

Relocate only subsequent ROM-data blobs. Static code, chart geometry,
music bytes, and PCM assets are preserved.
"""
import json,struct
from pathlib import Path

def sync(out,source):
    out=Path(out);source=Path(source)
    chart=json.loads((out/'level23.json').read_text());new=json.loads((source/'level23.json').read_text())
    assert json.loads((out/'pack.json').read_text())['levels']==[23]
    assert chart['notes']==new['notes'] and chart['checkpoints']==new['checkpoints']
    if chart.get('compiled_reference_sets') and chart.get('catchup_format')==new['catchup_format']:return
    descriptors=bytearray((out/'msu_descriptors.bin').read_bytes())
    old,table=struct.unpack_from('<II',descriptors,8)
    image=bytearray((out/'sa1_payload.bin').read_bytes());original_length=len(image)
    stream=(source/'animation23.bin').read_bytes();delta=len(stream)-chart['animation_bytes'];cut=old+chart['animation_bytes']
    assert delta>0 and delta<len(image) and not any(image[-delta:]),'Insufficient cartridge space'
    image[old-0x10000:cut-0x10000]=stream;del image[-delta:]
    locations=json.loads((out/'placements.json').read_text())
    offset=lambda a:a-0xC00000 if a>=0xC00000 else a
    for name,address in list(locations.items()):
        value=offset(address)
        if value>=cut:
            assert name.startswith('romdata23_'),name
            value+=delta;locations[name]=value+0xC00000 if value<0x400000 else value
    for field in (0,4,12):
        value=struct.unpack_from('<I',descriptors,field)[0]
        if value>=cut:struct.pack_into('<I',descriptors,field,value+delta)
    if table>=cut:table+=delta
    for i in range(len(new['checkpoints'])):
        pointer=struct.unpack_from('<I',image,table-0x10000+i*4)[0]
        if pointer>=cut:pointer+=delta
        struct.pack_into('<I',image,table-0x10000+i*4,pointer)
        blob=(source/f'animation23-checkpoint-{i}.bin').read_bytes()
        image[pointer-0x10000:pointer-0x10000+len(blob)]=blob
        (out/f'animation23-checkpoint-{i}.bin').write_bytes(blob)
    assert len(image)==original_length
    music=(out/'level23.brr').read_bytes();music_at=struct.unpack_from('<I',descriptors)[0]-0x10000
    assert image[music_at:music_at+len(music)]==music
    fast=(out/'level23-fast.brr').read_bytes();fast_at=struct.unpack_from('<I',descriptors,4)[0]-0x10000
    assert image[fast_at:fast_at+len(fast)]==fast
    (out/'sa1_payload.bin').write_bytes(image);(out/'msu_descriptors.bin').write_bytes(descriptors)
    (out/'placements.json').write_text(json.dumps(locations,indent=2))
    (out/'animation23.bin').write_bytes(stream);(out/'level23.json').write_text(json.dumps(new,indent=2))
    (out/'manifest.json').write_text(json.dumps([new],indent=2))
    (out/'ar-animation-sync.json').write_text(json.dumps(dict(passed=True,additional_bytes=delta,music_bytes_unchanged=True),indent=2))

if __name__=='__main__':
    root=Path(__file__).resolve().parents[1]
    sync(root/'build/all-audio-fix/sa1-renderer-extra-03',root/'build/packs/sa1-scheduled-hits')
