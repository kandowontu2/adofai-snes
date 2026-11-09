"""Compile authored tile colors into sixteen independently animated palettes.

Six CGRAM entries per visible material preserve three depth intensities and
one-pixel edges. Geometry uses stable material slots; fades change CGRAM,
not the tile patterns. Textures, shader bloom and audio-volume colors are
outside this renderer. Color animations use song time at 15 Hz.
"""
import bisect, collections, colorsys, math
from make_assets import FPS
from track_motion import enabled, easing, native_event_time, native_duration
from track_events import gameplay_actions

TYPES=('Single','Stripes','Glow','Blink','Switch','Rainbow','Volume')
STYLES=('Standard','Neon','NeonLight','Basic','Gems','Minimal')
FIELDS=('trackColorType','trackColor','secondaryTrackColor','trackColorAnimDuration',
        'trackColorPulse','trackPulseLength','trackStyle','trackGlowIntensity')
DEFAULT=dict(trackColorType='Single',trackColor='a7c2da',secondaryTrackColor='ffffff',
             trackColorAnimDuration=2,trackColorPulse='None',trackPulseLength=10,trackStyle='Standard')

def rgb(value):
    if isinstance(value,dict):return tuple(max(0,min(1,float(value[k]))) for k in ('r','g','b'))
    value=str(value).lstrip('#')
    return tuple(int(value[i:i+2],16)/255 for i in (0,2,4))

def state(settings,floor,start):
    s=dict(DEFAULT,**settings);kind=s['trackColorType'];style=s['trackStyle']
    if isinstance(kind,int):kind=TYPES[kind]
    if isinstance(style,int):style=STYLES[style]
    a,b=rgb(s['trackColor']),rgb(s['secondaryTrackColor'])
    if kind=='Stripes':a=a if (floor-start)%2==0 else b;kind='Single'
    period=max(.001,float(s['trackColorAnimDuration']));length=max(1,int(s['trackPulseLength']))
    pulse=s['trackColorPulse'];pulse=('None','Forward','Backward')[pulse] if isinstance(pulse,int) else pulse
    phase=(1-floor%length/length) if pulse=='Forward' else floor%length/length if pulse=='Backward' else 0
    glow=0 if s.get('disableGlow',False) else max(0,float(s.get('trackGlowIntensity',100)))/100
    if kind in ('Single','Volume'):return ('Single',a,a,1.,0.,style,glow)
    return (kind,a,b,period,phase,style,glow)

def color(s,seconds):
    kind,a,b,period,phase,style=s[:6];t=(seconds/period+phase)%1
    if kind=='Rainbow':
        _,sat,val=colorsys.rgb_to_hsv(*a)
        return colorsys.hsv_to_rgb(t,sat,val)
    mix=(1-math.cos(t*math.tau))/2 if kind=='Glow' else t if kind=='Blink' else int(t>=.5) if kind=='Switch' else 0
    return tuple(x+(y-x)*mix for x,y in zip(a,b))

