"""Scene presentation that is separate from Neo Cosmos's musical floors."""
import collections
import math
from make_assets import FPS


def chapter_time(chart, beat):
    """Mawaru's scripted beat clock starts with the first musical floor."""
    bpms=[(0,170),(41,140),(117,155),(213,170),(341,185),(505,160),
          (569,200),(721,215)]
    if chart['code']=='T3EX-X':bpms += [(787,107.5),(788,215)]
    bpms += [(898,170),(930,180),(962,190),(994,200)]
    return chart['notes'][1]['time']+sum(max(0,min(beat,bpms[j+1][0] if j+1<len(bpms) else beat)-start)*60/bpm
                                        for j,(start,bpm) in enumerate(bpms))


def configure(data, chart):
    notes=chart['notes']
    chart['neo_opacity_events']=[]
    chart['neo_motion_events']=[]
    if data['code'] in ('T3-X','T3EX-X'):
        from neo_warps import compile_math
        compile_math(data,chart)
        for n in notes:n.pop('warp_visual',None)
        unit=24/data['native_tile_size']
        for w in data.get('native_warps',[]):
            i=min(range(len(notes)),key=lambda i:sum((a-b)**2 for a,b in zip(data['native_positions'][i],w['position'])))
            base=data['native_positions'][i]
            local=lambda pos:[round((pos[0]-base[0])*unit),round(-(pos[1]-base[1])*unit)]
            marker=dict(center=local(w['position']),link=[local(p) for p in w.get('link',[])])
            notes[i].setdefault('warp_visual',dict(markers=[]))['markers'].append(marker)
            if 'native_track_colors' in data:data['native_track_colors'][i]['color']=w['tint']
            if w['section']=='lofi':events=[(0,0,0),(257,8*60/170,1),(297,4*60/170,0)]
            elif w['index']==0:events=[(0,0,0),(962,0,1),(970,2*60/190,0)]
            else:events=[(0,0,0),(974,4*60/190,1),(994,0,0)]
            chart['neo_opacity_events'] += [dict(floor=i,time=0 if b==0 else chapter_time(chart,b),duration=duration,opacity=alpha) for b,duration,alpha in events]
        # SpawnBootlegFloors reveals four real floors when the two-beat
        # delivery animation lands. These reveals are chapter code, not ffx.
        ex=data['code']=='T3EX-X';first=1023 if ex else 812
        for group in range(4):
            when=chapter_time(chart,(1010 if ex else 1008)+group*4)
            for i in range(first+group*6,first+group*6+4):
                chart['neo_opacity_events'].append(dict(floor=i,time=when,duration=0,opacity=1))
        for i,start,end in ((319 if ex else 248,301,337),(727 if ex else 555,673,713)):
            if 'scene_visual' not in notes[i]:continue
            chart['neo_opacity_events'] += [dict(floor=i,time=0,duration=0,opacity=0),
                dict(floor=i,time=chapter_time(chart,start),duration=8*60/170,opacity=1),
                dict(floor=i,time=chapter_time(chart,end),duration=8*60/170,opacity=0)]
        for root in ((319,331,727,739) if ex else (248,260,555,567)):
            i=root+3;a=notes[i];b=notes[i+1]
            chart['neo_motion_events'].append(dict(floor=i,time=a['time'],duration=4*60/(170 if root<500 else 200),
                offset=[(b['x']-24-a['x'])/24,-(b['y']-a['y'])/24],ease='InOutSine'))
    # Several chapters reuse one moving platform for successive orbits.
    # Match identical authored motion, not just nearby or crossing floors.
    if data['code'] in ('T3-X','T3EX-X','T4-X','T4EX-X','T5-X'):
        motions=collections.defaultdict(list)
        for e in data['native_track_effects']:
            if e['type']!='ffxMoveFloorPlus' or not e.get('positionUsed',True):continue
            for i in range(e['start'],e['end']+1,1+e.get('gapLength',0)):
                motions[i].append((e['floor'],e.get('degreeOffset',0),e['duration'],e['targetPos']['x'],e['targetPos']['y'],e['ease']))
        groups=collections.defaultdict(list)
        for i,events in motions.items():
            n=notes[i]
            if n['hold_length']<0 and n['spin_kind']=='normal':
                groups[(n['x'],n['y'],tuple(events))].append(i)
        for (_,_,events),ids in groups.items():
            if len(ids)<2:continue
            dx,dy=events[0][3:5]
            if not (dx or dy):continue
            angle=math.atan2(-dy,dx)
            for i in ids:
                notes[i]['platform_group']=ids
                notes[i]['platform_angle']=angle
                notes[i]['platform_hidden']=i!=ids[0]
    # Mawaru's defense minigames replace pairs of hidden rhythm floors.
    # Each projectile's direction and deadline come from those same floors,
    # so checkpoints, speed changes, and calibration share the gameplay clock.
    sections={'T3-X':((370,50,3.),(754,9,2.2)),
              'T3EX-X':((484,74,3.),(951,13,2.2))}.get(data['code'],())
    chart['neo_meteors']=[]
    for first,count,approach in sections:
        for k in range(count):
            i=first+2*k;n=notes[i];center=notes[i+1]
            dx=n['x']-center['x'];dy=n['y']-center['y'];radius=math.hypot(dx,dy)
            duration=round(approach*FPS)
            # Original spawn distance is 13 Unity units (85% after first).
            # Defense floors use a larger native radius. Match the cartridge's
            # 24-pixel orbit so the visible projectile meets the moving planet.
            distance=13*24/data['native_tile_size']*(1 if not k else .85)*24/radius
            chart['neo_meteors'].append(dict(start=n['frame']-duration,end=n['frame'],judge=i+1,
                dx=round(dx/radius*24),dy=round(dy/radius*24),
                vx=round(dx/radius*(distance-24)*256/duration),
                vy=round(dy/radius*(distance-24)*256/duration)))
            for j in (i,i+1):notes[j]['scene_hidden']=True
