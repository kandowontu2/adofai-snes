"""Sample authored planet visibility/size without evaluating tweens on cartridge."""
import bisect,json
from pathlib import Path
from track_motion import enabled,easing
from make_assets import FPS
ROOT=Path(__file__).resolve().parents[1]
TARGETS={'All':(0,1,2),'Both':(0,1,2),'FirePlanet':(0,),'IcePlanet':(1,),'GreenPlanet':(2,)}


def conditional_scales(data,chart):
    """Instant perfect callbacks, retained until the next authored size event.

    Tagged events are blueprints, not scheduled animation. The runtime reads
    the actual recorded judgment; Watch records the same perfect grade.
    Unsupported callback timing must fail rather than reveal a hidden orb.
    """
    actions=[a for a in data.get('featured_actions',[]) if enabled(a.get('active',True))]
    tagged=[a for a in actions if a['eventType']=='ScalePlanets' and a.get('eventTag')]
    if not tagged:return []
    conditions={a['floor']:a for a in actions if a['eventType']=='SetConditionalEvents'}
    points=sorted(conditions)
    rows=[]
    for action in tagged:
        if action.get('duration',0) or action.get('angleOffset',0):
            raise ValueError('Conditional planet scaling needs an instant, unshifted event')
        tag=action['eventTag'];triggers=[]
        for at,first in enumerate(points):
            condition=conditions[first]
            references=[k for k,v in condition.items() if k.endswith('Tag') and v==tag]
            if not references:continue
            if references!=['perfectTag']:
                raise ValueError(('Unsupported planet-scale judgment callback',tag,references))
            end=points[at+1] if at+1<len(points) else len(chart['notes'])
            triggers.extend(range(first,end))
        if not triggers:raise ValueError(('Unresolved planet-scale callback',tag))
        value=max(0,min(32,round(action['scale']/100*16)))*16
        for floor in triggers:
            note=chart['notes'][floor]
            for target in TARGETS[action['targetPlanet']]:
                following=[]
                for other in actions:
                    if other['eventType']!='ScalePlanets' or other.get('eventTag'):continue
                    if target not in TARGETS[other['targetPlanet']]:continue
                    n=chart['notes'][other['floor']]
                    beat=60/data['bpm']/n['speed']*FPS
                    start=max(0,round(n['time']*FPS+other.get('angleOffset',0)/180*beat))
                    if start>note['frame']:following.append((start,other.get('duration',0)))
                expiry,duration=min(following) if following else (chart['notes'][-1]['frame']+121,0)
                if duration:raise ValueError('Conditional planet scaling cannot resume a precomputed tween')
                assert 0<=floor<65536 and expiry<65536,'Conditional planet-scale address capacity'
                rows.append([floor,expiry,target*2,value])
    return sorted(rows,key=lambda row:row[0])