def sequences(data,chart):
    notes=chart['notes'];count=len(notes);settings=dict(DEFAULT,**data.get('track_settings',{}))
    by_floor=collections.defaultdict(list);commands=[[] for _ in notes]
    for a in gameplay_actions(data):
        if a.get('active',True):by_floor[a['floor']].append(a)
    native={e['floor']:e for e in data.get('native_track_effects',[]) if e['type']=='ffxChangeTrack'}
    initial=[];original=[];origins=[];start=0
    for i in range(count):
        local=dict(settings);local_start=start
        if not data.get('track_settings'):
            colors=data.get('native_track_colors',[])
            if colors:local.update(trackColor=colors[i]['color'],trackStyle=colors[i]['style'],trackGlowIntensity=colors[i].get('glow',1)*100,disableGlow=colors[i].get('disableGlow',False))
            if i in native:
                e=native[i]
                local.update(trackColor=e['color1'],secondaryTrackColor=e['color2'],trackColorType=e['colorType'],
                             trackColorAnimDuration=e['colorAnimDuration'],trackColorPulse=e['pulseType'],trackPulseLength=e['pulseLength'])
                local_start=e.get('startOfColorChange',0)
        for a in by_floor[i]:
            if a['eventType'] not in ('ColorTrack','ChangeTrack'):continue
            local.update({k:a[k] for k in FIELDS if k in a and a[k] is not None})
            if 'trackColorType' in a:local_start=i
            if not enabled(a.get('justThisTile',False)):settings=dict(local);start=local_start
        initial.append((0,0.,'Linear',state(local,i,local_start)))
        original.append(dict(local));origins.append(local_start)
    beat=lambda i:60/data['bpm']/notes[i]['speed']
    def tile(value,floor):
        offset,relative=value
        return max(0,min(count-1,int(offset)+(floor if relative=='ThisTile' else count-1 if relative=='End' else 0)))
    repeats={}
    for a in gameplay_actions(data):
        if a['eventType']=='RepeatEvents' and a.get('active',True):
            for tag in a.get('tag','').split():repeats[a['floor'],tag]=a
    raw=[]
    for a in gameplay_actions(data):
        if a['eventType']!='RecolorTrack' or not a.get('active',True):continue
        floor=a['floor'];repeat=next((repeats[floor,t] for t in a.get('eventTag','').split() if (floor,t) in repeats),{})
        mode=repeat.get('repeatType','Beat');amount=repeat.get('repetitions',0) if mode=='Beat' else repeat.get('floorCount',0)
        for k in range(amount+1):
            current=floor+(k*repeat.get('gapLength',1) if mode=='Floor' else 0)
            if current>=count:break
            origin=current if enabled(repeat.get('executeOnCurrentFloor',False)) else floor
            t=notes[current]['time']+a.get('angleOffset',0)/180*beat(origin)
            if mode=='Beat':t+=k*repeat.get('interval',1)*beat(floor)
            begin=tile(a.get('startTile',[0,'ThisTile']),origin);end=tile(a.get('endTile',[0,'ThisTile']),origin)
            raw.append((max(0,round(t*FPS)),a.get('duration',0)*beat(origin),a.get('ease','Linear'),min(begin,end),max(begin,end),a.get('gapLength',0),a))
    native_names=dict(color1='trackColor',color2='secondaryTrackColor',colorType='trackColorType',
                      colorAnimDuration='trackColorAnimDuration',pulseType='trackColorPulse',pulseLength='trackPulseLength',style='trackStyle',glowMult='trackGlowIntensity')
    used=dict(color1='usedColor1',color2='usedColor2',colorType='usedColorType',colorAnimDuration='usedColorAnimDuration',
              pulseType='usedPulseType',pulseLength='usedPulseLength',style='usedStyle',glowMult='usedGlowMult')
    for e in data.get('native_track_effects',[]):
        if e['type']!='ffxRecolorFloorPlus':continue
        i=e['floor'];t=native_event_time(data,chart,e)
        a={v:(e[k]*100 if k=='glowMult' else e[k]) for k,v in native_names.items() if k in e and e.get(used[k],True)}
        raw.append((max(0,round(t*FPS)),native_duration(data,chart,e),e.get('ease','Linear'),min(e['start'],e['end']),max(e['start'],e['end']),e.get('gapLength',0),a))
    # Keep source settings, including stripe origin, when an event omits fields.
    current=original
    for frame,duration,ease,begin,end,gap,a in sorted(raw,key=lambda e:e[0]):
        for i in range(max(0,begin),min(count-1,end)+1,1+gap):
            current[i].update({k:a[k] for k in FIELDS if k in a and a[k] is not None})
            if 'trackColorType' in a:origins[i]=begin
            commands[i].append((frame,duration,ease,state(current[i],i,origins[i])))
    return [tuple([initial[i]]+commands[i]) for i in range(count)]

def evaluate(sequence,frame):
    at,duration,ease,target=sequence[0];start=color(target,0)
    def sample(frame):
        value=color(target,frame/FPS)
        if target[0]=='Single' and duration and frame<at+duration*FPS:
            phase=easing(ease,max(0,min(1,(frame-at)/(duration*FPS))))
            value=tuple(a+(b-a)*phase for a,b in zip(start,value))
        return value
    for record in sequence[1:]:
        if record[0]>frame:break
        start=sample(record[0]);at,duration,ease,target=record
    return sample(frame),target[5]

def palette_words(value,style,glow=0):
    # Opaque black interiors are essential to Neon; index zero is transparent.
    fill=(.025,.025,.035) if style=='Neon' else tuple(v*(.65 if style=='NeonLight' else .48) for v in value)
    edge=tuple(min(1,v*.8+.2) for v in value) if style!='Neon' else value
    # Approximate the original white top glow with surface brightness. Keep
    # the authored color, opacity and one-pixel boundary; no hit stamp.
    strength=min(.8,max(0,glow)*.8)
    fill=tuple(v+(1-v)*strength for v in fill)
    words=[]
    for depth in (1.,.68,.4):
        for c in (fill,edge):
            r,g,b=(max(0,min(31,round(v*depth*31))) for v in c)
            words.append(r|(g<<5)|(b<<10))
    return words

