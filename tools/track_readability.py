"""Depth cues and a bounded preview for dense tech routes.

Intersect with authored visibility: these cues never reveal a hidden tile.
"""
import collections
from PIL import ImageChops,ImageFilter
from make_assets import FPS

def depth_schedule(chart,initial,changes,motion=None,camera_data=None):
    # Rasterize only the local camera neighborhood, without inventing a
    # musical reveal/hide window. Original opacity is stored independently
    # for gameplay icons, checkpoints and original-visibility verification.
    notes=chart['notes'];count=len(notes);motion=motion or {}
    if motion and not chart.get('motion_bounds'):
        positions=[(n['x'],n['y']) for n in notes]
        for updates in motion.values():
            for i,(dx,dy) in updates.items():positions.append((notes[i]['x']+dx,notes[i]['y']+dy))
        bx=max(0,128-min(x for x,y in positions));by=max(0,144-min(y for x,y in positions))
        for n in notes:n['x']+=bx;n['y']+=by
        chart['motion_bounds']=[max(x for x,y in positions)+bx,max(y for x,y in positions)+by]
    from track_camera import follow_schedule
    camera=follow_schedule(chart,motion,camera_data)
    raster_camera=camera
    if chart.get('reuse_motion_phase'):
        from raster_phase import schedule,camera as shift_camera
        chart['raster_origin_versions']=schedule(motion)
        raster_camera=shift_camera(camera,chart['raster_origin_versions'])
        chart['camera_follow_versions']=raster_camera
    rotations={f:(c,s) for f,c,s in chart.get('camera_world_sampling_versions',chart.get('camera_sampling_versions',chart.get('camera_rotation_versions',[])))}
    extents={};views={};transforms={};c,s=256,0;x,y=raster_camera[0][1:];positions={f:(x,y) for f,x,y in raster_camera}
    for frame in sorted(set(positions)|set(rotations)):
        if frame in positions:x,y=positions[frame]
        if frame in rotations:c,s=rotations[frame]
        half=72-chart.get('viewport_inset',0)
        ex=(128*abs(c)+half*abs(s)+255)//256;ey=(half*abs(c)+128*abs(s)+255)//256
        extents[frame]=(ex+20,ey+20)
        norm=c*c+s*s
        transforms[frame]=(round(c*65536/norm),round(s*65536/norm),x+128,y+104)
        views[frame]=((x+128-ex)//8,(y+104-ey)//8,(2*ex+14)//8,(2*ey+14)//8)

    chart['viewport_center_y']=104
    chart['viewport_top']=32+chart.get('viewport_inset',0)
    chart['viewport_bottom']=176-chart.get('viewport_inset',0)
    chart['render_viewports']=views
    if rotations:chart['render_transforms']=transforms
    chart['authored_visibility']=True
    chart['global_pattern_references']=True
    chart['pattern_latency']=0
    chart['simplified_depth']=True
    chart['readability_detail_starts']=[0]*count
    chart['readability_window']=dict(authored=True,spatial_culling=True,
                                    preview=None,seconds=None,foreground=None,
                                    past=None,outline_preview=False,
                                    preview_bounds=[148,84])
    authored=list(initial);offsets=[(0,0)]*count;center=0
    centers={f:(x+128,y+104) for f,x,y in camera}
    center=centers[0];bounds=extents[0]
    for i,v in motion.get(0,{}).items():offsets[i]=v
    def value(i):
        n=notes[i]
        dx=n['x']+offsets[i][0]-center[0]
        dy=n['y']+offsets[i][1]-center[1]
        return authored[i] if abs(dx)<=bounds[0] and abs(dy)<=bounds[1] else 0
    result=[value(i) for i in range(count)];start=list(result);out={}
    for frame in sorted(set(changes)|set(centers)|set(motion)|set(extents)):
        for i,v in changes.get(frame,{}).items():authored[i]=v
        for i,v in motion.get(frame,{}).items():offsets[i]=v
        if frame in centers:center=centers[frame]
        if frame in extents:bounds=extents[frame]
        updates={}
        for i in range(count):
            v=value(i)
            if v!=result[i]:updates[i]=v;result[i]=v
        if updates:out[frame]=updates
    return start,out

def legacy_depth_schedule(chart,initial,changes,motion=None):
    notes=chart['notes'];count=len(notes);events=collections.defaultdict(dict)
    preview=chart.get('readability_preview',16) if chart.get('mode7') else 48
    front=chart.get('readability_foreground',1 if chart.get('id',0)>=40 else 2)
    medium=chart.get('readability_detail',front) if chart.get('mode7') else 24
    if not chart.get('mode7'):front=8
    seconds=chart.get('readability_seconds',2.) if chart.get('mode7') else 0
    chart['readability_detail_starts']=[notes[max(0,i-front)]['frame'] for i in range(count)]
    for i in range(count):
        past=chart.get('readability_past',1)
        behind=[(-1,2),(-min(3,past),1),(-(past+1),0)] if past else [(-1,0)]
        # Count-based windows collapse during rolls, midspins and chords.
        # Keep at least two song seconds of warning as well as the route span.
        reveal=min(notes[max(0,i-preview)]['frame'],max(0,notes[i]['frame']-round(seconds*FPS)))
        events[reveal][i]=1
        for offset,value in [(medium,2),(front,3),*behind]:
            at=i-offset
            if at>=count:continue
            frame=notes[max(0,at)]['frame']
            if offset<0:frame=max(frame,notes[i]['frame']+1)
            events[frame][i]=value
    motion=motion or {};centers={n['frame']:i for i,n in enumerate(notes)}
    spatial=bool(chart.get('mode7'));offsets=[(0,0)]*count;center=0
    authored=list(initial);depth=[0]*count
    for i,v in events.pop(0,{}).items():depth[i]=v
    def value(i):
        a=min(authored[i],depth[i])
        if spatial and a==1:
            dx=notes[i]['x']+offsets[i][0]-notes[center]['x']-offsets[center][0]
            dy=notes[i]['y']+offsets[i][1]-notes[center]['y']-offsets[center][1]
            bx,by=chart.get('readability_bounds',[176,112])
            if abs(dx)>bx or abs(dy)>by:return 0
        return a
    if 0 in centers:center=centers[0]
    for i,v in motion.get(0,{}).items():offsets[i]=v
    result=[value(i) for i in range(count)];start=list(result);out={}
    for frame in sorted(set(events)|set(changes)|set(centers)|set(motion)):
        authored_updates=changes.get(frame,{});depth_updates=events.get(frame,{})
        for i,v in authored_updates.items():authored[i]=v
        for i,v in depth_updates.items():depth[i]=v
        spatial_changed=frame in centers or frame in motion
        if frame in centers:center=centers[frame]
        for i,v in motion.get(frame,{}).items():offsets[i]=v
        updates={}
        candidates=range(count) if spatial and spatial_changed else set(authored_updates)|set(depth_updates)
        for i in candidates:
            v=value(i)
            if v!=result[i]:updates[i]=v;result[i]=v
        if updates:out[frame]=updates
    chart['readability_window']=dict(preview=preview,seconds=seconds,medium=medium,foreground=front,past=past,outline_preview=spatial,preview_bounds=chart.get('readability_bounds',[176,112]))
    return start,out

def draw_depth(image,levels):
    for threshold in (2,3):
        front=levels.point(lambda v:255 if v>=threshold else 0)
        shadow=ImageChops.subtract(ImageChops.offset(front,1,2),front)
        image.paste(0,mask=shadow)
        contour=ImageChops.subtract(front,front.filter(ImageFilter.MinFilter(3)))
        image.paste(3,mask=contour)
