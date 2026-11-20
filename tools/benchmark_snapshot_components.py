"""Measure sharing each lossless LZ4 atlas across independent screen poses."""
import argparse,hashlib,json,struct
from pathlib import Path
from animation_bulk import HEADER,records


def packets(folder,level):
    stream=(folder/f'stream_data{level}.bin').read_bytes()
    index=(folder/f'stream_index{level}.bin').read_bytes()
    pointers={};visited=set()
    for _,_,choice in list(struct.iter_unpack('<HHI',index))[:-1]:
        for j in range(4):
            _,size,offset=struct.unpack_from('<HHI',stream,choice+j*8)
            offset&=0x0fffffff
            while size:
                length=size&32767
                if offset not in visited:
                    visited.add(offset)
                    for a,b,t,kind,i,value in records(stream[offset:offset+length]):
                        if kind==42:pointers[struct.unpack_from('<I',stream,offset+a+7)[0]]=value
                if not size&32768:break
                offset+=length;size=struct.unpack_from('<H',stream,offset)[0];offset+=2
    for at,size in sorted(pointers.items()):
        packet=stream[at:at+size]
        assert len(packet)==size and packet[-7:]==HEADER.pack(65535,255,0,0)
        yield bytes(2)+packet[2:]


def benchmark(folders):
    seen=set();atlases=set();wrappers=set();before=after=0;rows=[]
    digest=lambda b:hashlib.sha256(b).digest()
    for folder,levels in folders:
        start_before,start_after=before,after
        for n in levels:
            for packet in packets(folder,n):
                key=digest(packet)
                if key in seen:continue
                seen.add(key);before+=len(packet)
                _,kind,count,size=HEADER.unpack_from(packet)
                if kind not in (46,47):after+=len(packet);continue
                header_size=struct.unpack_from('<H',packet,7)[0]
                header=packet[7:9+header_size]
                atlas=packet[9+header_size:7+size]
                atlas_key=digest(atlas)
                if atlas_key not in atlases:
                    atlases.add(atlas_key);after+=len(atlas)
                wrapper_key=digest(bytes([kind])+struct.pack('<H',count)+header+atlas_key)
                if wrapper_key not in wrappers:
                    wrappers.add(wrapper_key);after+=len(header)+20
        row=dict(source=str(folder),levels=len(levels),original=before-start_before,
                 components=after-start_after,total_original=before,total_components=after,
                 ratio=after/before if before else 1)
        rows.append(row);print(json.dumps(row),flush=True)
    return rows


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--levels',type=int,nargs='+',required=True)
    p.add_argument('--rendered',action='store_true',help='Per-level on directories rather than a flat pack')
    p.add_argument('--report',type=Path,required=True)
    a=p.parse_args()
    batches=[(a.source/str(n)/'on',[n]) for n in a.levels] if a.rendered else [(a.source,a.levels)]
    a.report.write_text(json.dumps(benchmark(batches),indent=2))
