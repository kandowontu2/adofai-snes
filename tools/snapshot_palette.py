"""Reindex scalar palette events without changing immutable screen packets."""
import struct
from animation_bulk import HEADER,records
from sa1_stream import indexed_packets


def replace_palette(index,data,chart):
    events=[];pointers=[]
    for _,_,choice in list(struct.iter_unpack('<HHI',index))[:-1]:
        _,size,offset=struct.unpack_from('<HHI',data,choice)
        assert not size&0x8000,'A primary packet must not be a catch-up chain'
        for a,b,t,k,i,v in records(data[offset:offset+size]):
            if k in (7,8,255):continue
            payload=data[offset+a+7:offset+b]
            if k==42:pointers.append(struct.unpack('<I',payload)[0])
            events.append((t,k,i,v,payload))
    base=min(pointers)
    for t,i,v in chart['track_palette_versions']:events.append((t,7,i,v,b''))
    events.sort(key=lambda e:e[0]);canonical=bytearray()
    for t,k,i,v,payload in events:
        if k==42:payload=struct.pack('<I',struct.unpack('<I',payload)[0]-base)
        canonical+=HEADER.pack(t,k,i,v)+payload
    canonical+=HEADER.pack(65535,255,0,0)
    new_index,prefix=indexed_packets(bytes(canonical),chart);prefix=bytearray(prefix)
    visited=set()
    for _,_,choice in list(struct.iter_unpack('<HHI',new_index))[:-1]:
        for j in range(4):
            _,size,offset=struct.unpack_from('<HHI',prefix,choice+j*8)
            while size:
                length=size&0x7fff
                if offset not in visited:
                    visited.add(offset)
                    for a,b,t,k,i,v in records(prefix[offset:offset+length]):
                        if k==42:
                            at=offset+a+7;pointer=struct.unpack_from('<I',prefix,at)[0]
                            struct.pack_into('<I',prefix,at,len(prefix)+pointer)
                if not size&0x8000:break
                offset+=length;size=struct.unpack_from('<H',prefix,offset)[0];offset+=2
    return new_index,bytes(prefix)+data[base:]
