"""Losslessly compress native event runs; keep pose references patchable."""
import struct
import lz4.block
from animation_bulk import HEADER,records,payload_size
from snapshot_codec import encode

END=HEADER.pack(65535,255,0,0)


def coordinate_filter(packet,*,restore=False):
    """Predict typed event fields and adjacent bulk coordinates per run."""
    output=bytearray(packet);indices={};values={};start=0
    while start<len(packet):
        t,kind,index,value=HEADER.unpack_from(packet,start)
        if kind==255:
            assert packet[start:]==END
            break
        actual_index=(index+indices.get(kind,0))&65535 if restore else index
        actual_value=(value+values.get(kind,0))&65535 if restore else value
        HEADER.pack_into(output,start,t,kind,
            actual_index if restore else (index-indices.get(kind,0))&65535,
            actual_value if restore else (value-values.get(kind,0))&65535)
        indices[kind]=actual_index;values[kind]=actual_value
        if kind in (17,18):
            prior=0
            for at in range(start+7,start+7+actual_value*2,2):
                word=struct.unpack_from('<H',packet,at)[0]
                actual=(word+prior)&65535 if restore else word
                struct.pack_into('<H',output,at,actual if restore else (word-prior)&65535)
                prior=actual
        start+=7+payload_size(kind,actual_index,actual_value)
    assert start==len(packet)-7,'Native filter terminator differs'
    return bytes(output)


def compress_packet(packet):
    result=bytearray();run=bytearray();wrappers=0
    def flush():
        nonlocal wrappers
        if not run:return
        raw=bytes(run)+END
        packed=encode(raw)
        filtered=encode(coordinate_filter(raw))
        kind=50
        if len(filtered)<len(packed):packed=filtered;kind=51
        if len(packed)+7<len(run):
            result.extend(HEADER.pack(HEADER.unpack_from(run)[0],kind,len(raw),len(packed)))
            result.extend(packed);wrappers+=1
        else:result.extend(run)
        run.clear()
    for first,last,t,kind,i,value in records(packet):
        if kind in (50,51):raise ValueError('Native packets are already compressed')
        if kind in (42,255):
            flush()
            result.extend(packet[first:last])
        else:run.extend(packet[first:last])
    assert len(result)<=len(packet)
    return bytes(result),wrappers


def expand_packet(packet):
    result=bytearray()
    for first,last,t,kind,count,value in records(packet):
        if kind not in (50,51):
            result.extend(packet[first:last]);continue
        raw=lz4.block.decompress(packet[first+7:last],uncompressed_size=count)
        assert len(raw)==count and raw.endswith(END),'Invalid native LZ4 block'
        if kind==51:raw=coordinate_filter(raw,restore=True)
        # Interior termination returns to the outer packet. It does not
        # discard any source event, source timestamp, or final terminator.
        result.extend(raw[:-7])
    return bytes(result)


def compact_prefix(prefix,count):
    """Relocate all four choices and their chains, preserving every due time."""
    output=bytearray(prefix[:count*32]);patches=[];cache={};shared={}
    before=after=wrappers=0
    for row in range(count):
        for choice in range(4):
            entry=row*32+choice*8
            time,size,tagged=struct.unpack_from('<HHI',prefix,entry)
            if not size:continue
            offset=tagged&0x0fffffff;chunks=[]
            while size:
                length=size&32767;key=(offset,length)
                if key not in cache:
                    raw=bytes(prefix[offset:offset+length])
                    assert len(raw)==length and raw.endswith(END)
                    packed,n=compress_packet(raw)
                    assert expand_packet(packed)==raw,'Native compression changed source records'
                    cache[key]=packed;before+=len(raw);after+=len(packed);wrappers+=n
                chunks.append(cache[key])
                if not size&32768:break
                offset+=length;size=struct.unpack_from('<H',prefix,offset)[0];offset+=2
            sizes=[len(c)|(32768 if i+1<len(chunks) else 0) for i,c in enumerate(chunks)]
            blob=b''.join((struct.pack('<H',sizes[i]) if i else b'')+c for i,c in enumerate(chunks))
            key=(sizes[0],blob)
            if key not in shared:
                at=len(output);shared[key]=at;output+=blob
                start=at
                for i,chunk in enumerate(chunks):
                    if i:start+=2
                    patches.extend(start+a+7 for a,b,t,k,_,v in records(chunk) if k==42)
                    start+=len(chunk)
            struct.pack_into('<HHI',output,entry,time,sizes[0],(tagged&0xf0000000)|shared[key])
    assert len(output)<0x10000000
    return output,patches,dict(native_raw_bytes=before,native_lz4_bytes=after,native_lz4_blocks=wrappers)
