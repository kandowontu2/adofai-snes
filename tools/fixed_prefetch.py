"""Move fixed-slot bitmap loads earlier without changing any visible bitmap."""
import bisect
import collections
import json
import struct
from pathlib import Path
from animation_bulk import records, HEADER


def relocate(data, initial, window=(1320,1650)):
    rows=list(records(data));active={0};frames={};tag_at=collections.defaultdict(list)
    for p,e,t,k,i,v in rows:
        if k==14:frames[t]=set(data[p+7:e])
        elif k==27:tag_at[t].append((i,v))
        else:assert k!=25,'Prepare an unbatched resident stream'
    last=max(t for _,_,t,k,_,_ in rows if k!=255)
    visits=[[] for _ in initial]
    for t in range(last+1):
        if t in frames:active=frames[t]
        for slot in active:visits[slot].append(t)
    loads=collections.Counter(t for _,_,t,k,_,_ in rows if k==27)
    scheduled=[];last_load=[0]*len(initial);moved=0
    for p,e,t,k,i,v in rows:
        new_t=t
        if k==27:
            if window[0]<=t<window[1]:
                at=bisect.bisect_left(visits[i],t)
                prior=visits[i][at-1] if at else -1
                earliest=max(1,t-128,prior+1,last_load[i]+1)
                if earliest<t:
                    loads[t]-=1
                    new_t=min(range(earliest,t+1),key=lambda f:(loads[f],f))
                    loads[new_t]+=1
                    moved+=new_t!=t
            last_load[i]=new_t
        scheduled.append((new_t,0 if k==27 else 1,p,k,i,v,data[p+7:e]))
    scheduled.sort(key=lambda r:(r[0],r[1],r[2]))
    out=bytearray();starts=[];versions=[[(0,v)] for v in initial]
    for t,_,p,k,i,v,payload in scheduled:
        starts.append((t,len(out)))
        out+=HEADER.pack(t,k,i,v)+payload
        if k==27 and (t,v)!=versions[i][-1]:versions[i].append((t,v))
    # The logical map and its active lists are unchanged. Verify the raw
    # identity visible through every logical slot on every song-clock frame.
    before=list(initial);after=list(initial);later=collections.defaultdict(list)
    for t,_,_,k,i,v,_ in scheduled:
        if k==27:later[t].append((i,v))
    active={0}
    for t in range(last+1):
        for i,v in tag_at[t]:before[i]=v
        for i,v in later[t]:after[i]=v
        if t in frames:active=frames[t]
        assert all(before[i]==after[i] for i in active),(t,active)
    return bytes(out),starts,versions,dict(moved_loads=moved,frames_checked=last+1)


def prepare(source,level=23):
    source=Path(source);file=source/f'level{level}.json';c=json.loads(file.read_text())
    if c.get('fixed_prefetch_format'):return
    assert c.get('resident_pattern_format') and not c.get('catchup_format')
    stream,starts,versions,report=relocate((source/f'animation{level}.bin').read_bytes(),c['pattern_initial'])
    times=[t for t,_ in starts];patterns=(source/f'patterns{level}.bin').read_bytes()
    for i,cp in enumerate(c['checkpoints']):
        at=max(0,cp['origin_frame']-32)
        cursor=starts[bisect.bisect_right(times,at)][1]
        f=source/f'animation{level}-checkpoint-{i}.bin';blob=bytearray(f.read_bytes())
        struct.pack_into('<I',blob,4,cursor)
        size=struct.unpack_from('<H',blob,12)[0]
        assert size==16384
        raw=[rows[bisect.bisect_right([t for t,v in rows],at)-1][1] for rows in versions]
        blob[-size:]=b''.join(patterns[v*64:(v+1)*64] for v in raw)
        f.write_bytes(blob)
    (source/f'animation{level}.bin').write_bytes(stream)
    c.update(pattern_versions=versions,animation_bytes=len(stream),fixed_prefetch_format=1)
    file.write_text(json.dumps(c,indent=2))
    (source/f'fixed-prefetch{level}.json').write_text(json.dumps(dict(passed=True,**report),indent=2))
    print(report)
