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
from track_geometry import piece,STYLE
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
    for frame in sorted(set(changes)|set(scale_events)):
        affected=set(changes.get(frame,{}))|set(scale_events.get(frame,{}))
        for i,v in changes.get(frame,{}).items():alpha[i]=v
        for i,v in scale_events.get(frame,{}).items():scale[i]=v
        for i in affected:
            value=alpha[i] if scale[i] else 0
            if value!=shown[i]:combined[frame][i]=value;shown[i]=value
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
    rotations=rotation_schedule(color_data,chart) if color_data and chart.get('mode7') and chart.get('tile_rotation_enabled',chart.get('id')==45) else {}
    angles=[0]*len(notes)
    if rotations:chart['tile_rotation_version']=1
    def piece_cells(i,dx,dy):
        result=set()
        for part,ox,oy in [(base_pieces[i],dx,dy)]:
            x0,y0,im=part;x0+=ox;y0+=oy
            w,h=im.size
            # A rotated corner can extend outside its unrotated footprint.
            # Keep a conservative sweep around the floor's own pivot.
            if rotations:
                x0=notes[i]['x']+dx-23;y0=notes[i]['y']+dy-23
                w=h=47
            result.update((x,y) for y in range(max(0,(y0-1)//8),min(height,(y0+h+8)//8)) for x in range(max(0,(x0-1)//8),min(width,(x0+w+8)//8)))
        return result
    if chart.get('mode7'):
        from track_motion import nearby_motion
        render_motion=nearby_motion(chart,motion,initial,changes)
    else:render_motion=motion
    if chart.get('reuse_motion_phase'):
        from raster_phase import motion as shift_motion
        render_motion=shift_motion(chart,render_motion)
    for i in {i for updates in rotations.values() for i in updates}:
        for x,y in piece_cells(i,0,0):cells[x,y].add(i)
    for updates in render_motion.values():
        for i,(dx,dy) in updates.items():
            for x,y in piece_cells(i,round(dx/grid)*grid,round(dy/grid)*grid):cells[x,y].add(i)
    mode7=chart.get('mode7',False)
    if mode7 and chart.get('shared_track_contour'):chart['track_separators_version']=1
    color_slots=[0]*len(notes);color_changes={}
    if mode7 and color_data:
        from track_colors import palette_schedule
        color_slots,color_changes=palette_schedule(color_data,chart,initial,changes)
    alpha=list(initial);tiles=[bytes(64 if mode7 else 32)];lookup={tiles[0]:0};history={};current={}
    view_events={int(f):v for f,v in chart.get('render_viewports',{}).items()}
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
        for i in sorted(ids,reverse=True):
            if not alpha[i]:continue
            px,py,part=preview_pieces[i] if mode7 and frame<detail_starts[i] else pieces[i]
            layer=Image.new('L',size);layer.paste(part,(px-x0,py-y0));mask=ImageChops.lighter(mask,layer)
            levels.paste(alpha[i],mask=layer)
            # Keep every individual contour, including the top edge where
            # two floors cross, while fully occluding lower-floor detail.
            contour=ImageChops.subtract(layer,layer.filter(ImageFilter.MinFilter(3)))
            material.paste(1,mask=layer);material.paste(3,mask=contour)
            if notes[i].get('taps_needed',1)>1 and frame<notes[i]['frame']:
                inset=STYLE.get('multitap_border_inset',3)
                inner=layer.filter(ImageFilter.MinFilter(inset*2+1))
                inner_border=ImageChops.subtract(inner,inner.filter(ImageFilter.MinFilter(3)))
                material.paste(3,mask=inner_border)
            separators.paste(0,mask=layer)
            if chart.get('authored_visibility') and i+1<len(notes) and notes[i].get('spin_kind','normal')=='normal':
                # A recessed join belongs to this piece, before higher pieces
                # occlude it. Never draw seams through overlapping upper floors.
                a=notes[i].get('exit_angle')
                if a is not None:
                    a-=math.radians(angles[i])
                    direction=np.array((math.cos(a),math.sin(a)))
                    normal=np.array((-direction[1],direction[0]))*7
                    center=np.array((notes[i]['x']+offsets_xy[i][0]-x0,notes[i]['y']+offsets_xy[i][1]-y0))
                    join=Image.new('L',size);jd=ImageDraw.Draw(join)
                    for distance,value in (((11,3),) if chart.get('shared_track_contour') else ((11,3),(12,4))):
                        end=center+np.round(direction*distance)
                        jd.line([tuple(np.round(end-normal).astype(int)),tuple(np.round(end+normal).astype(int))],fill=value,width=1)
                    join_mask=ImageChops.multiply(layer.filter(ImageFilter.MinFilter(3)) if chart.get('shared_track_contour') else layer,join.point(lambda p:255 if p else 0))
                    material.paste(join,mask=join_mask)
                    separators.paste(join,mask=join_mask)
            if color_data:owners.paste(color_slots[i],mask=layer)
        border=ImageChops.subtract(mask,mask.filter(ImageFilter.MinFilter(3)))
        if chart.get('shared_track_contour'):
            im=Image.new('P',size);im.paste(1,mask=mask);im.paste(3,mask=border)
            # Sharing an exterior contour must not merge the playable steps.
            im.paste(separators,mask=separators.point(lambda p:255 if p else 0))
        else:im=Image.fromarray(np.array(material),mode='P')
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
    render(set(cells) if viewport is None else rectangle(viewport),0)
    for frame in sorted(set(changes)|set(render_motion)|set(rotations)|set(color_changes)|set(detail_events)|set(view_events)):
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
        for i in detail_events.get(frame,[]):
            if alpha[i]:dirty.update(piece_cells(i,*offsets_xy[i]))
        for i,value in color_changes.get(frame,{}).items():
            color_slots[i]=value
            if alpha[i]:dirty.update(piece_cells(i,*offsets_xy[i]))
        for i,value in rotations.get(frame,{}).items():
            dirty.update(piece_cells(i,*offsets_xy[i]));angles[i]=value
            base_pieces[i]=piece(notes,i,rotation=value)
            base_preview[i]=piece(preview_notes,i,line_width=1 if compact_preview else None,rotation=value)
            dx,dy=offsets_xy[i];px,py,part=base_pieces[i];pieces[i]=(px+dx,py+dy,part)
            px,py,part=base_preview[i];preview_pieces[i]=(px+dx,py+dy,part)
        for i,(dx,dy) in render_motion.get(frame,{}).items():
            dx=round(dx/grid)*grid;dy=round(dy/grid)*grid
            if offsets_xy[i]==(dx,dy):continue
            dirty.update(piece_cells(i,*offsets_xy[i]));dirty.update(piece_cells(i,dx,dy))
            offsets_xy[i]=(dx,dy);px,py,part=base_pieces[i];pieces[i]=(px+dx,py+dy,part)
            px,py,part=base_preview[i];preview_pieces[i]=(px+dx,py+dy,part)
        for i,value in updates.items():
            if alpha[i]==value:continue
            alpha[i]=value;dirty.update(piece_cells(i,*offsets_xy[i]))
        render({p for p in dirty if in_view(*p) or current.get(p,0)} if viewport is not None else dirty,frame)
    if chart.get('adaptive_raster'):
        from track_mipmaps import mipmap_history
        tiles,history=mipmap_history(chart,tiles,history)
    print(chart['code'],f'visibility grid {grid}: {len(tiles)} CHR tiles, {len(history)} cells',flush=True)
    if chart.get('readability_window') and chart.get('allow_pattern_cache'):
        from track_patterns import cache_patterns
        if chart.get('precise_viewport_cells'):
            from viewport_cells import share_clipped_patterns
            history=share_clipped_patterns(chart,tiles,history)
        while True:
            try:
                tiles,history=cache_patterns(chart,tiles,history)
                break
            except AssertionError as e:
                if not(mode7 and e.args and isinstance(e.args[0],tuple) and e.args[0][0] in ('Track pattern capacity','Pattern upload budget')):raise
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
