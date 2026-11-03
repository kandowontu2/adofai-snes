"""Compile AR-X texture reference lists without rebuilding music or raster art."""
import json,os,struct
from pathlib import Path
from animation_assets import generate

def patch_pack(out):
    out=Path(out);pack=json.loads((out/'pack.json').read_text())
    if 23 not in pack['levels'] or pack.get('standalone'):return
    path=out/'level23.json';chart=json.loads(path.read_text())
    if chart.get('compiled_reference_sets'):return
    assert chart.get('spatial_cell_order')==1,'Reference-only upgrade requires unchanged spatial indexing'
    descriptors=bytearray((out/'msu_descriptors.bin').read_bytes());at=pack['levels'].index(23)*24
    old,table=struct.unpack_from('<II',descriptors,at+8)
    target=out/'adofai.msu';image=bytearray(target.read_bytes())
    if old+chart['animation_bytes']==len(image):image=image[:old]
    chart.pop('catchup_format',None);chart['compiled_reference_sets']=True
    generate(out,chart,(out/'timeline23.bin').read_bytes(),(out/'patterns23.bin').read_bytes())
    stream=(out/'animation23.bin').read_bytes();struct.pack_into('<I',descriptors,at+8,len(image));image+=stream
    for c in range(len(chart['checkpoints'])):
        pointer=struct.unpack_from('<I',image,table+c*4)[0]
        blob=(out/f'animation23-checkpoint-{c}.bin').read_bytes()
        image[pointer:pointer+len(blob)]=blob
    temp=target.with_suffix('.msu.refs-tmp');temp.write_bytes(image);os.replace(temp,target)
    (out/'msu_descriptors.bin').write_bytes(descriptors);path.write_text(json.dumps(chart,indent=2))
