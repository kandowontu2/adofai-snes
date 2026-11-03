"""Compile tile translation and optional rotation on the musical timeline.

The chart controls sampling frequency. Opacity is compiled separately;
gradual per-tile scaling is not implemented.
"""
import collections,math
from make_assets import FPS
from track_events import gameplay_actions

def enabled(value):
    return value.lower() in ('enabled','true','yes','on','1') if isinstance(value,str) else bool(value)

def native_event_time(data,chart,event):
    """SetFxPlusFromComponents recalculates serialized editor timestamps."""
    note=chart['notes'][event['floor']]
    return note['time']+event.get('degreeOffset',0)/180*60/data['bpm']/note['speed']

def native_duration(data,chart,event):
    value=event.get('duration',0)
    if data.get('native_component_notation',False):
        value*=60/data['bpm']/chart['notes'][event['floor']]['speed']
    return value

def stick_schedule(data,count):
    """Decorative MoveTrack offsets only move planets on sticky floors."""
    if 'native_controller_stick_to_floor' in data:
        return [bool(data['native_controller_stick_to_floor'])]*count
    native=data.get('native_stick_to_floors')
    if native is not None:return list(native)
    current=enabled(data.get('track_settings',{}).get('stickToFloors',False))
    events=collections.defaultdict(list)
    for a in data.get('track_actions',[]):
        if a.get('active',True) and a['eventType']=='PositionTrack' and not enabled(a.get('editorOnly',False)):
            events[a['floor']].append(a)
    values=[]
    for i in range(count):
        value=current
        for a in events[i]:
            if 'stickToFloors' in a:
                value=enabled(a['stickToFloors'])
                if not enabled(a.get('justThisTile',False)):current=value
        values.append(value)
    return values

def ease_name(value):
    names=['Unset','Linear','InSine','OutSine','InOutSine','InQuad','OutQuad','InOutQuad','InCubic','OutCubic','InOutCubic',
           'InQuart','OutQuart','InOutQuart','InQuint','OutQuint','InOutQuint','InExpo','OutExpo','InOutExpo','InCirc','OutCirc',
           'InOutCirc','InElastic','OutElastic','InOutElastic','InBack','OutBack','InOutBack','InBounce','OutBounce','InOutBounce']
    return names[value] if isinstance(value,int) and 0<=value<len(names) else str(value)

def easing(name,t):
    name=ease_name(name)
    if name=='Linear':return t
    mode='InOut' if name.startswith('InOut') else 'Out' if name.startswith('Out') else 'In'
    kind=name[len(mode):]
    if kind=='Elastic' and mode=='InOut':
        if t in (0,1):return t
        c=2*math.pi/4.5
        return -(2**(20*t-10)*math.sin((20*t-11.125)*c))/2 if t<.5 else (2**(-20*t+10)*math.sin((20*t-11.125)*c))/2+1
    if kind=='Back' and mode=='InOut':
        c=1.70158*1.525
        return ((2*t)**2*((c+1)*2*t-c))/2 if t<.5 else ((2*t-2)**2*((c+1)*(2*t-2)+c)+2)/2
    def bounce(v):
        if v<1/2.75:return 7.5625*v*v
        if v<2/2.75:v-=1.5/2.75;return 7.5625*v*v+.75
        if v<2.5/2.75:v-=2.25/2.75;return 7.5625*v*v+.9375
        v-=2.625/2.75;return 7.5625*v*v+.984375
    def inside(v):
        if kind in ('Quad','Cubic','Quart','Quint'):return v**{'Quad':2,'Cubic':3,'Quart':4,'Quint':5}[kind]
        if kind=='Sine':return 1-math.cos(v*math.pi/2)
        if kind=='Expo':return 0 if v==0 else 2**(10*v-10)
        if kind=='Circ':return 1-math.sqrt(max(0,1-v*v))
        if kind=='Back':return 2.70158*v**3-1.70158*v*v
        if kind=='Elastic':return v if v in (0,1) else -(2**(10*v-10))*math.sin((v*10-10.75)*2*math.pi/3)
        if kind=='Bounce':return 1-bounce(1-v)
        return v
    if mode=='Out':return 1-inside(1-t)
    if mode=='InOut':return inside(2*t)/2 if t<.5 else 1-inside(2-2*t)/2
    return inside(t)

