"""Mawaru's authored camera copies, sampled from unclipped world geometry."""
import base64,bisect,collections,copy,math,struct,zlib
from pathlib import Path
import numpy as np
from make_assets import FPS
from neo_mawaru import clock,copy_cameras
from neo_visuals import chapter_time
from viewport_cells import sampled_pixels

ROOT=Path(__file__).resolve().parents[1]


def capture_world(folder,level):
    """Retain the off-camera floors which the additional cameras can see."""
    import json
    import track_patterns
    from track_visibility import animated_track
    folder=Path(folder);chart=json.loads((folder/f'level{level}.json').read_text())
    if chart.get('code') not in ('T3-X','T3EX-X'):return None
    chart=copy.deepcopy(chart)
    data=json.loads((ROOT/f'assets/private/level{level}.json').read_text())
    first=math.ceil(chapter_time(chart,850)*FPS);last=math.ceil(chapter_time(chart,882)*FPS)
    versions=chart['visibility_floor_versions'];initial=[rows[0][1] for rows in versions];changes={}
    for i,rows in enumerate(versions):
        for frame,value in rows[1:]:changes.setdefault(frame,{})[i]=value
    timeline=(folder/f'timeline{level}.bin').read_bytes();count=len(chart['notes'])
    motion={};nodes=chart['visibility_offsets']
    for axis,key in enumerate(('x','y')):
        for i,note in enumerate(chart['notes']):
            offset=nodes[chart['visibility_cells']+count+axis*count+i]
            length=struct.unpack_from('<H',timeline,offset)[0]
            for frame,value in struct.iter_unpack('<HH',timeline[offset+2:offset+2+length*4]):
                if value>=32768:value-=65536
                motion.setdefault(frame,{}).setdefault(i,[None,None])[axis]=value-note[key]
    position=[[0,0] for _ in range(count)]
    for frame,updates in sorted(motion.items()):
        for i,values in updates.items():
            for axis,value in enumerate(values):
                if value is not None:position[i][axis]=value
            updates[i]=tuple(position[i])
    views={int(f):v for f,v in chart['render_viewports'].items()};times=sorted(views)
    transforms={int(f):v for f,v in chart.get('render_transforms',{}).items()}
    for frame in range(first,last):
        x,y,width,height=views[times[bisect.bisect_right(times,frame)-1]]
        # Native offsets reach ten Unity units (160 world pixels). This
        # conservative union also encloses the extra rotated camera views.
        views[frame]=[x-40,y-40,width+80,height+80]
        transforms[frame]=[256,0,0,0]
    chart.update(render_viewports=views,render_transforms=transforms,precise_viewport_cells=False,
                 projected_pattern_overflow=False,share_palette_patterns=False,allow_pattern_cache=True)
    chart.pop('projected_spill_frames',None)
    captured={}
    class Complete(Exception):pass
    def collect(current,tiles,history):
        selected={}
        for xy,rows in history.items():
            before=0;kept=[]
            for frame,value in rows:
                if frame<first:before=value
                elif frame<last:kept.append((frame,value))
            rows=[(0,before)]+kept
            if any(value for frame,value in rows):selected[xy]=rows
        ids=sorted({0}|{value for rows in selected.values() for frame,value in rows})
        remap={value:i for i,value in enumerate(ids)};cells=bytearray()
        for (x,y),rows in sorted(selected.items()):
            cells+=struct.pack('<HHH',x,y,len(rows))
            cells+=b''.join(struct.pack('<HH',frame,remap[value]) for frame,value in rows)
        palette=[0]*96;updates=[]
        for frame,index,value in current['track_palette_versions']:
            if frame<first:palette[index]=value
            elif frame<last:updates.append([frame,index,value])
        def pack(raw):return base64.b64encode(zlib.compress(raw,9)).decode('ascii')
        captured.update(version=1,first=first,last=last,patterns=pack(b''.join(tiles[i] for i in ids)),
                        cells=pack(cells),cell_count=len(selected),palette=palette,palette_changes=updates)
        raise Complete
    original=track_patterns.cache_patterns;track_patterns.cache_patterns=collect
    try:animated_track(chart,initial,changes,motion=motion,color_data=data,authored=(initial,changes))
    except Complete:pass
    finally:track_patterns.cache_patterns=original
    assert captured,'Unclipped copy geometry was not captured'
    return captured


