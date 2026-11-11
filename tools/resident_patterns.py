"""Store immutable animated bitmaps in ROM and stream only their identities.

The SA-1 reads the dictionary through a separate C0 window. The SNES data
reader keeps its F0 window, so embedded audio cannot repage a tile DMA.
"""
import argparse
import collections
import json
import struct
from pathlib import Path
from animation_bulk import HEADER, records


def changes(data):
    """Yield timestamped tag changes and complete authored active lists."""
    for pos,end,t,k,i,v in records(data):
        if k==4:
            yield t,'tag',(i,v)
        elif k==20:
            for j in range(v):yield t,'tag',struct.unpack_from('<HH',data,pos+7+j*68)
        elif k==27:
            yield t,'tag',(i,v)
        elif k==25:
            for j in range(i):yield t,'tag',struct.unpack_from('<HH',data,pos+7+j*4)
        elif k==14:
            yield t,'active',data[pos+7:end]


def future_intervals(data,initial):
    groups=collections.defaultdict(list)
    for t,k,v in changes(data):groups[t].append((k,v))
    tags=list(initial);active={0};prior=set();starts={};intervals=[]
    for t,updates in sorted(groups.items()):
        for k,v in updates:
            if k=='tag':tags[v[0]]=v[1]
            else:active=set(v)
        current={tags[slot] for slot in active}-{0}
        for raw in prior-current:intervals.append((starts.pop(raw),t-1,raw))
        for raw in current-prior:starts[raw]=t
        prior=current
    intervals.extend((start,65534,raw) for raw,start in starts.items())
    return sorted([max(1,start-40),raw,start,end]
                  for start,end,raw in intervals if start>=40)


def compact(data,patterns):
    out=bytearray();mapping={}
    for pos,end,t,k,i,v in records(data):
        mapping[pos]=len(out)
        if k==4:
            assert data[pos+11:end]==patterns[v*64:(v+1)*64]
            out+=HEADER.pack(t,27,i,v)
        elif k==20:
            payload=bytearray()
            for j in range(v):
                p=pos+7+j*68;slot,raw=struct.unpack_from('<HH',data,p)
                assert data[p+4:p+68]==patterns[raw*64:(raw+1)*64]
                payload+=struct.pack('<HH',slot,raw)
            out+=HEADER.pack(t,25,v,len(payload))+payload
        elif k in (21,22,24,25,26,27):
            raise ValueError('Prepare resident patterns from the original animation stream')
        else:out+=data[pos:end]
    mapping[len(data)]=len(out)
    assert list(changes(data))==list(changes(out))
    return bytes(out),mapping


def prepare(source,level,dense_prefetch=False):
    source=Path(source);path=source/f'level{level}.json'
    chart=json.loads(path.read_text())
    if chart.get('resident_pattern_format')==1:return chart
    assert not chart.get('adaptive_raster'),'Resident preparation requires full-detail geometry'
    assert not chart.get('catchup_format'),'Prepare before optional catch-up branches'
    patterns=(source/f'patterns{level}.bin').read_bytes()
    assert len(patterns)%64==0 and len(patterns)//64<=32768
    original=(source/f'animation{level}.bin').read_bytes()
    future=future_intervals(original,chart['pattern_initial'])
    if dense_prefetch:
        loads=collections.Counter(row[2] for row in future)
        # Sparse changes can load on demand. Reserve early transfers for
        # dense scene changes, as in the AR-X resident schedule.
        future=sorted([max(1,deadline-160),raw,deadline,end]
                      for _,raw,deadline,end in future if loads[deadline]>=100)
    stream,mapping=compact(original,patterns)
    for i,_ in enumerate(chart['checkpoints']):
        cp=source/f'animation{level}-checkpoint-{i}.bin';blob=bytearray(cp.read_bytes())
        cursor=struct.unpack_from('<I',blob,4)[0]
        struct.pack_into('<I',blob,4,mapping[cursor]);cp.write_bytes(blob)
    (source/f'animation{level}.bin').write_bytes(stream)
    (source/f'resident_raw{level}.bin').write_bytes(patterns)
    (source/f'resident_future{level}.bin').write_bytes(b''.join(
        struct.pack('<HHHH',frame,raw,end,deadline) for frame,raw,deadline,end in future))
    chart.update(resident_pattern_format=1,catchup_disabled=True,
                 bitmap_prefetch_versions=future,animation_bytes=len(stream))
    path.write_text(json.dumps(chart,indent=2))
    print(json.dumps(dict(level=level,patterns=len(patterns)//64,
                          animation_before=len(original),animation_after=len(stream),
                          future_intervals=len(future))),flush=True)
    return chart


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--source',type=Path,required=True)
    ap.add_argument('--level',type=int,required=True);ap.add_argument('--dense-prefetch',action='store_true')
    a=ap.parse_args();prepare(a.source,a.level,a.dense_prefetch)
