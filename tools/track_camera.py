"""Original orthographic zoom events sampled into SNES Mode 7 matrices."""
import math
from make_assets import FPS
from track_motion import easing,ease_name,native_event_time,native_duration

def follow_schedule(chart,motion,data=None):
    """One song-clock trajectory shared by viewport streaming and sprites.

    Focus the occupied floor, never a future route point. Subpixel easing
    is sampled before integer rasterization, independently of dropped frames.
    """
    notes=chart['notes'];offsets=[(0,0)]*len(notes)
    x=float(notes[0]['x']);y=float(notes[0]['y']);i=0;result=[];last=None
    for frame in range(notes[-1]['frame']+121):
        for j,p in motion.get(frame,{}).items():offsets[j]=p
        while i+1<len(notes) and notes[i+1]['frame']<=frame:i+=1
        dx,dy=offsets[i] if notes[i].get('stick_to_floor',True) else notes[i].get('position_track_offset',(0,0))
        x+=(notes[i]['x']+dx-x)*.25;y+=(notes[i]['y']+dy-y)*.25
        p=(round(x)-128,round(y)-96)
        if p!=last:result.append((frame,*p));last=p
    if data is not None:result=position_schedule(data,chart,motion,result)
    chart['camera_follow_versions']=[list(p) for p in result]
    return result


def position_schedule(data,chart,motion,follow):
    """ffxCameraPlus parent-space movement, with per-axis completed tweens."""
    from track_events import gameplay_actions
    notes=chart['notes'];settings=data.get('track_settings',{})
    actions=gameplay_actions({'track_actions':data.get('camera_actions',[])})
    repeats={}
    for a in actions:
        if a['eventType']=='RepeatEvents':
            for tag in a.get('tag','').split():repeats[a['floor'],tag]=a
    commands=[]
    for a in actions:
        if a['eventType']!='MoveCamera' or not ('position' in a or 'relativeTo' in a):continue
        floor=a['floor'];repeat=next((repeats[floor,t] for t in a.get('eventTag','').split() if (floor,t) in repeats),{})
        kind=repeat.get('repeatType','Beat');amount=repeat.get('repetitions',0) if kind=='Beat' else repeat.get('floorCount',0)
        for k in range(amount+1):
            current=floor+(k*repeat.get('gapLength',1) if kind=='Floor' else 0)
            if current>=len(notes):break
            origin=current if repeat.get('executeOnCurrentFloor',False) else floor
            beat=60/data['bpm']/notes[origin]['speed']
            t=notes[current]['time']+a.get('angleOffset',0)/180*beat
            if kind=='Beat':t+=k*repeat.get('interval',1)*beat
            commands.append((max(0,round(t*FPS)),a.get('duration',0)*beat*FPS,origin,a))
    commands.sort(key=lambda row:row[0]);cursor=0
    mode=settings.get('relativeTo','Player');parent=[0.,0.]
    offset=settings.get('position',[0,0]);world=[notes[0]['x'],notes[0]['y']]
    parent=[(world[j] if mode!='Player' else 0)+(offset[j] or 0)*24*(1 if j==0 else -1) for j in range(2)]
    tweens=[None,None];positions={f:(x+128,y+96) for f,x,y in follow};player=positions[0]
    initial_offsets=motion.get(0,{})
    rotations={f:(c,s) for f,c,s in chart.get('camera_projection_versions',chart.get('camera_rotation_versions',[]))}
    cosine,sine=256,0;constrained=0
    def evaluate(tween,frame):
        at,duration,start,target,ease=tween
        p=1 if duration<=0 else max(0,min(1,(frame-at)/duration))
        return start+(target-start)*easing(ease,p)
    result=[];last=None
    for frame in range(notes[-1]['frame']+121):
        player=positions.get(frame,player)
        cosine,sine=rotations.get(frame,(cosine,sine))
        for j in range(2):
            if tweens[j]:parent[j]=evaluate(tweens[j],frame)
        while cursor<len(commands) and commands[cursor][0]<=frame:
            at,duration,floor,a=commands[cursor];cursor+=1
            changed='relativeTo' in a;newmode=a.get('relativeTo',mode);pos=a.get('position')
            # A mode change treats omitted/null axes as zero. Otherwise a
            # null axis leaves its current tween running.
            used=[changed or (pos is not None and pos[j] is not None) for j in range(2)]
            for j in range(2):
                if used[j] and tweens[j]:parent[j]=tweens[j][3];tweens[j]=None
            if (mode=='Player')!=(newmode=='Player'):
                for j in range(2):parent[j]+=player[j]*(1 if mode=='Player' else -1)
            previous=list(parent);mode=newmode
            base=[0.,0.] if mode=='Player' else [notes[floor]['x']+initial_offsets.get(floor,(0,0))[0],notes[floor]['y']+initial_offsets.get(floor,(0,0))[1]] if mode=='Tile' else world if mode=='Global' else previous
            if settings.get('legacyCamRelativeTo',False) and not changed:base=previous
            for j in range(2):
                if not used[j]:continue
                value=(pos[j] or 0) if pos is not None else 0
                target=base[j]+value*24*(1 if j==0 else -1)
                tweens[j]=(at,duration,parent[j],target,a.get('ease','Linear'))
                parent[j]=evaluate(tweens[j],frame)
        center=[parent[j]+(player[j] if mode=='Player' else 0) for j in range(2)]
        # Keep the orbit within the shorter SNES playfield. The projection
        # matrix includes inverse zoom in experimental zoom builds.
        dx,dy=center[0]-player[0],center[1]-player[1]
        sx=(cosine*dx-sine*dy)/256;sy=(sine*dx+cosine*dy)/256
        cx=max(-88,min(88,sx));cy=max(-24,min(24,sy))
        if (cx,cy)!=(sx,sy):
            constrained+=1;norm=(cosine*cosine+sine*sine)/256
            center=[player[0]+(cosine*cx+sine*cy)/norm,player[1]+(-sine*cx+cosine*cy)/norm]
        p=tuple(round(center[j])-(128 if j==0 else 96) for j in range(2))
        if p!=last:result.append((frame,*p));last=p
    chart['camera_position_events']=len(commands)
    chart['camera_position_constrained_frames']=constrained
    return result

