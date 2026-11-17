"""Prove compact MSU directories, native events, poses and restart references.

Compare the assembled file against the independent local render caches. This
checks bytes and timestamps, not an assumption that similar images are enough.
"""
import argparse,json,mmap,struct
from pathlib import Path
from animation_bulk import records
from verification_data import identity


def verify(base):
    frozen=identity(base/'adofai.sfc',fresh=True);rows=[]
    assert 'REFERENCE_SNAPSHOT_SEEDS = 1' in (base/'addresses.inc').read_text()
    with (base/'adofai.msu').open('rb') as file,mmap.mmap(file.fileno(),0,access=mmap.ACCESS_READ) as image:
        assert len(image)<=2**32 and image[12:14]==struct.pack('<H',35)
        for n in json.loads((base/'pack.json').read_text())['levels']:
            chart=json.loads((base/f'level{n}.json').read_text())
            if not chart.get('mode1_snapshot'):continue
            for suffix,c in [('',chart)]+([('_vfx_off',chart['vfx_off'])] if chart.get('vfx_off') else []):
                assert c['compact_snapshot_seeds']==4
                stream=(base/f'stream_data{suffix}{n}.bin').read_bytes()
                index=(base/f'stream_index{suffix}{n}.bin').read_bytes()
                seed=(base/f'mode1_seeds{suffix}{n}.bin').read_bytes()
                count=len(index)//8;removed=count*512;directory=count*544
                stream_base=c['stream_msu_base'];seed_base=c['mode1_seed_base']
                refs={};visited=set();packets={}
                for i in range(count):
                    for j in range(4):
                        before=struct.unpack_from('<HHI',stream,i*544+j*8)
                        after=struct.unpack_from('<HHI',image,stream_base+i*32+j*8)
                        assert before[:2]==after[:2],(n,suffix,i,j,'Changed due time or packet size')
                        if not before[1]:
                            assert before==after;continue
                        offset=before[2]&0x0fffffff
                        assert after[2]==((before[2]&0xf0000000)|(offset-removed))
                        size=before[1]
                        while size:
                            length=size&0x7fff
                            if offset not in visited:
                                visited.add(offset)
                                for a,b,t,k,_,v in records(stream[offset:offset+length]):
                                    if k!=42:continue
                                    at=offset+a+7;pointer=struct.unpack_from('<I',stream,at)[0]
                                    runtime=struct.unpack_from('<I',image,stream_base+at-removed)[0]
                                    assert image[stream_base+runtime:stream_base+runtime+v]==bytes(2)+stream[pointer+2:pointer+v],(n,suffix,t,'Changed pose')
                                    assert packets.setdefault(pointer,runtime)==runtime
                                    refs[at]=runtime
                            if not size&0x8000:break
                            offset+=length;size=struct.unpack_from('<H',stream,offset)[0];offset+=2
                assert packets
                expected=bytearray(stream[directory:min(packets)])
                for at,runtime in refs.items():struct.pack_into('<I',expected,at-directory,runtime)
                actual=stream_base+count*32
                assert image[actual:actual+len(expected)]==expected,(n,suffix,'Changed native animation bytes')
                native_bytes=len(expected)
                expected=bytearray(seed);seed_count=struct.unpack_from('<I',seed)[0]//4
                for at in struct.unpack_from('<'+str(seed_count)+'I',seed):
                    header=struct.unpack_from('<H',seed,at+2)[0]
                    field=at+4+(42 if header&0x8000 else 0)
                    size,pointer=struct.unpack_from('<HI',seed,field)
                    if size:struct.pack_into('<I',expected,field+2,packets[pointer])
                assert image[seed_base:seed_base+len(seed)]==expected,(n,suffix,'Changed restart state')
                rows.append(dict(id=n,variant=suffix or 'main',directories=count,pose_references=len(refs),
                                 unique_poses=len(packets),restart_seeds=seed_count,native_bytes=native_bytes))
    assert identity(base/'adofai.sfc',fresh=True)==frozen
    report=dict(passed=True,**frozen,variants=rows,pose_references=sum(r['pose_references'] for r in rows),
                restart_seeds=sum(r['restart_seeds'] for r in rows))
    folder=base/'verification';folder.mkdir(exist_ok=True)
    (folder/'snapshot-storage.json').write_text(json.dumps(report,indent=2))
    print('SNAPSHOT STORAGE PASS',len(rows),'variants;',report['pose_references'],'pose references;',report['restart_seeds'],'restart seeds',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--pack',required=True)
    verify(Path(__file__).resolve().parents[1]/'build/packs'/parser.parse_args().pack)
