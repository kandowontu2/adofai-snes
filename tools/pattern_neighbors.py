"""Choose exact-color replacement leases from the previous authored scene."""
import bisect,collections,struct
import numpy as np
from scipy.optimize import linear_sum_assignment

def lease_hints(chart,timeline,raw):
    tiles=np.frombuffer(raw,dtype=np.uint8).reshape(-1,64)
    events=collections.defaultdict(list)
    for cell,offset in enumerate(chart['visibility_offsets'][:chart['visibility_cells']]):
        count=struct.unpack_from('<H',timeline,offset)[0]
        for i in range(count):
            f,v=struct.unpack_from('<HH',timeline,offset+2+i*4);events[f].append((0,cell,v))
    for slot,rows in enumerate(chart['pattern_versions']):
        for f,v in rows:events[f].append((1,slot,v))
    counts=collections.Counter();cells={};patterns=[0]*256;frames=[];states=[]
    for frame,updates in sorted(events.items()):
        for kind,i,v in updates:
            if kind:patterns[i]=v
            else:
                old=cells.get(i,0)
                if old:counts[old]-=1
                if v:counts[v]+=1
                cells[i]=v
        frames.append(frame);states.append({patterns[i] for i,v in counts.items() if v>0}-{0})
    cache={}
    def hints(frame,pattern):
        if frame not in cache:
            at=bisect.bisect_right(frames,frame)-1;current=states[max(0,at)];assignments=[]
            for lag in (4,8):
                at=bisect.bisect_right(frames,max(0,frame-lag))-1;previous=states[max(0,at)]
                needed=sorted(current-previous);available=sorted(previous-current);mapping={}
                if needed and available:
                    cost=(tiles[needed,None,:]!=tiles[None,available,:]).sum(axis=2)
                    rows,cols=linear_sum_assignment(cost)
                    mapping={needed[r]:available[c] for r,c in zip(rows,cols)}
                assignments.append(mapping)
            cache[frame]=assignments
        return tuple(m.get(pattern,65535) for m in cache[frame])
    return hints


def signature_blob(raw):
    import struct
    tiles=np.frombuffer(raw,dtype=np.uint8).reshape(-1,8,8);out=bytearray(struct.pack('<H',len(tiles)))
    for tile in tiles:
        full=tile!=0;edge=(tile&1)!=0
        small=full.reshape(4,2,4,2).any(axis=(1,3));se=edge.reshape(4,2,4,2).any(axis=(1,3))
        bits=lambda a:sum(int(v)<<i for i,v in enumerate(a.ravel()))
        out+=struct.pack('<HH',bits(small),bits(se))
        out+=bytes(bits(row) for row in full)
        out+=bytes(bits(edge[i]) for i in (1,3,4,6))
    return bytes(out)

def patch_signatures(out):
    import json,re
    levels=json.loads((out/'pack.json').read_text())['levels']
    if 60 not in levels:return
    text=(out/'addresses.inc').read_text()
    if 'ROM_DATA_BUILD' in text:
        address=json.loads((out/'placements.json').read_text())['romdata60_signatures']
        if address>=0xC00000:address-=0xC00000
    else:
        blob=signature_blob((out/'patterns60.bin').read_bytes());path=out/'adofai.msu';size=path.stat().st_size
        with path.open('r+b') as f:
            f.seek(max(0,size-len(blob)))
            if f.read()==blob:address=size-len(blob)
            else:f.seek(0,2);address=f.tell();f.write(blob)
    text=re.sub(r'^PATTERN_SIGNATURE_.*\n','',text,flags=re.M)
    (out/'addresses.inc').write_text(text+f'PATTERN_SIGNATURE_SOURCE = ${address:08X}\nPATTERN_SIGNATURE_LEVEL = {levels.index(60)}\n')
