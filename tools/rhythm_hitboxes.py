"""Sample authored rhythm hazards using the artwork's existing transforms."""
import bisect
import math
from decoration_tracks import DecorationTracks


def configure(data,chart):
    killers=[d for d in data.get('featured_decorations',[]) if d.get('hitbox')=='Kill'
             and d.get('relativeTo','Tile') in ('Tile','Global')]
    if not killers or chart.get('freeroam_regions'):return
    source=DecorationTracks(dict(data,featured_decorations=killers),chart)
    phases=chart.get('raster_origin_versions',[[0,0,0]]);phase_times=[r[0] for r in phases]
    objects=[]
    for obj in source.objects:
        dec=obj['source'];frames=[]
        if dec.get('failHitboxType','Box')!='Box':
            raise ValueError(('Unsupported rhythm collider',dec.get('tag')))
        for frame in range(chart['last_frame']+121):
            x,y,rotation,sx,sy,*_= [t.at(frame) for t in obj['tracks']]
            name=obj['images'][bisect.bisect_right(obj['image_times'],frame)-1][1]
            image=source.images[name];scale=dec.get('failHitboxScale',(100,100))
            _,dx,dy=phases[bisect.bisect_right(phase_times,frame)-1]
            parent_angle=-math.radians(rotation)
            angle=parent_angle-math.radians(dec.get('failHitboxRotation',0))
            co,si=math.cos(angle),math.sin(angle)
            ox,oy=dec.get('failHitboxOffset',(0,0));ox*=16*sx/100;oy*=-16*sy/100
            cx=source.world_origin[0]+16*x-dx+math.cos(parent_angle)*ox-math.sin(parent_angle)*oy
            cy=source.world_origin[1]-16*y-dy+math.sin(parent_angle)*ox+math.cos(parent_angle)*oy
            width=round(abs(image.shape[1]*.0008*sx*scale[0]/100))
            height=round(abs(image.shape[0]*.0008*sy*scale[1]/100))
            if obj['tracks'][12].at(frame)<.5:width=height=0
            frames.append([round(cx),round(cy),
                           round(co*256),round(si*256),width,height])
        objects.append(dict(tag=dec.get('tag',''),start=0,end=len(frames),frames=frames))
    chart['rhythm_hitboxes']=objects
