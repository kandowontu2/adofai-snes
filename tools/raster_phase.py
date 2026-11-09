"""Change raster origin without changing any screen-space tile or planet pose.

Large translated groups keep their 8x8 bitmap phase. The camera and all
planet coordinates receive the same tiny translation, using existing events.
"""
from collections import Counter


def schedule(motion):
    rows=[[0,0,0]]
    for frame,updates in sorted(motion.items()):
        if not frame or len(updates)<32:continue
        offset,count=Counter(updates.values()).most_common(1)[0]
        if count<32:continue
        phase=[round(v)%8 for v in offset]
        if phase!=rows[-1][1:]:rows.append([frame,*phase])
    return rows


def camera(rows,origins):
    positions={f:(x,y) for f,x,y in rows};phases={f:(x,y) for f,x,y in origins}
    position=positions[0];phase=(0,0);result=[]
    for frame in sorted(set(positions)|set(phases)):
        position=positions.get(frame,position);phase=phases.get(frame,phase)
        value=[position[i]-phase[i] for i in range(2)]
        if not result or result[-1][1:]!=value:result.append([frame,*value])
    return result


def motion(chart,updates,planet=False):
    notes=chart['notes'];origins={f:(x,y) for f,x,y in chart['raster_origin_versions']}
    offsets=[(0,0)]*len(notes);phase=(0,0);last=[None]*len(notes);result={}
    for frame in sorted({0}|set(updates)|set(origins)):
        for i,value in updates.get(frame,{}).items():offsets[i]=value
        changed=frame in origins and origins[frame]!=phase
        phase=origins.get(frame,phase)
        candidates=range(len(notes)) if changed or frame==0 else updates[frame]
        values={}
        for i in candidates:
            offset=notes[i].get('position_track_offset',(0,0)) if planet and not notes[i].get('stick_to_floor',True) else offsets[i]
            value=tuple(offset[j]-phase[j] for j in range(2))
            if value!=last[i]:values[i]=value;last[i]=value
        if values:result[frame]=values
    return result