def motion_schedule(data,chart):
    notes=chart['notes'];count=len(notes);commands=[[] for _ in notes]
    beat=lambda i:60/data['bpm']/notes[i]['speed']
    initial=[(0.,0.) for _ in notes]
    by_floor=collections.defaultdict(list)
    for a in data.get('track_actions',[]):
        if a.get('active',True) and a['eventType']=='PositionTrack' and not enabled(a.get('editorOnly',False)):by_floor[a['floor']].append(a)
    carry=(0.,0.)
    for i,n in enumerate(notes):
        value=carry
        for a in by_floor[i]:
            if a.get('positionOffset') is None:continue
            value=tuple(old+(v or 0)*24*sign for old,v,sign in zip(value,a['positionOffset'],(1,-1)))
            offset,relative=a.get('relativeTo',[0,'ThisTile'])
            target=max(0,min(count-1,offset+(i if relative=='ThisTile' else count-1 if relative=='End' else 0)))
            if target!=i:
                value=tuple(v+notes[target][axis]+initial[target][j]-n[axis]-carry[j] for j,(axis,v) in enumerate(zip(('x','y'),value)))
            if not enabled(a.get('justThisTile',False)):carry=value
        initial[i]=value
    for n,offset in zip(notes,initial):n['position_track_offset']=[round(v) for v in offset]
    def add(j,t,duration,pos,ease='Linear'):
        if 0<=j<count and any(v is not None and math.isfinite(v) for v in pos):commands[j].append((max(0,t),max(0,duration),pos,ease))
    for e in data.get('native_track_effects',[]):
        if e['type']!='ffxMoveFloorPlus' or not e.get('positionUsed',True):continue
        i=e['floor'];p=e['targetPos'];pos=[p.get('x'),p.get('y')] if isinstance(p,dict) else p
        t=native_event_time(data,chart,e)
        size=data.get('native_tile_size',1.5)
        pos=[None if v is None else v/size for v in pos]
        for j in range(min(e['start'],e['end']),max(e['start'],e['end'])+1,1+e.get('gapLength',0)):
            add(j,t,native_duration(data,chart,e),pos,ease_name(e.get('ease','Linear')))
    actions=gameplay_actions(data)
    repeats={}
    for a in actions:
        if a['eventType']=='RepeatEvents':
            for tag in a.get('tag','').split():repeats[a['floor'],tag]=a
    def tile(value,floor):
        offset,relative=value
        return max(0,min(count-1,offset+(floor if relative=='ThisTile' else count-1 if relative=='End' else 0)))
    for a in actions:
        if a['eventType']!='MoveTrack' or a.get('positionOffset') is None:continue
        floor=a['floor'];repeat=next((repeats[floor,t] for t in a.get('eventTag','').split() if (floor,t) in repeats),{})
        mode=repeat.get('repeatType','Beat');amount=repeat.get('repetitions',0) if mode=='Beat' else repeat.get('floorCount',0)
        for k in range(amount+1):
            current=floor+(k*repeat.get('gapLength',1) if mode=='Floor' else 0)
            if current>=count:break
            origin=current if enabled(repeat.get('executeOnCurrentFloor',False)) else floor
            t=notes[current]['time']+a.get('angleOffset',0)/180*beat(origin)
            if mode=='Beat':t+=k*repeat.get('interval',1)*beat(floor)
            start=tile(a.get('startTile',[0,'ThisTile']),origin);end=tile(a.get('endTile',[0,'ThisTile']),origin)
            for j in range(min(start,end),max(start,end)+1,1+a.get('gapLength',0)):
                add(j,t,a.get('duration',0)*beat(origin),a['positionOffset'],a.get('ease','Linear'))
    changes=collections.defaultdict(dict)
    for i,value in enumerate(initial):
        if value!=(0.,0.):changes[0][i]=tuple(round(v) for v in value)
    for i,events in enumerate(commands):
        axes=[{},{}]
        # Each axis has its own original tween. A null X must not cancel a
        # running X tween when an action changes only Y (and vice versa).
        for axis,sign in enumerate((1,-1)):
            selected=sorted(((t,d,p[axis],ease) for t,d,p,ease in events if p[axis] is not None and math.isfinite(p[axis])),key=lambda e:e[0])
            target=initial[i][axis]
            for k,(t,duration,pos,ease) in enumerate(selected):
                start=target
                # PrepVfx captures startPos after PositionTrack placement.
                # A MoveTrack offset is relative to that authored start.
                target=initial[i][axis]+pos*24*sign
                stop=selected[k+1][0] if k+1<len(selected) else math.inf
                frames=list(range(round(t*FPS),round((t+duration)*FPS),chart.get('motion_step',8) if chart.get('mode7') else 4))+[round((t+duration)*FPS)]
                for f in frames:
                    if f/FPS>stop+1/FPS:break
                    phase=1 if not duration else max(0,min(1,(f/FPS-t)/duration))
                    axes[axis][f]=round(start+(target-start)*easing(ease,phase))
        value=tuple(round(v) for v in initial[i])
        for frame in sorted(set(axes[0])|set(axes[1])):
            new=tuple(axes[axis].get(frame,value[axis]) for axis in range(2))
            if new!=value:changes[frame][i]=new;value=new
    return dict(sorted(changes.items()))

