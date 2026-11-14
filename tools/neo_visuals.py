"""Scene presentation that is separate from Neo Cosmos's musical floors."""
import collections
import math
from make_assets import FPS


def chapter_time(chart, beat):
    """Chapter beat clocks include their authored BPM changes."""
    if chart['code'] in ('T4-X','T4EX-X'):
        bpms=[(0,150),(96,75),(104,150),(120,75),(122,150),
              (238,112.5),(250,56.25),(252,112.5),(255,225),
              (313,112.5),(317,225),(381,112.5)]
        return chart['notes'][1]['time']+sum(max(0,min(beat,bpms[j+1][0] if j+1<len(bpms) else beat)-start)*60/bpm
                                            for j,(start,bpm) in enumerate(bpms))
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
    if data['code'] in ('T3-X','T3EX-X','T4-X','T4EX-X'):
        for i,c in enumerate(data.get('native_track_colors',[])):
            if c['style']==4:notes[i]['gem_platform']=True
    if data['code'] in ('T2-X','T2EX-X'):
        # Keep gameplay geometry; omit the expensive decorative room texture
        # and EX notefield backboards that obscure the route on the SNES.
        chart['singsing_backgrounds_disabled']=True
        chart['singsing_note_cues']=data['code']=='T2EX-X'
        chart['singsing_connectors']=[i for i in range(58 if data['code']=='T2-X' else 82,
                                                       148 if data['code']=='T2-X' else 194)
                                      if notes[i].get('spin_kind')=='midspin']
    if data['code']=='T2-X':
        # The chapter's shared cubicle is visible during the approach. Its
        # hot/cold route changes at CubicleTransition, independently of the
        # underlying rhythm floors' brief on-hit flashes.
        chart['singsing_route_window']=[notes[1]['time']+b*60/data['bpm'] for b in (28,84)]
        when=chart['singsing_route_window'][0]
        chart['neo_opacity_events'] += [dict(floor=i,time=when,duration=0,opacity=1)
                                       for i in range(58,148)
                                       if notes[i].get('spin_kind')!='midspin']
        chart['singsing_route_events']=[]
        for k,beat in enumerate((28,44,56,62,68,74,84)):
            active=() if beat==84 else ((60,66) if k%2==0 else (84,90))
            chart['singsing_route_events'] += [dict(floor=i,time=notes[1]['time']+beat*60/data['bpm'],
                                                   duration=0,opacity=int(i in active))
                                             for i in chart['singsing_connectors']]
    if data['code'] in ('T4-X','T4EX-X') and len(notes)>52:
        # ThirdSun.Bounce47, scheduled at beat 26. The EX rhythm copies
        # share each bounce; the two elevated midspins remain stationary.
        groups=(((47,49),28),((50,52),29)) if data['code']=='T4EX-X' else (((47,),28),((48,),29))
        beat=60/data['bpm'];origin=notes[1]['time'];height=1/data['native_tile_size']
        for ids,start in groups:
            for i in ids:
                chart['neo_motion_events'] += [
                    dict(floor=i,time=origin+start*beat,duration=.5*beat,offset=[0,height],ease='OutCubic'),
                    dict(floor=i,time=origin+(start+.5)*beat,duration=.5*beat,offset=[0,0],ease='InCubic')]
        # ThirdSun.Bounce335 is a second, independent chapter coroutine.
        # Relative moves are in the scene's XY axes, not each tile's angle.
        groups=((379,381),(382,384),(385,387)) if data['code']=='T4EX-X' else ((335,),(336,),(337,))
        if len(notes)>max(groups[-1]):
            for j,(ids,offset) in enumerate(zip(groups,((.25,.433),(.5,0),(.25,-.433)))):
                start=170+j*1.332
                for i in ids:
                    chart['neo_motion_events'] += [
                        dict(floor=i,time=chapter_time(chart,start),duration=.666*beat,
                             offset=[v/data['native_tile_size'] for v in offset],ease='OutCubic'),
                        dict(floor=i,time=chapter_time(chart,start+.666),duration=.666*beat,
                             offset=[0,0],ease='InCubic')]
    if data['code'] in ('T3-X','T3EX-X'):
        from neo_warps import compile_math
        compile_math(data,chart)
        if data.get('native_fog'):chart['mawaru_fog']=data['native_fog']
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
            # The alternate routes are scene sprites; the real routes are
            # rhythm floors. Their reveal must match as well as their tint,
            # otherwise full-bright real floors give away the answer early.
            branches=[i]+[root+j for root in (i,i+12) for j in (1,2,3)]
            for branch in branches:
                chart['neo_opacity_events'] += [dict(floor=branch,time=0,duration=0,opacity=0),
                    dict(floor=branch,time=chapter_time(chart,start),duration=8*60/170,opacity=1),
                    dict(floor=branch,time=chapter_time(chart,end),duration=8*60/170,opacity=0)]
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
    for section,(first,count,approach) in enumerate(sections):
        setup=round(chapter_time(chart,489 if section==0 else 962)*FPS)
        for k in range(count):
            i=first+2*k;n=notes[i];center=notes[i+1]
            dx=n['x']-center['x'];dy=n['y']-center['y'];radius=math.hypot(dx,dy)
            start=max(setup,n['frame']-round(approach*FPS))
            duration=max(1,n['frame']-start)
            # Original spawn distance is 13 Unity units (85% after first).
            # Defense floors use a larger native radius. Match the cartridge's
            # 24-pixel orbit so the visible projectile meets the moving planet.
            distance=13*24/data['native_tile_size']*(1 if not k else .85)*24/radius
            chart['neo_meteors'].append(dict(start=start,end=n['frame'],judge=i+1,
                dx=round(dx/radius*24),dy=round(dy/radius*24),
                vx=round(dx/radius*(distance-24)*256/duration),
                vy=round(dy/radius*(distance-24)*256/duration)))
            for j in (i,i+1):notes[j]['scene_hidden']=True
