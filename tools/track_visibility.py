"""Compile original opacity/AnimateTrack effects into sparse BG-cell timelines.

Timing follows ffxFloorAppearPlus, ffxFloorDisappearPlus, and
ffxMoveFloorPlus from the installed game. Three SNES palette intensities
replace the original floating-point fade; geometry stays cartridge-native.
"""
import collections,math,struct
import numpy as np
from PIL import Image,ImageDraw,ImageFilter,ImageChops
import make_assets as common
from track_motion import enabled,easing,ease_name,native_event_time,native_duration
from track_geometry import piece,STYLE,recessed_join
from track_events import gameplay_actions

APPEAR=['None','Assemble','Assemble_Far','Extend','Grow','Grow_Spin','Fade','Drop','Rise']
DISAPPEAR=['None','Scatter','Scatter_Far','Retract','Shrink','Shrink_Spin','Fade']

def visibility_schedule(data,chart):
    chart['opacity_curve_version']=1
    notes=chart['notes'];count=len(notes);commands=[[] for _ in notes]
    scale_events=collections.defaultdict(dict)
    initial_float=[max(0,min(1,a)) for a in data.get('native_track_initial',[1]*count)]
    initial=[round(a*3) for a in initial_float]
    beat=lambda i:60/data['bpm']/notes[i]['speed']
    def move(i,t,duration,target,ease='Linear'):
        commands[i].append((t,max(0,duration),max(0,min(1,target)),ease_name(ease)))
    def animate(i,appear,disappear,ahead,behind):
        b=beat(i);duration=min(b*.5,.5)
        if appear!='None':
            initial[i]=0
            initial_float[i]=0
            move(i,max(0,notes[i]['time']-ahead*b*(2 if appear in ('Drop','Rise') else 1)),ahead*b if appear in ('Drop','Rise') else duration,1)
        if disappear!='None' and i+1<count:move(i,notes[i+1]['time']+behind*b,duration,0)
    for e in data.get('native_track_effects',[]):
        i=e['floor'];kind=e['type']
        if kind=='ffxChangeTrack':animate(i,APPEAR[e['animationType']],DISAPPEAR[e['animationType2']],e['tilesAhead'],e['tilesBehind'])
        elif kind=='ffxFloorAppearPlus':animate(i,APPEAR[e['animType']],'None',e['tilesAhead'],0)
        elif kind=='ffxFloorDisappearPlus':animate(i,'None',DISAPPEAR[e['animType']],0,e['tilesBehind'])
        elif kind=='ffxMoveFloorPlus' and e.get('opacityUsed',True):
            t=native_event_time(data,chart,e)
            for j in range(min(e['start'],e['end']),max(e['start'],e['end'])+1,1+e.get('gapLength',0)):
                if 0<=j<count:move(j,t,native_duration(data,chart,e),e['targetOpacity'],e.get('ease','Linear'))
    for e in chart.get('neo_opacity_events',[]):
        move(e['floor'],e['time'],e['duration'],e['opacity'])
    settings=data.get('track_settings',{});actions=gameplay_actions(data)
    if settings:
        events=collections.defaultdict(list)
        for a in actions:events[a['floor']].append(a)
        appear=settings.get('trackAnimation','None');disappear=settings.get('trackDisappearAnimation','None')
        ahead=settings.get('beatsAhead',3);behind=settings.get('beatsBehind',4);reference_speed=old_reference=1.;appear_enabled=True;opacity=1.
        for i,n in enumerate(notes):
            floor_opacity=opacity
            for a in events[i]:
                if a['eventType']=='AnimateTrack':
                    appear_enabled='trackAnimation' in a
                    if appear_enabled:appear=a['trackAnimation'];ahead=a.get('beatsAhead',3)
                    if 'trackDisappearAnimation' in a:disappear=a['trackDisappearAnimation'];behind=a.get('beatsBehind',4)
                    old_reference,reference_speed=reference_speed,n['speed']
                elif a['eventType']=='PositionTrack' and a.get('opacity') is not None:
                    floor_opacity=a['opacity']/100
                    if not enabled(a.get('justThisTile',False)):opacity=floor_opacity
            initial[i]=max(0,min(3,round(floor_opacity*3)))
            initial_float[i]=max(0,min(1,floor_opacity))
            scale=n['speed']/(reference_speed if appear_enabled else old_reference)
            animate(i,appear,disappear,ahead*scale,behind*scale)
        repeats={}
        for a in actions:
            if a['eventType']=='RepeatEvents':
                for tag in a.get('tag','').split():repeats[a['floor'],tag]=a
        def tile(value,floor):
            offset,relative=value
            return max(0,min(count-1,offset+(floor if relative=='ThisTile' else count-1 if relative=='End' else 0)))
        for a in actions:
            if a['eventType']!='MoveTrack' or (a.get('opacity') is None and a.get('scale') is None):continue
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
                    duration=a.get('duration',0)*beat(origin)
                    if a.get('opacity') is not None:move(j,t,duration,a['opacity']/100,a.get('ease','Linear'))
                    if a.get('scale') is not None:
                        size=a['scale'] if isinstance(a['scale'],list) else [a['scale']]*2
                        visible=all(v!=0 for v in size if v is not None)
                        scale_events[max(0,math.ceil((t+(duration if not visible else 0))*common.FPS))][j]=visible
    changes=collections.defaultdict(dict)
    for region in chart.get('freeroam_regions',[]):
        i=region['step']
        # The root is an invisible trigger floor. Generated grid cells have
        # their own opacity; inheriting the root's zero alpha hides the grid.
        initial[i]=3
        initial_float[i]=1.
        commands[i]=[]
        # The original fades all unoccupied cells over one base beat when
        # the return begins. The selected cell is rendered by the runtime.
        move(i,region['return_start']/common.FPS,region['fade_duration']/common.FPS,0)
    if chart.get('singsing_route_window'):
        start,end=chart['singsing_route_window']
        for i in chart['singsing_connectors']:
            commands[i]=[c for c in commands[i] if not start<=c[0]<=end]
        for e in chart['singsing_route_events']:
            move(e['floor'],e['time'],0,e['opacity'])
    for i,cs in enumerate(commands):
        current=initial[i];prior=initial_float[i]
        cs.sort(key=lambda c:c[0])
        for k,(t,duration,target,ease) in enumerate(cs):
            stop=cs[k+1][0] if k+1<len(cs) else math.inf
            # ffxMoveFloorPlus kills an interrupted opacity tween with
            # complete:true. Keep its floating-point target as the next
            # tween's origin, and quantize only the displayed samples.
            start=prior;prior=target
            first=max(0,math.ceil(t*common.FPS));last=math.ceil((t+duration)*common.FPS)
            if math.isfinite(stop):last=min(last,math.ceil(stop*common.FPS)-1)
            if last<0:
                current=round(target*3);initial[i]=current
                continue
            for frame in range(first,max(first,last)+1):
                if frame/common.FPS>=stop:break
                phase=1 if duration==0 else min(1,max(0,(frame/common.FPS-t)/duration))
                value=max(0,min(3,round((start+(target-start)*easing(ease,phase))*3)))
                if value!=current:changes[frame][i]=value;current=value
    # A zero-sized original tile remains hidden even when a later opacity
    # event restores alpha. Native charts use this to remove decorative
    # 360-degree pieces (XO-X floors 212/213 are one example).
    for e in data.get('native_track_effects',[]):
        if e['type']!='ffxMoveFloorPlus' or not e.get('scaleUsed',True):continue
        scalar=e.get('targetScale',float('nan'))
        scale=[scalar,scalar] if math.isfinite(scalar) else [e.get('targetScaleV2',{}).get(k,1) for k in ('x','y')]
        visible=all(v!=0 for v in scale if v is not None and math.isfinite(v))
        when=native_event_time(data,chart,e)+(native_duration(data,chart,e) if not visible else 0)
        for j in range(min(e['start'],e['end']),max(e['start'],e['end'])+1,1+e.get('gapLength',0)):
            if 0<=j<count:scale_events[max(0,math.ceil(when*common.FPS))][j]=visible
    alpha=list(initial);shown=list(initial);scale=[True]*count;combined=collections.defaultdict(dict)
    free_roots={r['step'] for r in chart.get('freeroam_regions',[])}
    for updates in scale_events.values():
        for i in free_roots:updates.pop(i,None)
    for frame in sorted(set(changes)|set(scale_events)):
        affected=set(changes.get(frame,{}))|set(scale_events.get(frame,{}))
        for i,v in changes.get(frame,{}).items():alpha[i]=v
        for i,v in scale_events.get(frame,{}).items():scale[i]=v
        for i in affected:
            value=alpha[i] if scale[i] else 0
            if value!=shown[i]:combined[frame][i]=value;shown[i]=value
    hidden={i for i,n in enumerate(notes) if n.get('scene_hidden') or n.get('platform_hidden')}
    for i in hidden:initial[i]=0
    for updates in combined.values():
        for i in hidden:updates.pop(i,None)
    if chart.get('singsing_connectors'):
        # Shared cubicle turns have hidden rhythm-floor meshes underneath
        # their visible midspins. Their connector must share the marker's
        # visibility before palette allocation and viewport compilation.
        raw=list(initial);shown=list(initial)
        connectors={j-1:j for j in chart['singsing_connectors']}
        for i,j in connectors.items():initial[i]=shown[i]=max(raw[i],raw[j])
        result=collections.defaultdict(dict)
        for frame,updates in sorted(combined.items()):
            for i,v in updates.items():raw[i]=v
            affected=set(updates)|{i for i,j in connectors.items() if i in updates or j in updates}
            for i in affected:
                value=max(raw[i],raw[connectors[i]]) if i in connectors else raw[i]
                if value!=shown[i]:result[frame][i]=value;shown[i]=value
        combined=result
    return initial,dict(sorted(combined.items()))