def rotation_schedule(data,chart):
    """MoveTrack rotation is an independent absolute offset from the floor pose."""
    notes=chart['notes'];count=len(notes);commands=[[] for _ in notes]
    actions=gameplay_actions(data);repeats={}
    for a in actions:
        if a['eventType']=='RepeatEvents':
            for tag in a.get('tag','').split():repeats[a['floor'],tag]=a
    def tile(value,floor):
        offset,relative=value
        return max(0,min(count-1,offset+(floor if relative=='ThisTile' else count-1 if relative=='End' else 0)))
    for a in actions:
        value=a.get('rotationOffset')
        if a['eventType']!='MoveTrack' or value is None or not math.isfinite(value):continue
        floor=a['floor'];repeat=next((repeats[floor,t] for t in a.get('eventTag','').split() if (floor,t) in repeats),{})
        mode=repeat.get('repeatType','Beat');amount=repeat.get('repetitions',0) if mode=='Beat' else repeat.get('floorCount',0)
        for k in range(amount+1):
            current=floor+(k*repeat.get('gapLength',1) if mode=='Floor' else 0)
            if current>=count:break
            origin=current if enabled(repeat.get('executeOnCurrentFloor',False)) else floor
            beat=60/data['bpm']/notes[origin]['speed']
            t=notes[current]['time']+a.get('angleOffset',0)/180*beat
            if mode=='Beat':t+=k*repeat.get('interval',1)*60/data['bpm']/notes[floor]['speed']
            start=tile(a.get('startTile',[0,'ThisTile']),origin);end=tile(a.get('endTile',[0,'ThisTile']),origin)
            for j in range(min(start,end),max(start,end)+1,1+a.get('gapLength',0)):
                commands[j].append((max(0,t),max(0,a.get('duration',0)*beat),value,a.get('ease','Linear')))
    changes=collections.defaultdict(dict)
    for i,events in enumerate(commands):
        previous=None;last=0
        def evaluate(event,t):
            at,duration,start,target,ease=event
            phase=1 if not duration else max(0,min(1,(t-at)/duration))
            return start+(target-start)*easing(ease,phase)
        events.sort(key=lambda e:e[0])
        for k,(at,duration,target,ease) in enumerate(events):
            # Starting another tween completes the old rotation first.
            start=previous[3] if previous else 0
            previous=(at,duration,start,target,ease)
            stop=events[k+1][0] if k+1<len(events) else math.inf
            frames=list(range(round(at*FPS),round((at+duration)*FPS),chart.get('motion_step',8)))+[round((at+duration)*FPS)]
            for frame in frames:
                if frame/FPS>stop+1/FPS:break
                value=target if frame==round((at+duration)*FPS) else round(evaluate(previous,frame/FPS),5)
                if value!=last:changes[frame][i]=value;last=value
    return dict(sorted(changes.items()))

def nearby_motion(chart,motion,initial=None,visibility=None):
    """Follow authored movement on visible tiles; dense fallback stays local."""
    if initial is not None:
        alpha=list(initial);last=[(0,0)]*len(alpha);shown=[None]*len(alpha)
        changes=collections.defaultdict(dict);visibility=visibility or {}
        detail=chart.get('readability_detail_starts')
        starts=collections.defaultdict(list)
        if detail:
            for i,at in enumerate(detail):starts[at].append(i)
        for frame in sorted({0}|set(motion)|set(visibility)|set(starts)):
            prior=list(alpha)
            for i,value in motion.get(frame,{}).items():last[i]=value
            for i,value in visibility.get(frame,{}).items():alpha[i]=value
            candidates=set(motion.get(frame,{}))|set(visibility.get(frame,{}))
            candidates.update(starts.get(frame,[]))
            if frame==0:candidates.update(i for i,a in enumerate(alpha) if a)
            for i in candidates:
                if not alpha[i]:continue
                detailed=(frame>=detail[i] if detail else alpha[i]>1)
                # Decorative offsets can scatter a tile far from the real
                # path. Keep the active nonsticky route under the planets;
                # the distant silhouette still shows its authored movement.
                value=last[i] if chart.get('authored_visibility') else (0,0) if detailed and not chart['notes'][i].get('stick_to_floor',True) else last[i]
                if not chart.get('nearby_motion_only',False) or detailed or not prior[i] or shown[i] is None:
                    if shown[i]!=value:changes[frame][i]=value;shown[i]=value
        return dict(sorted(changes.items()))
    notes=chart['notes'];changes=collections.defaultdict(dict);last=[(0,0)]*len(notes)
    starts=collections.defaultdict(list)
    for i in range(len(notes)):starts[notes[max(0,i-4)]['frame']].append(i)
    for frame in sorted(set(starts)|set(motion)):
        for i,value in motion.get(frame,{}).items():last[i]=value
        for i in starts.get(frame,[]):
            if last[i]!=(0,0):changes[frame][i]=last[i]
        for i,value in motion.get(frame,{}).items():
            if notes[max(0,i-4)]['frame']<=frame<=notes[min(len(notes)-1,i+2)]['frame']:
                changes[frame][i]=value
    return dict(sorted(changes.items()))
