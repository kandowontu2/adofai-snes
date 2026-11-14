"""Offline scheduling of the 1023 reusable PPU track-pattern slots."""
import bisect,collections,heapq

def palette_alias_table(palette,write_counts):
    """Prefer colors whose CGRAM entries stay stable through the window."""
    canonical={};table=list(range(256))
    for index,value in sorted(palette.items(),key=lambda p:(write_counts.get(p[0],0),p[0])):
        table[index]=canonical.setdefault(value,index)
    return bytes(table)

def share_palette_patterns(chart,tiles,history):
    """Share identical CGRAM colors without changing a single displayed pixel.

    A fill and an outline need not use the same material pair. In particular,
    landed and upcoming floors often have identical outlines but distinct fills.
    Re-evaluate on palette writes so later color changes cannot leak across floors.
    """
    events=collections.defaultdict(dict);writes=collections.defaultdict(dict)
    for cell,rows in history.items():
        for frame,value in rows:events[frame][cell]=value
    for frame,index,value in chart['track_palette_versions']:
        writes[frame][32+index]=value
    # Color aliases are only needed at cache-pressure peaks. Keeping ordinary
    # material indices elsewhere lets CGRAM fades run without rewriting CHR.
    current={};windows=[];times=sorted(events);pressure=[]
    for frame in times:
        current.update(events[frame]);pressure.append(len(set(current.values())-{0}))
    for j,frame in enumerate(times):
        if pressure[j]>chart.get('palette_sharing_threshold',255):
            # Switch representations while there is room to retain both old
            # and new textures. Switching at an already-full atlas forces an
            # atomic replacement larger than a single VBlank can upload.
            left=j;right=j
            while left>0 and pressure[left]>96:left-=1
            while right+1<len(times) and pressure[right]>96:right+=1
            start=times[left];end=times[right]+1
            if windows and start<=windows[-1][1]:windows[-1][1]=max(end,windows[-1][1])
            else:windows.append([start,end])
    chart['palette_pattern_share_windows']=windows
    # Choosing the lowest palette index made a fading material the alias
    # for stationary floors. Every shade change then rewrote those floors'
    # CHR too. A stable representative preserves the exact same RGB pixels.
    ranks=[collections.Counter(index for f,updates in writes.items() if a<=f<b for index in updates if f!=a) for a,b in windows]
    boundaries={f for pair in windows for f in pair};window=0
    palette={};live={};previous={};result={};lookup={raw:i for i,raw in enumerate(tiles)}
    translation=bytes(range(256));mapped={}
    for frame in sorted(set(events)|set(writes)|boundaries):
        if frame>=chart['notes'][-1]['frame']:break
        palette.update(writes.get(frame,{}));live.update(events.get(frame,{}))
        new=bytes(range(256))
        while window<len(windows) and frame>=windows[window][1]:window+=1
        if window<len(windows) and windows[window][0]<=frame:
            new=palette_alias_table(palette,ranks[window])
        if new!=translation:translation=new;mapped={}
        current={}
        for cell,p in live.items():
            if not p:continue
            if p not in mapped:
                raw=tiles[p].translate(translation)
                if raw not in lookup:lookup[raw]=len(tiles);tiles.append(raw)
                mapped[p]=lookup[raw]
            current[cell]=mapped[p]
        for cell in previous.keys()|current.keys():
            value=current.get(cell,0)
            if value!=previous.get(cell,0):result.setdefault(cell,[]).append((frame,value))
        previous=current
    chart['palette_pattern_alias_version']=2
    return result

def cache_patterns(chart,tiles,history):
    # Rasterization can create intermediate textures outside the sampled
    # viewport. They need no global IDs or cartridge snapshot storage.
    used=sorted({0}|{v&0xfffff for rows in history.values() for _,v in rows})
    if len(used)<len(tiles):
        remap={old:new for new,old in enumerate(used)}
        chart['unreferenced_patterns_removed']=len(tiles)-len(used)
        tiles=[tiles[i] for i in used]
        history={cell:[(f,(v&~0xfffff)|remap[v&0xfffff]) for f,v in rows] for cell,rows in history.items()}
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
    future_starts=collections.defaultdict(list)
    if chart.get('optimal_pattern_cache'):
        for start,end,p in intervals:future_starts[p].append(start)
    def patch_span(old,new):
        if old is None:return 64
        a,b=tiles[old],tiles[new]
        first=0
        while first<64 and a[first]==b[first]:first+=1
        last=64
        while last>first and a[last-1]==b[last-1]:last-=1
        return last-first
    for start,end,p in intervals:
        if p in pinned:continue
        slot=pattern_slot.get(p)
        if slot is not None and last_pattern.get(slot)==p and slot_end[slot]<start:
            previous=slot_end[slot]
        else:
            if future_starts:
                # Retain bitmaps needed again soon. The old oldest-end
                # allocator discarded those repeatedly during moving loops.
                available=[s for s in range(first_slot,capacity) if slot_end[s]<start]
                assert available,('Track pattern capacity',chart['code'],start)
                def eviction(s):
                    uses=future_starts.get(last_pattern.get(s),[])
                    j=bisect.bisect_left(uses,start)
                    return (uses[j] if j<len(uses) else 65536,
                            -patch_span(last_pattern.get(s),p) if chart.get('delta_pattern_cache') else 0,
                            -slot_end[s])
                slot=max(available,key=eviction);previous=slot_end[slot]
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
    if chart.get('id')==60:
        preloads=[]
        for start,end,p in intervals:
            if start<40:continue
            preloads.append([max(1,start-40),p,start,end])
        chart['bitmap_prefetch_versions']=sorted(preloads)
    chart['pattern_initial']=initial
    chart['pattern_versions']=versions
    chart['pattern_count']=len(tiles)
    chart['pattern_pinned_count']=len(pinned)
    chart['pattern_max_uploads']=max((n for f,n in loads.items() if f),default=0)
    chart['_pattern_data']=b''.join(tiles) if chart.get('mode7') else b''.join(t[:16] for t in tiles)
    print(chart['code'],len(tiles),'patterns;',len(intervals),'cache intervals; peak',chart['pattern_max_uploads'],'uploads/frame',flush=True)
    return [tiles[p] for p in initial],converted