def camera_schedule(data,chart):
    notes=chart['notes'];count=len(notes);commands=[]
    beat=lambda i:60/data['bpm']/notes[i]['speed']
    initial=float(data.get('camera_initial',1.))
    for e in data.get('native_camera_effects',[]):
        i=e['floor']
        if not e.get('zoomUsed',True):continue
        t=native_event_time(data,chart,e)
        commands.append((max(0,t),max(0,native_duration(data,chart,e)),e['targetZoom'],ease_name(e.get('ease','Linear'))))
    from track_events import gameplay_actions
    actions=gameplay_actions({'track_actions':data.get('camera_actions',[])})
    repeats={}
    for a in actions:
        if a['eventType']=='RepeatEvents':
            for tag in a.get('tag','').split():repeats[a['floor'],tag]=a
    for a in actions:
        if a['eventType']!='MoveCamera' or a.get('zoom') is None:continue
        floor=a['floor'];repeat=next((repeats[floor,t] for t in a.get('eventTag','').split() if (floor,t) in repeats),{})
        mode=repeat.get('repeatType','Beat');amount=repeat.get('repetitions',0) if mode=='Beat' else repeat.get('floorCount',0)
        for k in range(amount+1):
            current=floor+(k*repeat.get('gapLength',1) if mode=='Floor' else 0)
            if current>=count:break
            origin=current if repeat.get('executeOnCurrentFloor',False) else floor
            t=notes[current]['time']+a.get('angleOffset',0)/180*beat(origin)
            if mode=='Beat':t+=k*repeat.get('interval',1)*beat(floor)
            commands.append((max(0,t),max(0,a.get('duration',0)*beat(origin)),a['zoom']/100,a.get('ease','Linear')))
    commands.sort(key=lambda e:e[0]);values={0:initial};prior_target=initial
    for i,(t,duration,target,ease) in enumerate(commands):
        if not math.isfinite(target):continue
        # ffxCameraPlus kills a previous tween with complete:true, then
        # starts the new tween from that completed target.
        start=prior_target;prior_target=target
        first=round(t*FPS);last_frame=round((t+duration)*FPS)
        stop=round(commands[i+1][0]*FPS)-1 if i+1<len(commands) else last_frame
        for frame in range(first,min(last_frame,stop)+1):
            phase=1 if not duration or frame==last_frame else min(1,max(0,(frame/FPS-t)/duration))
            values[frame]=start+(target-start)*easing(ease,phase)
    result=[];last=None
    for frame,value in sorted(values.items()):
        matrix=max(-32767,min(32767,round(value*256)))
        if value and not matrix:matrix=1 if value>0 else -1
        inverse=0 if not matrix else max(-32767,min(32767,round(65536/matrix)))
        pair=(matrix,inverse)
        if pair!=last:result.append((frame,*pair));last=pair
    chart['camera_zoom_versions']=[list(v) for v in result]
    chart['camera_zoom_events']=len(commands)
    return result