def palette_schedule(data,chart,initial,changes):
    if chart.get('authored_visibility'):
        return authored_palette_schedule(data,chart,initial,changes)
    seqs=sequences(data,chart);unique={};groups=[]
    for sequence in seqs:
        key=repr(sequence)
        if key not in unique:unique[key]=len(unique)
        groups.append(unique[key])
    seq_by_group={g:seqs[i] for i,g in enumerate(groups)}
    alpha=list(initial);slots=[0]*len(alpha);initial_slots=None;slot_changes={};palette=[0]*96
    versions=[(0,i,0) for i in range(96)];assigned={};peak=0
    outline=chart.get('readability_window',{}).get('outline_preview',False)
    detail_starts=chart.get('readability_detail_starts',[0]*len(alpha))
    preview_words=tuple(palette_words((.65,.76,.85),'Standard'))
    end=max(n['frame'] for n in chart['notes'])+120
    frames=set(range(0,end+1,4))|set(changes)
    for sequence in seqs:
        for at,duration,_,_ in sequence:frames.update((at,round(at+duration*FPS)))
    for frame in sorted(frames):
        for i,a in changes.get(frame,{}).items():alpha[i]=a
        active={groups[i] for i,a in enumerate(alpha) if a and (a>1 or not outline)}
        peak=max(peak,len(active))
        capacity=15 if outline else 16
        aliases={g:g for g in active};colors={}
        if chart.get('authored_visibility'):
            # Several independently animated materials may currently have
            # identical SNES colors. Share their palette without hiding any
            # of their tiles. If more than 16 distinct colors are on screen,
            # quantize colors only; opacity and geometry remain authored.
            buckets=collections.defaultdict(list)
            for g in active:
                words=tuple(palette_words(*evaluate(seq_by_group[g],frame)))
                colors[g]=words;buckets[words].append(g)
            for gs in buckets.values():
                representative=next((g for g in gs if g in assigned),min(gs))
                for g in gs:aliases[g]=representative
            active=set(aliases.values())
            def distance(a,b):
                return sum((((x>>s)&31)-((y>>s)&31))**2 for x,y in zip(colors[a][:2],colors[b][:2]) for s in (0,5,10))
            if len(active)>capacity:
                chosen=[min(active)]
                while len(chosen)<capacity:
                    chosen.append(max(active-set(chosen),key=lambda g:(min(distance(g,c) for c in chosen),-g)))
                aliases={g:(r if r in chosen else min(chosen,key=lambda c:distance(r,c))) for g,r in aliases.items()}
                active=set(chosen)
        assert len(active)<=capacity,('Track color capacity',chart['code'],frame,len(active))
        assigned={g:s for g,s in assigned.items() if g in active}
        free=iter(sorted(set(range(capacity))-set(assigned.values())))
        for g in sorted(active-set(assigned)):assigned[g]=next(free)
        updates={}
        for i,a in enumerate(alpha):
            slot=15 if outline and a==1 else assigned[aliases[groups[i]]] if a else slots[i]
            if a and slots[i]!=slot:slots[i]=slot;updates[i]=slots[i]
        if initial_slots is None:initial_slots=list(slots)
        elif updates:slot_changes[frame]=updates
        writes=[(palette_words(*evaluate(seq_by_group[g],frame)),s) for g,s in assigned.items()]
        for words,s in writes+([(preview_words,15)] if outline else []):
            for j,value in enumerate(words):
                index=s*6+j
                if palette[index]!=value:palette[index]=value;versions.append((frame,index,value))
    # Collapse the initial clear and initial material values to a single write.
    packed={ (f,i):v for f,i,v in versions }
    chart.update(track_palette_versions=[(f,i,v) for (f,i),v in sorted(packed.items())],
                 track_color_groups=len(unique),track_color_peak=peak,track_color_slots=16,track_color_cadence=4)
    return initial_slots,slot_changes