class CopyWorld:
    def __init__(self,data):
        assert data['version']==1
        self.first=data['first'];self.last=data['last'];self.events=collections.defaultdict(list)
        self.patterns=np.frombuffer(zlib.decompress(base64.b64decode(data['patterns'])),dtype=np.uint8).reshape(-1,8,8)
        cells=zlib.decompress(base64.b64decode(data['cells']));at=0;maxx=maxy=0
        for _ in range(data['cell_count']):
            x,y,count=struct.unpack_from('<HHH',cells,at);at+=6;maxx=max(maxx,x);maxy=max(maxy,y)
            for frame,value in struct.iter_unpack('<HH',cells[at:at+count*4]):self.events[frame].append((x,y,value))
            at+=count*4
        assert at==len(cells)
        self.world=np.zeros((maxy+1,maxx+1),dtype=np.uint16)
        self.palette=np.zeros(256,dtype=np.uint16);self.palette[32:128]=data['palette']
        self.colors=collections.defaultdict(list)
        for frame,index,value in data['palette_changes']:self.colors[frame].append((32+index,value))
        self.frame=-1
        self.beat=None

    def advance(self,frame):
        assert frame>=self.frame
        for t in range(self.frame+1,frame+1):
            for x,y,value in self.events.get(t,[]):self.world[y,x]=value
            for index,value in self.colors.get(t,[]):self.palette[index]=value
        self.frame=frame

    def sample(self,camera,rotation,chart):
        top=chart.get('viewport_top',32);bottom=chart.get('viewport_bottom',176)
        px,py=sampled_pixels(*camera,*rotation,chart.get('viewport_center_y',104),bottom,top)
        valid=(px>=0)&(py>=0)&(px//8<self.world.shape[1])&(py//8<self.world.shape[0])
        result=np.zeros(px.shape,dtype=np.uint8);x,y=px[valid],py[valid]
        result[valid]=self.patterns[self.world[y//8,x//8],y&7,x&7]
        image=np.zeros((184,256),dtype=np.uint8);image[top+1:bottom+1]=result
        return image

    def screen(self,frame,camera,rotation,palette,chart):
        self.advance(frame);image=np.zeros((184,256),dtype=np.uint8)
        if self.beat is None:self.beat=clock(chart)
        parts=[]
        for x,y,degrees in copy_cameras(self.beat(frame),chart['code']=='T3EX-X'):
            angle=math.radians(degrees);c,s=rotation
            view=(round(camera[0]-x*16),round(camera[1]+y*16))
            matrix=(round(c*math.cos(angle)-s*math.sin(angle)),round(c*math.sin(angle)+s*math.cos(angle)))
            part=self.sample(view,matrix,chart)
            parts.append(part)
        wanted={int(self.palette[index]) for part in parts for index in np.unique(part) if index}
        lookup={}
        for i in range(32,128):lookup.setdefault(int(palette[i]),i)
        retained={lookup[rgb] for rgb in wanted if rgb in lookup}
        available=iter(i for i in range(32,128) if i not in retained)
        for rgb in sorted(wanted-lookup.keys()):
            index=next(available);palette[index]=rgb;lookup[rgb]=index
        translate=np.arange(256,dtype=np.uint8)
        for part in parts:
            for index in np.unique(part):
                if index:translate[index]=lookup[int(self.palette[index])]
            mask=part!=0;image[mask]=translate[part[mask]]
        return image


def actor_events(chart,world):
    """The same native cameras as the track, applied to live OBJ centers."""
    from animation_bulk import HEADER
    beat=clock(chart);rotations=chart.get('camera_sampling_versions',chart.get('camera_rotation_versions',[(0,256,0)]))
    times=[row[0] for row in rotations];last=None;events=[]
    for frame in range(world['first'],world['last']):
        c,s=rotations[bisect.bisect_right(times,frame)-1][1:]
        inverse=65536/(c*c+s*s);pc,ps=c*inverse,s*inverse;rows=[]
        for x,y,degrees in copy_cameras(beat(frame),chart['code']=='T3EX-X'):
            x,y=round(x*16),round(-y*16);angle=math.radians(degrees)
            row=(round(math.cos(angle)*256),round(math.sin(angle)*256),
                 round((pc*x-ps*y)/16),round((ps*x+pc*y)/16),round(degrees*64/360)&63)
            if row not in rows:rows.append(row)
        body=b''.join(struct.pack('<5H',*(v&65535 for v in row)) for row in rows)
        if body!=last:events.append((frame,43,len(rows),len(body),body))
        last=body
    events.append((world['last'],43,0,0,b''))
    return events


def palette_events(folder,level,world):
    """Retain extra-camera and foreground colors without changing track RGB."""
    from projected_tracks import Source
    source=Source(folder,level,world);events=[];runtime=np.zeros(256,dtype=np.uint16)
    intervals=[(world['first'],world['last'])] if world else []
    if source.fog:intervals.append((source.fog.first,source.fog.last))
    if not intervals:return events
    first=min(a for a,b in intervals);last=max(b for a,b in intervals)
    for frame in range(last+1):
        for index,value in source.color_events.get(frame,[]):runtime[index]=value
        if frame<first:continue
        if any(a<=frame<b for a,b in intervals):source.screen(frame)
        else:source.advance(frame)
        for index in np.flatnonzero(runtime[32:128]!=source.palette[32:128])+32:
            events.append((frame,7,int(index)-32,int(source.palette[index]),b''))
            runtime[index]=source.palette[index]
    return events
