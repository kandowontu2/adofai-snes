"""Temporal mipmaps for the Mode 7 world texture.

Each output cell retains the authored scene's lifetime. Coarser texels are
used only when zoom makes multiple source pixels occupy one screen pixel.
"""
import collections
import numpy as np

def reduce_tile(block):
    samples=np.stack([block[dy::2,dx::2] for dy in range(2) for dx in range(2)])
    result=samples[0].copy();best=np.full((8,8),-1)
    for candidate in samples:
        count=(samples==candidate).sum(axis=0)
        # Preserve seams/background and edge colors when coverage is tied.
        score=count*8+(candidate==0)*2+(candidate&1)
        take=score>best;result[take]=candidate[take];best[take]=score[take]
    return result.tobytes()

def mipmap_history(chart,tiles,history):
    events=collections.defaultdict(dict)
    for cell,rows in history.items():
        for frame,value in rows:events[frame][cell]=value
    # Rotating individual floors can exhaust Mode 7's 255 usable patterns
    # even at native camera zoom. Restrict the coarser texture to the dense
    # interval; projection/planet scale remains tied to the authored camera.
    if chart.get('tile_rotation_version') or chart.get('adaptive_motion_raster'):
        live={};counts=collections.Counter();windows=[];start=None
        bursts=[]
        for frame,updates in sorted(events.items()):
            incoming=set(updates.values())-set(counts)-{0}
            if frame and chart.get('adaptive_motion_raster') and len(incoming)>16:bursts.append([max(0,frame-12),frame+20])
            for cell,value in updates.items():
                old=live.get(cell,0)
                if old:
                    counts[old]-=1
                    if not counts[old]:del counts[old]
                live[cell]=value
                if value:counts[value]+=1
            if start is None and len(counts)>240:start=max(0,frame-16)
            elif start is not None and len(counts)<190:
                windows.append([start,frame+16]);start=None
        if start is not None:windows.append([start,65535])
        windows=sorted(windows+bursts)
        merged=[]
        for a,b in windows:
            if merged and a<=merged[-1][1]:merged[-1][1]=max(b,merged[-1][1])
            else:merged.append([a,b])
        chart['raster_capacity_windows']=merged
        if merged:
            from track_camera import mode7_zoom_schedule
            mode7_zoom_schedule(chart)
    shifts=dict(chart['camera_raster_shift_versions'])
    source={};output={};result={};textures=[bytes(64)];lookup={textures[0]:0}
    arrays=[np.frombuffer(t,dtype=np.uint8).reshape(8,8) for t in tiles]
    shift=0;last_shift=None;peak=0
    def intern(raw):
        if raw not in lookup:lookup[raw]=len(textures);textures.append(raw)
        return lookup[raw]
    def write(cell,value,frame):
        if output.get(cell,0)==value:return
        rows=result.setdefault(cell,[(0,0)])
        if rows[-1][0]==frame:rows[-1]=(frame,value)
        else:rows.append((frame,value))
        if value:output[cell]=value
        else:output.pop(cell,None)
    for frame in sorted(set(events)|set(shifts)):
        updates=events.get(frame,{})
        for cell,value in updates.items():
            if value:source[cell]=value
            else:source.pop(cell,None)
        shift=shifts.get(frame,shift)
        changing=shift!=last_shift
        dirty=set(source)|set(updates) if changing else set(updates)
        if shift:
            dirty={(x//2,y//2) for x,y in dirty}
        if changing:dirty.update(output)
        for cell in sorted(dirty):
            if shift:
                x,y=cell;block=np.zeros((16,16),dtype=np.uint8)
                for dy in range(2):
                    for dx in range(2):
                        value=source.get((x*2+dx,y*2+dy),0)
                        if value:block[dy*8:dy*8+8,dx*8:dx*8+8]=arrays[value]
                value=intern(reduce_tile(block))
            else:value=intern(tiles[source.get(cell,0)])
            write(cell,value,frame)
        last_shift=shift;peak=max(peak,len(set(output.values())))
    chart['raster_mipmap_version']=1
    chart['raster_peak_unique_patterns']=peak
    print(chart.get('code'),f'mipmapped: {len(textures)} textures; peak {peak} simultaneous',flush=True)
    return textures,result
