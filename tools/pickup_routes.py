"""Find controller routes without inventing successful pickup counts.

Both planet positions are sampled along every intervening arc. This catches
unwanted pickups while waiting for the next direction, including the final
stationary orbit before a room closes.
"""
import heapq
import itertools
import math
from functools import lru_cache

from decoration_pickups import accepts


def route(region,note):
    cells={tuple(p) for p in region['cells']}
    points=[tuple(p) for p in region['coins']]
    kinds=region.get('coin_types',[0]*len(points))
    rate=note['rate']/256
    sign=1 if rate>0 else -1
    period=math.ceil(256/abs(rate))+2
    cos=[round(24*math.cos(i*math.pi/128)) for i in range(256)]
    sin=[round(24*math.sin(i*math.pi/128)) for i in range(256)]
    @lru_cache(None)
    def hits(cell,angle,duration):
        result=[];previous=set()
        for t in range(duration+1):
            a=(angle+math.floor(t*rate))&255
            planets=(cell,(cell[0]+cos[a],cell[1]+sin[a]))
            touched={i for i,(x,y) in enumerate(points)
                     if any(abs(x-px)<6 and abs(y-py)<6 for px,py in planets)}
            result.extend(sorted(touched-previous));previous=touched
        return tuple(result)
    def collect(mask,events):
        for i in events:
            if mask>>i&1:continue
            if kinds[i]==5:
                if (mask&31).bit_count()==4:return None
            elif kinds[i]==4:
                if i!=(mask&31).bit_count():return None
                mask|=1<<i
            else:mask|=1<<i
        return mask
    @lru_cache(None)
    def counts(mask):
        return tuple(sum((mask>>i)&1 for i,kind in enumerate(kinds) if (0 if kind>=3 else kind)==axis and kind!=5)
                     for axis in range(3))
    def feasible(mask):
        values=(*counts(mask),sum(counts(mask)))
        return all(mode!=2 or value<=target
                   for mode,target,value in zip(region['coin_modes'],region['coin_targets'],values))
    start=tuple(region.get('entry',(0,0)))
    angle=note['angle'];mask=collect(0,hits(start,angle,0))
    assert mask is not None
    initial=(start,angle,mask);best={initial:region['start']};parents={}
    serial=itertools.count();queue=[(region['start'],next(serial),initial)]
    deadline=region['return_start'];finish=None
    while queue:
        at,_,state=heapq.heappop(queue)
        if best[state]!=at:continue
        cell,angle,mask=state
        parked=collect(mask,hits(cell,angle,min(period,deadline-at)))
        if parked is not None and accepts(region,counts(parked)):
            finish=state;break
        for dx,dy,direction in ((24,0,0),(0,-24,192),(-24,0,128),(0,24,64)):
            target=(cell[0]+dx,cell[1]+dy)
            if target not in cells:continue
            turn=((direction-angle)*sign)%256
            if turn<16:turn+=256
            duration=max(3,round(turn/abs(rate)));when=at+duration
            if when>=deadline:continue
            obtained=collect(mask,hits(cell,angle,duration))
            if obtained is None or not feasible(obtained):continue
            next_angle=(direction^128)+(43*sign if note.get('planets',2)==3 else 0)
            next_angle&=255
            obtained=collect(obtained,hits(target,next_angle,0))
            if obtained is None or not feasible(obtained):continue
            following=(target,next_angle,obtained)
            if when>=best.get(following,deadline):continue
            best[following]=when;parents[following]=state
            heapq.heappush(queue,(when,next(serial),following))
        if len(best)>750000:
            raise ValueError(('Pickup route search capacity',region['step']))
    if finish is None:raise ValueError(('No legal pickup route',region['step'],len(best)))
    result=[]
    while finish!=initial:
        cell,angle,_=finish
        result.append([best[finish],*cell,angle]);finish=parents[finish]
    return list(reversed(result))