def rotation_schedule(data, chart):
    """Sample ffxCameraPlus' unwrapped, completed-target rotation tweens.

    Matrix values are signed 8.8, with no zoom. Unity's positive camera
    angle becomes a clockwise screen-space track rotation (screen Y down).
    """
    from track_events import gameplay_actions
    notes=chart['notes'];commands=[]
    beat=lambda i:60/data['bpm']/notes[i]['speed']
    initial=float(data.get('camera_rotation_initial',0))
    for e in data.get('native_camera_effects',[]):
        i=e['floor'];mode=e.get('movementType',0)
        relative=e.get('movementTypeUsed',True) and mode in (3,'LastPosition')
        reset=e.get('movementTypeUsed',True) and mode in (4,'LastPositionNoRotation')
        if not (e.get('rotationUsed',True) or relative or reset):continue
        t=native_event_time(data,chart,e)
        commands.append((max(0,t),max(0,native_duration(data,chart,e)),e.get('targetRot',0),ease_name(e.get('ease','Linear')),relative))
    actions=gameplay_actions({'track_actions':data.get('camera_actions',[])})
    repeats={}
    for a in actions:
        if a['eventType']=='RepeatEvents':
            for tag in a.get('tag','').split():repeats[a['floor'],tag]=a
    for a in actions:
        if a['eventType']!='MoveCamera':continue
        relative=a.get('relativeTo')=='LastPosition'
        if a.get('rotation') is None and a.get('relativeTo') not in ('LastPosition','LastPositionNoRotation'):continue
        floor=a['floor']
        repeat=next((repeats[floor,t] for t in a.get('eventTag','').split() if (floor,t) in repeats),{})
        mode=repeat.get('repeatType','Beat');amount=repeat.get('repetitions',0) if mode=='Beat' else repeat.get('floorCount',0)
        for k in range(amount+1):
            current=floor+(k*repeat.get('gapLength',1) if mode=='Floor' else 0)
            if current>=len(notes):break
            origin=current if repeat.get('executeOnCurrentFloor',False) else floor
            t=notes[current]['time']+a.get('angleOffset',0)/180*beat(origin)
            if mode=='Beat':t+=k*repeat.get('interval',1)*beat(floor)
            commands.append((max(0,t),max(0,a.get('duration',0)*beat(origin)),a.get('rotation') or 0,a.get('ease','Linear'),relative))
    commands=[c for c in commands if all(math.isfinite(v) for v in c[:3])]
    commands.sort(key=lambda e:e[0]);values={0:initial};prior=initial
    for i,(t,duration,target,ease,relative) in enumerate(commands):
        start=prior;target+=prior if relative else 0;prior=target
        first=round(t*FPS);end=round((t+duration)*FPS)
        stop=round(commands[i+1][0]*FPS)-1 if i+1<len(commands) else end
        for frame in range(first,min(end,stop)+1):
            phase=1 if not duration or frame==end else min(1,max(0,(frame/FPS-t)/duration))
            values[frame]=start+(target-start)*easing(ease,phase)
    result=[];last=None
    for frame,angle in sorted(values.items()):
        radians=math.radians(angle)
        pair=(round(math.cos(radians)*256),round(math.sin(radians)*256))
        if pair!=last:result.append([frame,*pair]);last=pair
    chart['camera_rotation_phase_versions']=[[f,round(a*256/360)&255] for f,a in sorted(values.items())]
    chart['camera_rotation_versions']=result
    chart['camera_rotation_events']=len(commands)
    return result


def mode7_zoom_schedule(chart):
    """Experimental, opt-in sampling and inverse world-to-screen projection.

    Compilation validates texture capacity; runtime PPU verification remains
    mandatory. Wider views can exceed VBlank even when their textures fit.
    """
    rotations={f:(c,s) for f,c,s in chart.get('camera_rotation_versions',[[0,256,0]])}
    zooms={f:z for f,z,_ in chart['camera_zoom_versions']}
    c,s,z=256,0,256;sampling=[];projection=[];world=[];shifts=[];shift=0;last=None
    forced=chart.get('raster_capacity_windows',[])
    boundaries={f for a,b in forced for f in (a,b)}
    for frame in sorted(set(rotations)|set(zooms)|boundaries):
        c,s=rotations.get(frame,(c,s));z=zooms.get(frame,z)
        if not 128<=z<=640:
            raise ValueError(f"{chart.get('code')}: zoom {z/256:g} exceeds experimental 0.5-2.5 range")
        if chart.get('adaptive_raster'):
            if z>320:shift=1
            elif z<=288:shift=0
            shift=max(shift,chart.get('raster_min_shift',0))
            if any(a<=frame<b for a,b in forced):shift=1
        original=(round(c*z/256),round(s*z/256))
        pair=tuple(round(v/(1<<shift)) for v in original)
        # Invert the quantized PPU matrix, not its unquantized source.
        norm=original[0]**2+original[1]**2
        inv=tuple(round(v*65536/norm) for v in original)
        if (pair,inv,shift)!=last:
            sampling.append([frame,*pair]);projection.append([frame,*inv])
            world.append([frame,*original]);shifts.append([frame,shift]);last=pair,inv,shift
    chart['camera_sampling_versions']=sampling
    if chart.get('adaptive_raster'):
        chart['camera_world_sampling_versions']=world
        chart['camera_raster_shift_versions']=[v for i,v in enumerate(shifts) if not i or v[1]!=shifts[i-1][1]]
    chart['camera_projection_versions']=projection
    chart['mode7_zoom_enabled']=True
    chart['pattern_pinned_limit']=0
