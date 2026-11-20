"""Share identical immutable screen packets without dropping any timestamp."""
import hashlib
import json
import struct
from pathlib import Path

from animation_bulk import HEADER, records


def share(index, data):
    patches={};packets={};visited=set()
    for _,_,choice in list(struct.iter_unpack('<HHI',index))[:-1]:
        for j in range(4):
            _,size,offset=struct.unpack_from('<HHI',data,choice+j*8)
            while size:
                length=size&0x7fff
                if offset not in visited:
                    visited.add(offset)
                    for start,end,frame,kind,_,value in records(data[offset:offset+length]):
                        if kind!=42:continue
                        at=offset+start+7;pointer=struct.unpack_from('<I',data,at)[0]
                        assert packets.setdefault(pointer,value)==value
                        patches[at]=pointer
                if not size&0x8000:break
                offset+=length;size=struct.unpack_from('<H',data,offset)[0];offset+=2
    if not packets:return bytes(data),0
    base=min(packets);prefix=bytearray(data[:base]);payload=bytearray();seen={};mapping={}
    for pointer,size in sorted(packets.items()):
        packet=data[pointer:pointer+size]
        assert len(packet)==size and packet[-7:]==HEADER.pack(65535,255,0,0)
        _,kind,_,length=HEADER.unpack_from(packet)
        assert kind in (41,44,45,46,47,48,49) and length+14==size
        # The due k42 event retains its original musical timestamp. The
        # immutable packet's earlier timestamp is only a decoder due check.
        key=hashlib.sha256(packet[2:]).digest()
        candidates=seen.setdefault(key,[])
        old=next((at for at,n in candidates if n==size and payload[at+2:at+n]==packet[2:]),None)
        if old is None:
            old=len(payload);payload+=packet;candidates.append((old,size))
        mapping[pointer]=base+old
    for at,pointer in patches.items():struct.pack_into('<I',prefix,at,mapping[pointer])
    result=bytes(prefix+payload)
    assert len(result)<=len(data)
    return result,len(data)-len(result)


def patch_pack(folder):
    folder=Path(folder);saved=0
    for level in json.loads((folder/'pack.json').read_text())['levels']:
        path=folder/f'level{level}.json';chart=json.loads(path.read_text())
        if not chart.get('mode1_snapshot'):continue
        variants=[('',chart)];changed=False
        if chart.get('vfx_off'):variants.append(('_vfx_off',chart['vfx_off']))
        for suffix,meta in variants:
            if meta.get('snapshot_packet_sharing'):continue
            source=folder/f'stream_data{suffix}{level}.bin'
            index=(folder/f'stream_index{suffix}{level}.bin').read_bytes()
            data,removed=share(index,source.read_bytes());source.write_bytes(data)
            meta['snapshot_packet_sharing']=1;meta['snapshot_shared_bytes']=removed;saved+=removed;changed=True
        if changed:path.write_text(json.dumps(chart,indent=2))
    return saved
