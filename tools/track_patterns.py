"""Offline scheduling of the 1023 reusable PPU track-pattern slots."""
import bisect,collections,heapq

def cache_patterns(chart,tiles,history):
    events=collections.defaultdict(list)
    for cell,versions in history.items():
        for frame,value in versions:events[frame].append((cell,value&0xfffff))
    counts=collections.Counter();live={};starts={};intervals=[]
    for frame,updates in sorted(events.items()):
        before={}
        for cell,pattern in updates:
            old=live.get(cell,0)
            for p in (old,pattern):
                if p:before.setdefault(p,counts[p])
            if old:counts[old]-=1
            if pattern:counts[pattern]+=1
            live[cell]=pattern
        for p,old in before.items():
            if old and not counts[p]:intervals.append((starts.pop(p),frame-1,p))
            elif not old and counts[p]:starts[p]=frame
    intervals.extend((start,65535,p) for p,start in starts.items())
    intervals.sort()
    capacity=256 if chart.get('mode7') else 1024
    # Keep common outlines and fills resident. Otherwise foreground changes
    # evict them between repeats and waste DMA on the same shapes again.
    repeated=collections.Counter(p for a,b,p in intervals)
    candidates=[p for p,n in repeated.most_common() if n>1]
    pinned=candidates[:chart.get('pattern_pinned_limit',24)] if chart.get('mode7') else []
    first_slot=1+len(pinned)
    slots=[(-1,i) for i in range(first_slot,capacity)];heapq.heapify(slots)
    versions=[[(0,0)] for _ in range(capacity)];pattern_intervals=collections.defaultdict(list)
    loads=collections.Counter();batches=collections.Counter();initial=[0]*capacity;last_pattern={};slot_end={i:-1 for i in range(1,capacity)};pattern_slot={}
    for slot,p in enumerate(pinned,1):
        versions[slot]=[(0,p)];initial[slot]=p
        pattern_intervals[p].append((0,65535,slot))
    pinned=set(pinned)
    for start,end,p in intervals:
        if p in pinned:continue
        slot=pattern_slot.get(p)
        if slot is not None and last_pattern.get(slot)==p and slot_end[slot]<start:
            previous=slot_end[slot]
        else:
            while True:
                previous,slot=heapq.heappop(slots)
                if previous==slot_end[slot]:break
        latency=chart.get('pattern_latency',24) if chart.get('mode7') and previous>=0 and last_pattern.get(slot)!=p else 0
        assert previous+latency<start,('Track pattern capacity',chart['code'],capacity,start)
        if last_pattern.get(slot)!=p:
            earliest=max(0,start-180,previous+1)
            if earliest==0:at=0
            else:
                last=max(earliest,start-latency)
                at=min(range(earliest,last+1),key=lambda f:(batches[f//8],loads[f],f) if chart.get('mode7') else (loads[f],f))
                assert loads[at]<(256 if chart.get('authored_visibility') else 64 if chart.get('mode7') else 24),('Pattern upload budget',chart['code'],start,loads[at])
                if chart.get('mode7'):
                    budget=4096 if chart.get('authored_visibility') else chart.get('pattern_batch_budget',64 if chart.get('id')==60 else 128)
                    assert batches[at//8]<budget,('Pattern upload budget',chart['code'],start,batches[at//8])
                    batches[at//8]+=1
            loads[at]+=1
            if at==0:versions[slot]=[(0,p)];initial[slot]=p
            else:versions[slot].append((at,p))
            last_pattern[slot]=p
        slot_end[slot]=end;pattern_slot[p]=slot
        pattern_intervals[p].append((start,end,slot));heapq.heappush(slots,(end,slot))
    lookup={p:([a for a,b,s in rows],rows) for p,rows in pattern_intervals.items()}
    def physical(value,frame):
        pattern=value&0xfffff
        if not pattern:return 0
        starts,rows=lookup[pattern];at=bisect.bisect_right(starts,frame)-1
        start,end,slot=rows[at];assert start<=frame<=end
        return slot if chart.get('mode7') else slot|(((value>>20)&7)<<10)|(((value>>23)&3)<<14)
    converted={cell:[(f,physical(v,f)) for f,v in rows] for cell,rows in history.items()}
    chart['pattern_initial']=initial
    chart['pattern_versions']=versions
    chart['pattern_count']=len(tiles)
    chart['pattern_pinned_count']=len(pinned)
    chart['pattern_max_uploads']=max((n for f,n in loads.items() if f),default=0)
    chart['_pattern_data']=b''.join(tiles) if chart.get('mode7') else b''.join(t[:16] for t in tiles)
    print(chart['code'],len(tiles),'patterns;',len(intervals),'cache intervals; peak',chart['pattern_max_uploads'],'uploads/frame',flush=True)
    return [tiles[p] for p in initial],converted
