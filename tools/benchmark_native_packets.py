"""Measure lossless LZ4 for native animation packets, retaining every record."""
import argparse,hashlib,json,struct
from pathlib import Path
from snapshot_codec import encode


def measure(folder,n,suffix=''):
    stream=(folder/f'stream_data{suffix}{n}.bin').read_bytes()
    index=(folder/f'stream_index{suffix}{n}.bin').read_bytes()
    count=len(index)//8;seen=set();packets={};chains=set();original=packed=0
    for _,_,choice in list(struct.iter_unpack('<HHI',index))[:-1]:
        for j in range(4):
            _,size,at=struct.unpack_from('<HHI',stream,choice+j*8);at&=0x0fffffff
            chain=[]
            while size:
                length=size&32767;key=(at,length)
                if key not in packets:
                    raw=stream[at:at+length]
                    data=encode(raw)
                    assert len(raw)==length
                    packets[key]=data if len(data)+14<length else raw
                    if key not in seen:
                        original+=length;seen.add(key)
                chain.append(packets[key])
                if not size&32768:break
                at+=length;size=struct.unpack_from('<H',stream,at)[0];at+=2
            if not chain:continue
            digest=hashlib.sha256(b''.join(struct.pack('<H',len(c))+c for c in chain)).digest()
            if digest not in chains:
                chains.add(digest)
                packed+=sum(len(c)+14 for c in chain)+2*(len(chain)-1)
    return dict(level=n,variant=suffix or 'on',native_original=original,native_lz4=packed,
                ratio=packed/original if original else 1,retained_packets=len(packets))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True)
    p.add_argument('--levels',type=int,nargs='+',required=True);p.add_argument('--report',type=Path,required=True)
    p.add_argument('--rendered',action='store_true')
    a=p.parse_args();rows=[]
    for n in a.levels:
        row=measure(a.source/str(n)/'on' if a.rendered else a.source,n);rows.append(row);print(json.dumps(row),flush=True)
    a.report.write_text(json.dumps(rows,indent=2))