def authored_palette_schedule(data,chart,initial,changes):
    """Use the 96 BG entries for 48 authored fill/edge materials.

    Opacity selects its own material; no entries are reserved for invented
    preview-depth shades. The underlying color animations remain live.
    """
    capacity=chart.get('authored_material_capacity',48)
    seqs=sequences(data,chart);unique={};groups=[]
    for sequence in seqs:
        key=repr(sequence)
        if key not in unique:unique[key]=len(unique)
        groups.append(unique[key])
    seq_by_group={g:seqs[i] for i,g in enumerate(groups)}
    alpha=list(initial);slots=[0]*len(alpha);initial_slots=None;slot_changes={}
    palette=[0]*96;versions=[(0,i,0) for i in range(96)];assigned={};peak=0
    end=max(n['frame'] for n in chart['notes'])+120
    landings=[n['frame'] for n in chart['notes']]
    frames=set(range(0,end+1,4))|set(changes)|set(landings)
    for sequence in seqs:
        for at,duration,_,_ in sequence:frames.update((at,round(at+duration*FPS)))
    # Compare complete animation trajectories instead of instantaneous colors.
    # Otherwise crossing Glow colors can swap aliases every palette tick,
    # rerasterizing whole visible sections despite unchanged geometry.
    signatures={};distances={}
    signature_frames={0}
    if chart.get('stable_color_quantization'):
        for sequence in seqs:
            for at,duration,_,target in sequence:
                signature_frames.update(round(at+target[3]*FPS*k/8) for k in range(9))
                signature_frames.update(round(at+duration*FPS*k/4) for k in range(5))
        signature_frames=sorted(signature_frames)
        if len(signature_frames)>256:
            signature_frames=[signature_frames[round(i*(len(signature_frames)-1)/255)] for i in range(256)]
    def glow(sequence,frame):
        at,duration,ease,target=sequence[0];start=target[6]
        def value(t):
            phase=easing(ease,max(0,min(1,(t-at)/(duration*FPS)))) if duration else 1
            return start+(target[6]-start)*phase
        for record in sequence[1:]:
            if record[0]>frame:break
            start=value(record[0]);at,duration,ease,target=record
        return value(frame)
    def signature(g):
        if g not in signatures:
            sequence=seq_by_group[g[0]]
            signatures[g]=tuple(v for f in signature_frames for v in palette_words(*evaluate(sequence,f),glow(sequence,f) if g[2] else 0)[(3-g[1])*2:(3-g[1])*2+2])
        return signatures[g]
    for frame in sorted(frames):
        for i,a in changes.get(frame,{}).items():alpha[i]=a
        keys=[(groups[i],a,frame>=landings[i]) for i,a in enumerate(alpha)]
        active={keys[i] for i,a in enumerate(alpha) if a}
        aliases={g:g for g in active}
        colors={g:tuple(palette_words(*evaluate(seq_by_group[g[0]],frame),glow(seq_by_group[g[0]],frame) if g[2] else 0)[(3-g[1])*2:(3-g[1])*2+2]) for g in active}
        peak=max(peak,len(active))
        if len(active)>capacity:
            def distance(a,b):
                if chart.get('stable_color_quantization'):
                    pair=tuple(sorted((a,b)))
                    if pair not in distances:
                        distances[pair]=sum((((x>>s)&31)-((y>>s)&31))**2 for x,y in zip(signature(a),signature(b)) for s in (0,5,10))
                    return distances[pair]
                return sum((((x>>s)&31)-((y>>s)&31))**2 for x,y in zip(colors[a],colors[b]) for s in (0,5,10))
            chosen=sorted(active & set(assigned))[:capacity]
            if not chosen:chosen=[min(active)]
            while len(chosen)<capacity:
                chosen.append(max(active-set(chosen),key=lambda g:(min(distance(g,c) for c in chosen),g)))
            aliases={g:(g if g in chosen else min(chosen,key=lambda c:distance(g,c))) for g in active}
            active=set(chosen)
        previous=assigned
        assigned={g:s for g,s in previous.items() if g in active}
        for g in sorted(active-set(assigned)):
            # Lighting/fading an otherwise exclusive material changes CGRAM
            # in place, rather than rerasterizing every pixel of that floor.
            old=next((k for k in previous if k[0]==g[0] and k not in active and previous[k] not in assigned.values()),None)
            if old is not None:assigned[g]=previous[old]
        free=iter(sorted(set(range(capacity))-set(assigned.values())))
        for g in sorted(active-set(assigned)):assigned[g]=next(free)
        updates={}
        for i,a in enumerate(alpha):
            if not a:continue
            slot=assigned[aliases[keys[i]]]
            if slots[i]!=slot:slots[i]=slot;updates[i]=slot
        if initial_slots is None:initial_slots=list(slots)
        elif updates:slot_changes[frame]=updates
        for g,s in assigned.items():
            for j,value in enumerate(colors[g]):
                index=s*2+j
                if palette[index]!=value:palette[index]=value;versions.append((frame,index,value))
    packed={(f,i):v for f,i,v in versions}
    chart.update(track_palette_versions=[(f,i,v) for (f,i),v in sorted(packed.items())],track_color_groups=len(unique),
                 track_color_peak=peak,track_color_slots=capacity,track_color_stride=2,track_color_cadence=4)
    return initial_slots,slot_changes
