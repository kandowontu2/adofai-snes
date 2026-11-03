"""Replace compiled chart graphics in an MSU pack without re-encoding audio.

The new animation and checkpoint snapshots are appended atomically. ROM
geometry is repacked afterwards; all existing music and PCM bytes stay intact.
"""
import argparse,json,os,shutil,struct
from pathlib import Path
import campaign_assets as assets
from build_sa1 import compile_engine

def install(out,source,n):
    pack=json.loads((out/'pack.json').read_text())
    assert not pack.get('standalone')
    old=json.loads((out/f'level{n}.json').read_text());new=json.loads((source/f'level{n}.json').read_text())
    for note in old['notes']:note.setdefault('position_track_offset',[0,0])
    assert old['notes']==new['notes'] and old['checkpoints']==new['checkpoints']
    assert (out/f'level{n}.brr').read_bytes()==(source/f'level{n}.brr').read_bytes()
    descriptors=bytearray((out/'msu_descriptors.bin').read_bytes());at=pack['levels'].index(n)*24
    image=bytearray((out/'adofai.msu').read_bytes())
    animation=len(image);image+=(source/f'animation{n}.bin').read_bytes()
    table=len(image);image+=bytes(4*len(new['checkpoints']))
    for i in range(len(new['checkpoints'])):
        struct.pack_into('<I',image,table+4*i,len(image))
        image+=(source/f'animation{n}-checkpoint-{i}.bin').read_bytes()
    struct.pack_into('<IIHH',descriptors,at+8,animation,table,new['visibility_cells'],int(bool(new.get('pattern_versions'))))
    temp=out/'adofai.msu.chart-tmp';temp.write_bytes(image);os.replace(temp,out/'adofai.msu')
    (out/'msu_descriptors.bin').write_bytes(descriptors)
    names=[f'level{n}.json',f'level{n}-build.json',f'patterns{n}.bin',f'animation{n}.bin']
    names += [f'{p}{n}.bin' for p in ('chart','track_chr','track_map','timeline','visibility_index','checkpoints')]
    names += [f'animation{n}-checkpoint-{i}.bin' for i in range(len(new['checkpoints']))]
    for name in names:shutil.copyfile(source/name,out/name)
    charts=[json.loads((out/f'level{i}.json').read_text()) for i in pack['levels']]
    assets.OUT=out;blobs=assets.ui_assets(pack['title'],mode7=True)
    for c in charts:
        i=c['id']
        for p in ('chart','track_chr','track_map'):blobs[f'{p}{i}']=(out/f'{p}{i}.bin').read_bytes()
        blobs[f'music{i}']=blobs[f'timeline{i}']=bytes(2)
        blobs[f'checkpoints{i}']=bytes(max(2,14*len(c['checkpoints'])))
    assets.pack_payload(blobs,charts,msu=True,sa1=True);assets.common_tables(charts)
    compile_engine(out)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);ap.add_argument('--source',type=Path,required=True);ap.add_argument('--level',type=int,required=True)
    a=ap.parse_args();install(a.out,a.source,a.level)