def animated_track(chart,initial,changes,grid=1,motion=None,color_data=None,authored=None):
    motion=motion or {}
    # Include translated destinations in the map, and retain room for camera
    # margins. The chart and its landing targets share this shifted origin.
    if motion and not chart.get('motion_bounds'):
        positions=[(n['x'],n['y']) for n in chart['notes']]
        for updates in motion.values():
            for i,(dx,dy) in updates.items():positions.append((chart['notes'][i]['x']+dx,chart['notes'][i]['y']+dy))
        bx=max(0,128-min(x for x,y in positions));by=max(0,144-min(y for x,y in positions))
        for n in chart['notes']:n['x']+=bx;n['y']+=by
        chart['motion_bounds']=[max(x for x,y in positions)+bx,max(y for x,y in positions)+by]
    # PPU patterns may be simplified; landing centers must stay on the same
    # integer coordinates as the planets and their 24-pixel orbit.
    if chart.get('mode7'):grid=1
    compact_preview=False
    chart['readability_compact_preview']=bool(compact_preview)
    notes=[dict(n,x=round(n['x']/grid)*grid,y=round(n['y']/grid)*grid) for n in chart['notes']]
    for region in chart.get('freeroam_regions',[]):
        notes[region['step']]['freeroam_grid']=dict(region)
    bound=chart.get('motion_bounds',[max(n['x'] for n in notes),max(n['y'] for n in notes)])
    width=1<<math.ceil(math.log2((bound[0]+200)/8));height=math.ceil((bound[1]+160)/8)
    pieces=[];preview_pieces=[];cells=collections.defaultdict(set);seams=[];preview_seams=[]
    preview_notes=notes
    for i,n in enumerate(notes):
        p=np.array((n['x'],n['y']),dtype=float);prev=np.array((notes[max(0,i-1)]['x'],notes[max(0,i-1)]['y']),dtype=float);nxt=np.array((notes[min(len(notes)-1,i+1)]['x'],notes[min(len(notes)-1,i+1)]['y']),dtype=float)
        right=(p+nxt)/2 if i+1<len(notes) else p+(p-prev)/np.linalg.norm(p-prev)*12
        pieces.append(piece(notes,i));preview_pieces.append(piece(preview_notes,i,line_width=1 if compact_preview else None))
        for x0,y0,image in (pieces[-1],preview_pieces[-1]):
            for y in range(max(0,y0//8),min(height,(y0+image.height+7)//8)):
                for x in range(max(0,x0//8),min(width,(x0+image.width+7)//8)):cells[x,y].add(i)
        if i+1<len(notes):
            delta=nxt-p;normal=np.array((-delta[1],delta[0]))/max(1e-9,np.linalg.norm(delta))*6
            seams.append([tuple(np.round(right+normal).astype(int)),tuple(np.round(right-normal).astype(int))])
            a=preview_notes[i];b=preview_notes[i+1]
            p0=np.array((a['x'],a['y']),float);p1=np.array((b['x'],b['y']),float)
            delta=p1-p0;normal=np.array((-delta[1],delta[0]))/max(1e-9,np.linalg.norm(delta))*(2 if compact_preview else 6)
            middle=(p0+p1)/2
            preview_seams.append([tuple(np.round(middle+normal).astype(int)),tuple(np.round(middle-normal).astype(int))])
    base_pieces=list(pieces);base_preview=list(preview_pieces);offsets_xy=[(0,0) for _ in notes]
    from track_motion import rotation_schedule
    rotations=rotation_schedule(color_data,chart) if color_data and chart.get('mode7') and chart.get('tile_rotation_enabled',chart.get('neo_cosmos') or chart.get('id') in (20,22,23,24,26,45)) else {}
    from track_motion import scale_schedule
    scales=scale_schedule(color_data,chart) if color_data and (chart.get('neo_cosmos') or chart.get('id') in (20,22,23,24,26)) else {}
    floor_scales=[(1.,1.)]*len(notes)
    angles=[0]*len(notes)
    radii=[23]*len(notes)
    for i,note in enumerate(notes):
        if note.get('hold_length',-1)>=0 or note.get('freeroam_grid') or note.get('warp_visual') or note.get('scene_visual'):
            x,y,im=base_pieces[i]
            radii[i]=max(radii[i],math.ceil(max(math.hypot(xx-note['x'],yy-note['y']) for xx in (x,x+im.width) for yy in (y,y+im.height))))
    base_radii=list(radii)
    for updates in scales.values():
        for i,value in updates.items():radii[i]=max(radii[i],math.ceil(max(abs(v) for v in value)*base_radii[i]))
    if rotations:chart['tile_rotation_version']=1
    def piece_cells(i,dx,dy):
        result=set()
        for part,ox,oy in [(base_pieces[i],dx,dy)]:
            x0,y0,im=part;x0+=ox;y0+=oy
            w,h=im.size
            # A rotated corner can extend outside its unrotated footprint.
            # Keep a conservative sweep around the floor's own pivot.
            if (rotations or radii[i]!=23) and notes[i].get('hold_length',-1)<0 and not any(k in notes[i] for k in ('scene_visual','warp_visual')):
                radius=radii[i]
                x0=notes[i]['x']+dx-radius;y0=notes[i]['y']+dy-radius
                w=h=radius*2+1
            result.update((x,y) for y in range(max(0,(y0-1)//8),min(height,(y0+h+8)//8)) for x in range(max(0,(x0-1)//8),min(width,(x0+w+8)//8)))
        return result
    if chart.get('mode7'):
        from track_motion import nearby_motion
        render_motion=nearby_motion(chart,motion,initial,changes)
    else:render_motion=motion
    # A visible hold still depends on its tail when that floor is culled.
    # Keep both endpoints on the gameplay motion timeline; floor opacity
    # continues to control whether the endpoint itself is drawn.
    hold_endpoints={j for i,n in enumerate(notes[:-1]) if n.get('hold_length',-1)>=0 for j in (i,i+1)}
    if hold_endpoints:
        render_motion={f:dict(updates) for f,updates in render_motion.items()}
        for frame,updates in motion.items():
            endpoints={i:p for i,p in updates.items() if i in hold_endpoints}
            if endpoints:render_motion.setdefault(frame,{}).update(endpoints)
    if chart.get('reuse_motion_phase'):
        from raster_phase import motion as shift_motion
        render_motion=shift_motion(chart,render_motion)
    for i in {i for updates in rotations.values() for i in updates}|{i for updates in scales.values() for i in updates}:
        for x,y in piece_cells(i,0,0):cells[x,y].add(i)
    for updates in render_motion.values():
        for i,(dx,dy) in updates.items():
            for x,y in piece_cells(i,round(dx/grid)*grid,round(dy/grid)*grid):cells[x,y].add(i)
    mode7=chart.get('mode7',False)
    if mode7 and chart.get('shared_track_contour'):chart['track_separators_version']=1
    scene=None
    if color_data and color_data.get('native_singsing_visuals') and (not chart.get('singsing_backgrounds_disabled') or chart.get('singsing_note_cues')):
        from neo_singsing import Scene
        scene=Scene(color_data,chart)
        chart['authored_material_capacity']=min(44,chart.get('authored_material_capacity',48))
        chart['singsing_scene_version']=4
    color_slots=[0]*len(notes);color_changes={}
    if mode7 and color_data:
        from track_colors import palette_schedule
        color_slots,color_changes=palette_schedule(color_data,chart,initial,changes)
        if scene:
            writes={(f,i):v for f,i,v in chart['track_palette_versions']}
            writes.update({(f,i):v for f,i,v in scene.palette()})
            chart['track_palette_versions']=[(f,i,v) for (f,i),v in sorted(writes.items())]
    alpha=list(initial);tiles=[bytes(64 if mode7 else 32)];lookup={tiles[0]:0};history={};current={}
    view_events={int(f):v for f,v in chart.get('render_viewports',{}).items()}
    if scene:
        previous=view_events[0]
        for f in sorted(set(view_events)|set(scene.frames)):
            previous=view_events.get(f,previous)
            if scene.first<=f<=scene.last:
                x,y,w,h=previous
                for yy in range(max(0,y),min(height,y+h)):
                    for xx in range(max(0,x),min(width,x+w)):cells[xx,yy]
    viewport=view_events.get(0)
    transforms={int(f):v for f,v in chart.get('render_transforms',{}).items()}
    transform=transforms.get(0)
    precise=None
    if chart.get('precise_viewport_cells'):
        from viewport_cells import sampled_cells
        camera_rows=chart['camera_follow_versions']
        sampling=chart.get('camera_world_sampling_versions',chart.get('camera_sampling_versions',chart.get('camera_rotation_versions',[])))
        def sampled(frame):
            _,x,y=next(r for r in reversed(camera_rows) if r[0]<=frame)
            c,s=next((r[1:] for r in reversed(sampling) if r[0]<=frame),(256,0))
            return sampled_cells(x,y,c,s,chart.get('viewport_center_y',96),chart.get('viewport_bottom',160),chart.get('viewport_top',32))
        precise=sampled(0)
    def in_view(x,y):
        if precise is not None:return (x,y) in precise
        if viewport is not None and not (viewport[0]<=x<viewport[0]+viewport[2] and viewport[1]<=y<viewport[1]+viewport[3]):return False
        if transform and transform[:2] not in ((256,0),[256,0]):
            c,s,cx,cy=transform;dx=x*8+4-cx;dy=y*8+4-cy
            # Conservative transformed tile bounds include every pixel the
            # fixed-point PPU can sample, but exclude invisible AABB corners.
            radius=4*(abs(c)+abs(s))+512
            if abs(c*dx-s*dy)>128*256+radius or abs(s*dx+c*dy)>(72-chart.get('viewport_inset',0))*256+radius:return False
        return True
    detail_starts=chart.get('readability_detail_starts',[0]*len(notes))
    detail_events=collections.defaultdict(list)
    for i,note in enumerate(notes):
        if note.get('taps_needed',1)>1:detail_events[note['frame']].append(i)
    if mode7:
        for i,at in enumerate(detail_starts):detail_events[at].append(i)
    def render_patch(dirty,frame):
        if not dirty:return
        x0=min(x for x,y in dirty)*8-1;y0=min(y for x,y in dirty)*8-1
        x1=(max(x for x,y in dirty)+1)*8+1;y1=(max(y for x,y in dirty)+1)*8+1
        size=(x1-x0,y1-y0);mask=Image.new('L',size);levels=Image.new('L',size);owners=Image.new('L',size);ids=set()
        for x,y in dirty:
            for dy in (-1,0,1):
                for dx in (-1,0,1):ids.update(cells.get((x+dx,y+dy),()))
        # Original MakeLevel assigns (100 + count - index) * 5: earlier
        # floors cover later floors. Composite opaque tile surfaces in
        # that order; a union of masks exposes outlines from lower layers.
        material=Image.new('L',size);separators=Image.new('L',size)
        overlap_edges=Image.new('L',size) if chart.get('shared_track_contour') else None
        def scene_layers(front):
            if scene is None:return
            for slot,above,px,py,part in scene.layers(frame):
                if above!=front:continue
                coverage=Image.new('L',size);coverage.paste(part,(px-x0,py-y0))
                layer=coverage.point(lambda v:255 if v>=64 else 0)
                bright=coverage.point(lambda v:255 if v>=192 else 0)
                mask.paste(255,mask=layer);levels.paste(3,mask=layer);owners.paste(slot,mask=layer)
                material.paste(1,mask=layer);material.paste(3,mask=bright)
        scene_layers(False)
        # The chapter reuses identical centers for a straight pass and a
        # midspin turn. Keep the active turn's actual geometry above the old
        # straight pass; no synthetic arrows or extra connectors are added.
        active_connectors={j-1:alpha[j] for j in chart.get('singsing_connectors',[]) if alpha[j]}
        active_centers={(notes[i]['x']+offsets_xy[i][0],notes[i]['y']+offsets_xy[i][1]):i
                        for i in active_connectors}
        for i in sorted(ids,key=lambda i:(i not in active_connectors,i),reverse=True):
            center=(notes[i]['x']+offsets_xy[i][0],notes[i]['y']+offsets_xy[i][1])
            if notes[i].get('spin_kind')=='normal' and center in active_centers and i!=active_centers[center]:
                continue
            visible_alpha=max(alpha[i],active_connectors.get(i,0))
            if not visible_alpha:continue
            px,py,part=preview_pieces[i] if mode7 and frame<detail_starts[i] else pieces[i]
            layer=Image.new('L',size);layer.paste(part,(px-x0,py-y0))
            gem_light=None
            if notes[i].get('gem_platform'):
                gem_light=layer.point(lambda v:255 if v==128 else 0)
                layer=layer.point(lambda v:255 if v else 0)
            if i in active_connectors and i+2<len(notes):
                # A midspin returns to the same center. Its incoming and
                # outgoing rhythm floors form one three-way junction, not
                # two competing surfaces or an isolated arrow-shaped cap.
                qx,qy,other=pieces[i+2]
                tail=Image.new('L',size);tail.paste(other,(qx-x0,qy-y0))
                layer=ImageChops.lighter(layer,tail)
            # Keep every individual contour, including the top edge where
            # two floors cross, while fully occluding lower-floor detail.
            contour=ImageChops.subtract(layer,layer.filter(ImageFilter.MinFilter(3)))
            if overlap_edges is not None:
                # A shared exterior may remove redundant outer edges, but
                # it must not weld crossing floors into one surface.
                crossing=ImageChops.multiply(contour,mask)
                overlap_edges.paste(0,mask=layer)
                overlap_edges.paste(255,mask=crossing)
            mask=ImageChops.lighter(mask,layer)
            levels.paste(visible_alpha,mask=layer)
            material.paste(1,mask=layer);material.paste(3,mask=contour)
            if gem_light is not None:
                material.paste(1,mask=layer);material.paste(3,mask=gem_light)
            if notes[i].get('scene_visual'):
                v=notes[i]['scene_visual']
                if v.get('surface'):
                    surface=Image.frombytes('L',tuple(v['size']),bytes.fromhex(v['surface']))
                    painted=Image.new('L',size);painted.paste(surface,(px-x0,py-y0))
                    material.paste(painted,mask=layer)
                for key in ('text','light'):
                    if v.get(key):
                        ink=Image.frombytes('1',tuple(v['size']),bytes.fromhex(v[key])).convert('L')
                        ink_layer=Image.new('L',size);ink_layer.paste(ink,(px-x0,py-y0))
                        material.paste(3,mask=ink_layer)
            if notes[i].get('taps_needed',1)>1 and frame<notes[i]['frame']:
                inset=STYLE.get('multitap_border_inset',3)
                inner=layer.filter(ImageFilter.MinFilter(inset*2+1))
                inner_border=ImageChops.subtract(inner,inner.filter(ImageFilter.MinFilter(3)))
                material.paste(3,mask=inner_border)
            separators.paste(0,mask=layer)
            if chart.get('authored_visibility') and i+1<len(notes) and notes[i].get('spin_kind','normal')=='normal' and notes[i].get('hold_length',-1)<0 and not any(k in notes[i] for k in ('platform_group','warp_visual','scene_visual','gem_platform')):
                # A recessed join belongs to this piece, before higher pieces
                # occlude it. Never draw seams through overlapping upper floors.
                a=notes[i].get('exit_angle')
                if a is not None:
                    a-=math.radians(angles[i])
                    center=np.array((notes[i]['x']+offsets_xy[i][0]-x0,notes[i]['y']+offsets_xy[i][1]-y0))
                    join,join_mask=recessed_join(size,layer,center,a,chart.get('shared_track_contour',False))
                    material.paste(join,mask=join_mask)
                    separators.paste(join,mask=join_mask)
            if color_data:owners.paste(color_slots[i],mask=layer)
        scene_layers(True)
        border=ImageChops.subtract(mask,mask.filter(ImageFilter.MinFilter(3)))
        if chart.get('shared_track_contour'):
            im=Image.new('P',size);im.paste(1,mask=mask);im.paste(3,mask=border)
            im.paste(3,mask=overlap_edges)
            # Sharing an exterior contour must not merge the playable steps.
            im.paste(separators,mask=separators.point(lambda p:255 if p else 0))
        else:im=Image.fromarray(np.array(material),mode='P')
        if scene:
            # Scene sprites carry authored alpha, including the faint lane
            # backboard beneath its bright beat ticks. Shared track contours
            # must not flatten both intensities into an opaque gray slab.
            scene_mask=owners.point(lambda v:255 if v>=44 else 0)
            im.paste(material,mask=scene_mask)
        d=ImageDraw.Draw(im)
        if chart.get('readability_window') and not chart.get('simplified_depth'):
            from track_readability import draw_depth
            draw_depth(im,levels)
        for i in (() if chart.get('authored_visibility') else ids):
            if i<len(seams) and alpha[i] and alpha[i+1] and offsets_xy[i]==offsets_xy[i+1] and notes[i].get('spin_kind','normal')==notes[i+1].get('spin_kind','normal')=='normal':
                far=mode7 and frame<detail_starts[i]
                if mode7 and far!=(frame<detail_starts[i+1]):continue
                line=preview_seams[i] if far else seams[i]
                dx,dy=offsets_xy[i]
                d.line([(x+dx-x0,y+dy-y0) for x,y in line],fill=2,width=1)
        pix=np.array(im);level=np.array(levels);owner=np.array(owners)
        if mode7 and chart.get('readability_window',{}).get('outline_preview'):
            # A stable wire preview exposes the route without spending colored
            # fill/depth variants on every upcoming rapid-fire floor.
            pix[(owner==15)&(pix==1)]=0
        for x,y in dirty:
            xx=x*8-x0;yy=y*8-y0;part=pix[yy:yy+8,xx:xx+8];a=int(level[yy:yy+8,xx:xx+8].max())
            if not a or not in_view(x,y):value=0
            else:
                if mode7 and color_data:
                    depth=level[yy:yy+8,xx:xx+8]
                    if chart.get('simplified_depth'):depth=np.where(depth==1,1,3)
                    if chart.get('authored_visibility'):
                        raw=bytes(np.where((part>0)&(part!=4),32+owner[yy:yy+8,xx:xx+8]*2+(part>1),0).astype(np.uint8).ravel())
                    else:
                        raw=bytes(np.where(part,32+owner[yy:yy+8,xx:xx+8]*6+(3-depth)*2+(part>1),0).astype(np.uint8).ravel())
                else:raw=bytes(np.where(part,part+(32 if chart.get('simplified_depth') else {1:48,2:64,3:32}[a]),0).astype(np.uint8).ravel()) if mode7 else bytes(common.tile_bytes(part))
                if raw not in lookup:
                    index=len(tiles);tiles.append(raw);lookup[raw]=index
                    if not mode7:
                        for flip,flag in [(part[:,::-1],0x4000),(part[::-1,:],0x8000),(part[::-1,::-1],0xC000)]:
                            lookup.setdefault(bytes(common.tile_bytes(flip)),index|((flag>>14)<<23))
                value=lookup[raw] if mode7 else lookup[raw]|({1:3,2:4,3:2}[a]<<20)
            if current.get((x,y),0)!=value:
                history.setdefault((x,y),[(0,0)])
                if history[x,y][-1][0]==frame:history[x,y][-1]=(frame,value)
                else:history[x,y].append((frame,value))
                current[x,y]=value
    def render(dirty,frame):
        chunks=collections.defaultdict(set)
        for x,y in dirty:chunks[x//16,y//16].add((x,y))
        for group in chunks.values():render_patch(group,frame)
    def rectangle(view):
        x,y,w,h=view
        return {(xx,yy) for yy in range(y,y+h) for xx in range(x,x+w) if (xx,yy) in cells and in_view(xx,yy)}
    grid_events=collections.defaultdict(list)
    for region in chart.get('freeroam_regions',[]):
        for frame in set(region.get('cell_deaths',[]))-{65535}:grid_events[frame].append(region['step'])
    render(set(cells) if viewport is None else rectangle(viewport),0)
    for frame in sorted(set(changes)|set(render_motion)|set(rotations)|set(color_changes)|set(detail_events)|set(view_events)|set(scales)|set(grid_events)|set(scene.frames if scene else [])):
        # While the final landing is pending, mode7_landing_time clamps the
        # scene to its frame minus one. Accepting it freezes the scene for
        # results. Never allocate patterns for unreachable post-clear views.
        if mode7 and frame>=notes[-1]['frame']:break
        updates=changes.get(frame,{})
        dirty=set()
        if frame in view_events:
            old=rectangle(viewport);viewport=view_events[frame]
            transform=transforms.get(frame,transform)
            if precise is not None:precise=sampled(frame)
            dirty.update(old ^ rectangle(viewport))
        if scene and scene.first<=frame<=scene.last:
            dirty.update(rectangle(viewport))
        for i in grid_events.get(frame,[]):
            dirty.update(piece_cells(i,*offsets_xy[i]))
            notes[i]['freeroam_grid']['render_frame']=frame
            base_pieces[i]=piece(notes,i);base_preview[i]=base_pieces[i]
            dx,dy=offsets_xy[i];px,py,part=base_pieces[i]
            pieces[i]=(px+dx,py+dy,part);preview_pieces[i]=pieces[i]
        for i in detail_events.get(frame,[]):
            if alpha[i]:dirty.update(piece_cells(i,*offsets_xy[i]))
        for i,value in color_changes.get(frame,{}).items():
            color_slots[i]=value
            if alpha[i]:dirty.update(piece_cells(i,*offsets_xy[i]))
        for i,value in scales.get(frame,{}).items():
            dirty.update(piece_cells(i,*offsets_xy[i]));floor_scales[i]=value
            base_pieces[i]=piece(notes,i,rotation=angles[i],scale=value)
            base_preview[i]=piece(preview_notes,i,rotation=angles[i],scale=value)
            dx,dy=offsets_xy[i];px,py,part=base_pieces[i];pieces[i]=(px+dx,py+dy,part)
            px,py,part=base_preview[i];preview_pieces[i]=(px+dx,py+dy,part)
            dirty.update(piece_cells(i,*offsets_xy[i]))
        for i,value in rotations.get(frame,{}).items():
            dirty.update(piece_cells(i,*offsets_xy[i]));angles[i]=value
            base_pieces[i]=piece(notes,i,rotation=value,scale=floor_scales[i])
            base_preview[i]=piece(preview_notes,i,line_width=1 if compact_preview else None,rotation=value,scale=floor_scales[i])
            dx,dy=offsets_xy[i];px,py,part=base_pieces[i];pieces[i]=(px+dx,py+dy,part)
            px,py,part=base_preview[i];preview_pieces[i]=(px+dx,py+dy,part)
        for i,(dx,dy) in render_motion.get(frame,{}).items():
            dx=round(dx/grid)*grid;dy=round(dy/grid)*grid
            if offsets_xy[i]==(dx,dy):continue
            dirty.update(piece_cells(i,*offsets_xy[i]));dirty.update(piece_cells(i,dx,dy))
            offsets_xy[i]=(dx,dy);px,py,part=base_pieces[i];pieces[i]=(px+dx,py+dy,part)
            px,py,part=base_preview[i];preview_pieces[i]=(px+dx,py+dy,part)
        # A hold's tail can move independently (e.g. T1's opening stretch).
        # Rebuild that curve from both current endpoints, rather than moving
        # an immutable mask away from its destination floor.
        moved=set(render_motion.get(frame,{}))
        hold_changed=moved|{i-1 for i in moved if i>0}|set(rotations.get(frame,{}))|set(scales.get(frame,{}))
        for i in hold_changed:
            if i+1>=len(notes) or notes[i].get('hold_length',-1)<0:continue
            dx,dy=offsets_xy[i];tx,ty=offsets_xy[i+1]
            dirty.update(piece_cells(i,dx,dy))
            tail=(notes[i+1]['x']+tx-dx,notes[i+1]['y']+ty-dy)
            base_pieces[i]=piece(notes,i,rotation=angles[i],scale=floor_scales[i],hold_tail=tail)
            base_preview[i]=base_pieces[i]
            px,py,part=base_pieces[i]
            pieces[i]=(px+dx,py+dy,part);preview_pieces[i]=pieces[i]
            changed_cells=piece_cells(i,dx,dy)
            dirty.update(changed_cells)
            for cell in changed_cells:cells[cell].add(i)
        for i,value in updates.items():
            if alpha[i]==value:continue
            alpha[i]=value;dirty.update(piece_cells(i,*offsets_xy[i]))
            if i in chart.get('singsing_connectors',[]):
                center=(notes[i-1]['x'],notes[i-1]['y'])
                for j,n in enumerate(notes):
                    if (n['x'],n['y'])==center:dirty.update(piece_cells(j,*offsets_xy[j]))
        render({p for p in dirty if in_view(*p) or current.get(p,0)} if viewport is not None else dirty,frame)
    if chart.get('adaptive_raster'):
        from track_mipmaps import mipmap_history
        tiles,history=mipmap_history(chart,tiles,history)
    print(chart['code'],f'visibility grid {grid}: {len(tiles)} CHR tiles, {len(history)} cells',flush=True)
    if chart.get('readability_window') and chart.get('allow_pattern_cache'):
        from track_patterns import cache_patterns
        if chart.get('share_palette_patterns'):
            from track_patterns import share_palette_patterns
            history=share_palette_patterns(chart,tiles,history)
        if chart.get('precise_viewport_cells'):
            from viewport_cells import share_clipped_patterns
            history=share_clipped_patterns(chart,tiles,history)
        if chart.get('projected_pattern_overflow'):
            from projected_spill import split
            history=split(chart,tiles,history)
        while True:
            try:
                tiles,history=cache_patterns(chart,tiles,history)
                break
            except AssertionError as e:
                if not(mode7 and e.args and isinstance(e.args[0],tuple) and e.args[0][0] in ('Track pattern capacity','Pattern upload budget')):raise
                if chart.get('strict_pattern_quality'):raise
                if not chart.get('simplified_depth'):
                    chart['simplified_depth']=True
                    return animated_track(chart,initial,changes,8,motion,color_data,authored)
                latency=chart.get('pattern_latency',24)
                minimum=0 if chart.get('authored_visibility') else 8 if compact_preview else 4
                if latency>minimum:
                    chart['pattern_latency']=max(minimum,latency-8)
                    continue
                pinned=chart.get('pattern_pinned_limit',24)
                if pinned:
                    chart['pattern_pinned_limit']=pinned//2 if pinned>6 else 0
                    continue
                if chart.get('authored_visibility') and not chart.get('adaptive_raster') and not chart.get('precise_viewport_cells'):
                    chart['precise_viewport_cells']=True
                    return animated_track(chart,initial,changes,8,motion,color_data,authored)
                if chart.get('authored_visibility') and chart.get('authored_material_capacity',48)>1:
                    chart['authored_material_capacity']=max(1,chart.get('authored_material_capacity',48)//2)
                    chart['pattern_pinned_limit']=0
                    return animated_track(chart,initial,changes,8,motion,color_data,authored)
                if chart.get('authored_visibility') and not chart.get('shared_track_contour'):
                    chart['shared_track_contour']=True
                    return animated_track(chart,initial,changes,8,motion,color_data,authored)
                if not chart.get('authored_visibility') and chart.get('readability_past',1) and authored:
                    chart['readability_past']=0
                    chart['pattern_pinned_limit']=24
                    from track_readability import depth_schedule
                    initial,changes=depth_schedule(chart,*authored,motion)
                    return animated_track(chart,initial,changes,8,motion,color_data,authored)
                if not chart.get('authored_visibility') and motion and not chart.get('nearby_motion_only'):
                    chart['nearby_motion_only']=True
                    chart['pattern_latency']=24
                    chart['pattern_pinned_limit']=24
                    return animated_track(chart,initial,changes,8,motion,color_data,authored)
                if not chart.get('authored_visibility') and chart.get('readability_foreground',1) and authored:
                    chart['readability_foreground']=0
                    chart['readability_detail']=0
                    chart['pattern_latency']=24
                    chart['pattern_pinned_limit']=24
                    from track_readability import depth_schedule
                    initial,changes=depth_schedule(chart,*authored,motion)
                    return animated_track(chart,initial,changes,8,motion,color_data,authored)
                raise
    else:
        if len(tiles)>1024 and grid<8:return animated_track(chart,initial,changes,grid*2,motion)
        history={cell:[(f,(v&0xfffff)|(((v>>20)&7)<<10)|(((v>>23)&3)<<14)) for f,v in rows] for cell,rows in history.items()}
    assert len(tiles)<=1024,(chart['id'],len(tiles),'animated CHR tiles')
    tilemap=[0]*(width*height);timeline=bytearray();offsets=[]
    for (x,y),versions in history.items():
        if len(versions)==1 and not chart.get('global_pattern_references'):tilemap[y*width+x]=versions[0][1]
        else:
            assert len(offsets)<32768,('Animated cell index capacity',chart['code'])
            index=len(offsets);tilemap[y*width+x]=0x2000|(index&8191)|((index&24576)<<1);offsets.append(len(timeline))
            timeline+=struct.pack('<H',len(versions))+b''.join(struct.pack('<HH',f,v) for f,v in versions)
    cell_count=len(offsets)
    if mode7:chart['cell_coordinates']=[(x&127)|((y&127)<<7) for (x,y),versions in history.items() if len(versions)>1]
    floor_initial,floor_changes=authored if chart.get('authored_visibility') and authored else (initial,changes)
    floor_versions=[[(0,a)] for a in floor_initial]
    for frame,updates in floor_changes.items():
        for i,value in updates.items():
            if floor_versions[i][-1][0]==frame:floor_versions[i][-1]=(frame,value)
            elif floor_versions[i][-1][1]!=value:floor_versions[i].append((frame,value))
    for versions in floor_versions:
        offsets.append(len(timeline))
        timeline+=struct.pack('<H',len(versions))+b''.join(struct.pack('<HH',f,v) for f,v in versions)
    if motion:
        for axis in range(2):
            for i,n in enumerate(chart['notes']):
                base=n['x' if axis==0 else 'y'];versions=[(0,base)]
                for frame,updates in motion.items():
                    if i in updates:
                        value=base+updates[i][axis]
                        if versions[-1][0]==frame:versions[-1]=(frame,value)
                        elif versions[-1][1]!=value:versions.append((frame,value))
                offsets.append(len(timeline));timeline+=struct.pack('<H',len(versions))+b''.join(struct.pack('<HH',f,v) for f,v in versions)
    if chart.get('pattern_versions'):
        chart['pattern_node_base']=len(offsets)
        for versions in chart['pattern_versions']:
            offsets.append(len(timeline));timeline+=struct.pack('<H',len(versions))+b''.join(struct.pack('<HH',f,v) for f,v in versions)
    chart.update(map_width=width,map_height=height,visual_grid=grid,track_tiles=len(tiles),visibility_cells=cell_count,visibility_frames=list(changes),visibility_offsets=offsets,visibility_floor_versions=floor_versions,moving_tiles=bool(motion))
    from campaign_assets import compress_map
    compressed=compress_map(tilemap,width,height);chart['map_rle_bytes']=len(compressed)
    return b''.join(tiles),compressed,bytes(timeline)