def schedule(data,chart):
    from gameplay_decorations import simple_planet_proxies
    if not data.get('_core_planets_only') and (data.get('id') in (155,158) or data.get('live_planet_visuals') or simple_planet_proxies(data)):
        # Several author-created circles take turns representing each live
        # planet. Keep the union of their visibility, not the last proxy in
        # the source file (which belongs to a much later scene).
        from decoration_tracks import expanded_moves,Tween
        moves=expanded_moves(data,chart);proxies=[[],[]]
        ordinary=schedule(dict(data,id=None,live_planet_visuals=False,live_planet_proxies=False,_core_planets_only=True),chart)
        ordinary={row[0]:row[1:] for row in ordinary};core=[256]*3
        for dec in data.get('featured_decorations',[]):
            target=dec.get('relativeTo')
            if target not in ('RedPlanet','BluePlanet'):continue
            tags=set(dec.get('tag','').split());tracks=[]
            for key,initial in [('visible',int(enabled(dec.get('visible',True)))),('opacity',dec.get('opacity',100))]:
                commands=[(start,duration,int(enabled(e[key])) if key=='visible' else e[key],e.get('ease','Linear'))
                          for start,_,duration,e in moves if key in e and tags.intersection(e.get('tag','').split())]
                tracks.append(Tween(initial,commands))
            scale=dec.get('scale',[100,100]);scale=[scale,scale] if isinstance(scale,(int,float)) else scale
            for axis in range(2):
                commands=[]
                for start,_,duration,e in moves:
                    if 'scale' not in e or not tags.intersection(e.get('tag','').split()):continue
                    value=e['scale'];value=[value,value] if isinstance(value,(int,float)) else value
                    if value[axis] is not None:commands.append((start,duration,value[axis],e.get('ease','Linear')))
                tracks.append(Tween(scale[axis],commands))
            color=dec.get('planetColor' if dec.get('objectType')=='Planet' else 'color','ffffff')
            commands=[]
            for start,_,duration,e in moves:
                if not tags.intersection(e.get('tag','').split()):continue
                value=e.get('planet_color' if dec.get('objectType')=='Planet' else 'color')
                if value:commands.append((start,duration,int(value[6:8] or 'ff',16),e.get('ease','Linear')))
            tracks.append(Tween(int(color[6:8] or 'ff',16),commands))
            proxies[target=='BluePlanet'].append(tracks)
        rows=[]
        for frame in range(chart['notes'][-1]['frame']+121):
            core=ordinary.get(frame,core)
            values=[max(core[i],256 if any(v.at(frame)>.5 and o.at(frame)>0 and abs(sx.at(frame))>.001 and abs(sy.at(frame))>.001 and a.at(frame)>0
                                          for v,o,sx,sy,a in group) else 0) for i,group in enumerate(proxies)]+[core[2]]
            if not rows or values!=rows[-1][1:]:rows.append([frame,*values])
        return rows
    # A hidden core planet can have a separate, visible author-created
    # planet proxy. The cartridge's live sprite represents that proxy.
    if data.get('live_planet_proxies'):
        from decoration_tracks import expanded_moves,Tween
        proxies={d['relativeTo']:d for d in data.get('featured_decorations',[])
                 if d.get('relativeTo') in ('RedPlanet','BluePlanet')}
        if not proxies:return []
        moves=expanded_moves(data,chart);tracks=[]
        for key in ('RedPlanet','BluePlanet'):
            dec=proxies[key];tags=set(dec.get('tag','').split())
            commands=[(start,duration,e['opacity'],e.get('ease','Linear'))
                      for start,_,duration,e in moves if 'opacity' in e
                      and tags.intersection(e.get('tag','').split())]
            tracks.append(Tween(dec.get('opacity',100),commands))
        rows=[]
        for frame in range(chart['notes'][-1]['frame']+121):
            values=[256 if t.at(frame)>0 else 0 for t in tracks]+[256]
            if not rows or values!=rows[-1][1:]:rows.append([frame,*values])
        return rows if any(0 in r[1:] for r in rows) else []
    commands=[[],[],[]]
    for order,a in enumerate(data.get('featured_actions',[])):
        if a['eventType']!='ScalePlanets' or not enabled(a.get('active',True)):continue
        if a.get('eventTag'):
            # Validate callback support; it must not enter the default pose.
            conditional_scales(data,chart)
            continue
        n=chart['notes'][a['floor']];beat=60/data['bpm']/n['speed']*FPS
        start=max(0,round(n['time']*FPS+a.get('angleOffset',0)/180*beat))
        targets=TARGETS[a['targetPlanet']]
        for target in targets:commands[target].append((start,order,a.get('duration',0)*beat,a['scale']/100,a.get('ease','Linear')))
    if not any(commands):return []
    tracks=[]
    for row in commands:
        row.sort();track=[]
        for start,order,duration,target,ease in row:
            previous=1.
            if track:
                at,length,origin,end,curve=track[-1]
                phase=1 if length<=0 else min(1,max(0,(start-at)/length))
                previous=origin+(end-origin)*easing(curve,phase)
            track.append((start,duration,previous,target,ease))
        tracks.append(([r[0] for r in track],track))
    rows=[]
    for frame in range(chart['notes'][-1]['frame']+121):
        values=[]
        for times,track in tracks:
            value=1.
            index=bisect.bisect_right(times,frame)-1
            if index>=0:
                start,duration,previous,target,ease=track[index]
                phase=1 if duration<=0 else min(1,(frame-start)/duration)
                value=previous+(target-previous)*easing(ease,phase)
            values.append(max(0,min(32,round(value*16)))*16)
        if not rows or values!=rows[-1][1:]:rows.append([frame,*values])
    return rows

def tables(folder,levels):
    from pack_sources import source_path
    entries=[];rows=[];callbacks=[];callback_ranges=[]
    for local,n in enumerate(levels):
        path=source_path(folder,n)
        if not path.exists():continue
        data=json.loads(path.read_text())
        if not data.get('planet_scale_import'):continue
        chart=json.loads((Path(folder)/f'level{n}.json').read_text())
        calls=conditional_scales(data,chart)
        events=schedule(data,chart)
        if calls and not events:events=[[0,256,256,256]]
        if events:
            start=len(rows)*8;rows.extend(events);entries.append((local,start,len(rows)*8))
            first=len(callbacks)*8;callbacks.extend(calls)
            callback_ranges.append((first,len(callbacks)*8))
    if not entries:return ''
    assert len(rows)*8<32768, 'Binary-search midpoint must fit a 16-bit sum'
    segment='FARSCALE' if len(levels)>=200 else 'NEOCODE'
    text='\n.segment "'+segment+'"\nPLANET_SCALE_LEVEL_COUNT = '+str(len(entries))+'\n'+''.join(
        label+': .word '+','.join(str(row[column]) for row in entries)+'\n'
        for column,label in enumerate(('planet_scale_levels','planet_scale_starts','planet_scale_ends')))+\
        'planet_scale_rows: .word '+','.join(str(v) for row in rows for v in row)+'\n'+\
        'planet_scale_radii: .byte '+','.join(str(min(15,(radius*scale+8)//16)) for scale in range(33) for radius in range(16))+'\n'
    if callbacks:
        assert len(callbacks)*8<65536,'Conditional planet-scale table capacity'
        text+='PLANET_SCALE_CALLBACK_COUNT = '+str(len(callbacks))+'\n'+''.join(
            label+': .word '+','.join(str(row[column]) for row in callback_ranges)+'\n'
            for column,label in enumerate(('planet_scale_callback_starts','planet_scale_callback_ends')))
        text+='planet_scale_callbacks: .word '+','.join(str(v) for row in callbacks for v in row)+'\n'
    return text+'\n.segment "RODATA"\n'
