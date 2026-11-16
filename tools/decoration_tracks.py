"""Sample authored PNG track decorations before screen-pose encoding.

This is an offline renderer, not a replacement floor layout. Planet-relative
images are reported separately because their transforms must follow live input.
"""
import bisect
import collections
import math
import re
from pathlib import Path

import numpy as np
from PIL import Image

from make_assets import FPS
from track_motion import enabled, easing


def text_image(text):
    """Keep instructional text readable with the project's editable CHR font."""
    font=(Path(__file__).resolve().parents[1]/'assets/graphics/campaign/font.chr').read_bytes()
    mathfont=(Path(__file__).resolve().parents[1]/'assets/graphics/campaign/math-font.chr').read_bytes()
    # Color is part of instructions such as "blue tiles are twirls".
    # Parse the supported TMP color spans without drawing markup as glyphs.
    lines=[[]];colors=[(255,255,255,255)]
    for token in re.split(r'(<[^>]*>)',text):
        if token.lower().startswith('<color='):
            value=token[7:-1].lstrip('#')
            if len(value) not in (6,8):raise ValueError(('Unsupported text color',token))
            colors.append(tuple(int(value[i:i+2],16) for i in (0,2,4))+(int(value[6:8] or 'ff',16),))
        elif token.lower()=='</color>':
            if len(colors)>1:colors.pop()
        elif token.startswith('<'):
            raise ValueError(('Unsupported instructional text markup',token))
        else:
            for char in token.upper():
                if char=='\n':lines.append([])
                elif char!='\r':lines[-1].append((char,colors[-1]))
    canvas=np.zeros((8*len(lines),max(1,max(map(len,lines)))*8,4),dtype=np.uint8)
    for row,line in enumerate(lines):
        for column,(char,color) in enumerate(line):
            if char=='■':
                pixels=np.zeros((8,8),dtype=bool);pixels[1:7,1:7]=True
            elif char=='↑':
                pixels=np.array([[int(v) for v in s] for s in
                    ['00010000','00111000','01111100','00010000','00010000','00010000','00010000','00000000']],dtype=bool)
            elif ord(char)<128 or char in '√×Π':
                glyph='√×Π'.index(char) if char in '√×Π' else ord(char)
                sheet=mathfont if char in '√×Π' else font
                raw=sheet[glyph*16:glyph*16+16]
                pixels=np.array([[bool((raw[y*2]|raw[y*2+1])&(128>>x)) for x in range(8)] for y in range(8)])
            else:
                raise ValueError(('Unsupported instructional text character',char))
            tile=canvas[row*8:row*8+8,column*8:column*8+8]
            tile[pixels]=color
    return np.asarray(Image.fromarray(canvas).resize((canvas.shape[1]*8,canvas.shape[0]*8),Image.Resampling.NEAREST))


def portal_image():
    """Use the project's editable portal CHR for native portal decorations."""
    root=Path(__file__).resolve().parents[1]/'assets/graphics/campaign'
    sheet=(root/'objects.chr').read_bytes()
    colors=np.frombuffer((root/'palette.bin').read_bytes(),dtype='<u2')
    canvas=np.zeros((16,16,4),dtype=np.uint8)
    for y in range(16):
        for x in range(16):
            tile=12+x//8+(y//8)*16;offset=tile*32
            value=sum(((sheet[offset+(b//2)*16+(y%8)*2+b%2]>>(7-x%8))&1)<<b for b in range(4))
            if value:
                c=int(colors[128+value])
                canvas[y,x]=[(c&31)*8,((c>>5)&31)*8,((c>>10)&31)*8,255]
    return np.asarray(Image.fromarray(canvas).resize((100,100),Image.Resampling.NEAREST))


def floor_image(dec):
    """Draw native AddObject floors with the same geometry as playable tiles."""
    from track_geometry import surface
    angle=float(dec.get('trackAngle',180))
    kind='midspin' if dec.get('trackType')=='Midspin' else 'full' if angle in (0,360) else 'normal'
    note=dict(x=24,y=24,entry_angle=math.pi,exit_angle=-math.radians(180-angle),spin_kind=kind)
    x,y,part=surface([note,note,note],1)
    pixels=Image.new('L',(48,48));pixels.paste(part,(x,y))
    p=np.asarray(pixels);rgba=np.zeros((48,48,4),dtype=np.uint8)
    rgba[p>0]=[215,215,215,255]
    rgba[p>=3]=[255,255,255,255]
    return np.asarray(Image.fromarray(rgba).resize((300,300),Image.Resampling.NEAREST))


def expanded_moves(data, chart):
    actions = list(data.get('featured_actions', []))
    for event in data.get('featured_actions', []):
        if event['eventType']=='SetText':
            actions.append(dict(event,eventType='MoveDecorations',duration=0,
                                decorationImage='@text:'+event.get('decText','')))
        if event['eventType']=='SetObject':
            converted=dict(event,eventType='MoveDecorations')
            if 'trackColor' in event:converted['color']=event['trackColor']
            if 'trackOpacity' in event:converted['opacity']=event['trackOpacity']
            actions.append(converted)
    moves = [a for a in actions if a['eventType'] == 'MoveDecorations' and enabled(a.get('active', True))]
    conditions = {a['floor']: a for a in actions if a['eventType'] == 'SetConditionalEvents'}
    conditional_tags = {v for c in conditions.values() for k, v in c.items() if k.endswith('Tag') and v != 'NONE'}
    def beat(floor):
        return 60 / data['bpm'] / chart['notes'][floor]['speed'] * FPS
    result = []
    for order, move in enumerate(moves):
        if move.get('eventTag') in conditional_tags:
            continue
        floor = move['floor']
        start = chart['notes'][floor]['time'] * FPS + move.get('angleOffset', 0) / 180 * beat(floor)
        result.append((start, order, move.get('duration', 0) * beat(floor), move))
    for repeat in actions:
        if repeat['eventType'] != 'RepeatEvents' or not enabled(repeat.get('active', True)):
            continue
        tag = repeat.get('tag', '')
        if not tag or tag in conditional_tags:
            continue
        for order, move in enumerate(moves):
            if tag not in move.get('eventTag', '').split():
                continue
            for k in range(1, repeat.get('repetitions', 0)+1):
                floor = repeat['floor']
                mode = repeat.get('repeatType', 'Beat')
                current = floor+k*repeat.get('floorCount', 1) if mode == 'Floor' else floor
                if current >= len(chart['notes']):
                    break
                origin = current if enabled(repeat.get('executeOnCurrentFloor', False)) else move['floor']
                start = chart['notes'][current]['time'] * FPS + move.get('angleOffset', 0)/180*beat(origin)
                if mode == 'Beat':
                    start += k*repeat.get('interval', 1)*beat(floor)
                result.append((start, order, move.get('duration', 0)*beat(origin), move))
    return sorted(result, key=lambda row: row[:2])


class Tween:
    """Replacement tweens complete the old target before starting the new one."""
    def __init__(self, initial, commands):
        self.initial = initial
        self.rows = []
        prior = initial
        for start, duration, target, ease in commands:
            self.rows.append((start, duration, prior, target, ease))
            prior = target
        self.times = [r[0] for r in self.rows]

    def at(self, frame):
        index = bisect.bisect_right(self.times, frame)-1
        if index < 0:
            return self.initial
        start, duration, previous, target, ease = self.rows[index]
        phase = 1 if duration <= 0 else min(1, (frame-start)/duration)
        return previous+(target-previous)*easing(ease, phase)


def actor_camera_events(data, chart, end):
    """Use a separate projection for live actors on a pre-rendered PNG track.

    Shared planet proxies are an affine transform around the authored camera.
    Existing camera/zoom records already retain that state across checkpoints;
    the raster camera stays unchanged in the source metadata.
    """
    proxies = [d for d in data.get('featured_decorations', [])
               if d.get('relativeTo') in ('RedPlanet','BluePlanet') and d.get('opacity',100)==100]
    if len(proxies)!=2 or {d['relativeTo'] for d in proxies}!={'RedPlanet','BluePlanet'}:
        raise ValueError('A replacement track needs one visible proxy per primary planet')
    moves=expanded_moves(data,chart);tracks=[]
    for dec in proxies:
        initial=[*dec.get('position',(0,0)),*dec.get('parallaxOffset',(0,0))]
        commands=[[] for _ in initial];tags=set(dec.get('tag','').split())
        for start,_,duration,event in moves:
            if not tags.intersection(event.get('tag','').split()):continue
            if 'opacity' in event and event['opacity']!=100:
                raise ValueError('Planet-proxy visibility needs live sprite support')
            for key,axes in [('positionOffset',(0,1)),('parallaxOffset',(2,3))]:
                for axis,value in zip(axes,event.get(key,(None,None))):
                    if value is not None:
                        target=value+initial[axis] if axis<2 else value
                        commands[axis].append((start,duration,target,event.get('ease','Linear')))
        tracks.append([Tween(v,c) for v,c in zip(initial,commands)])
    parallax=proxies[0].get('parallax',[0,0])
    if parallax!=proxies[1].get('parallax',[0,0]) or parallax[0]!=parallax[1]:
        raise ValueError('Asymmetric planet-proxy parallax needs independent actor transforms')
    scale=1-parallax[0]/100
    if scale<=0:raise ValueError('Nonpositive planet-proxy scale')
    cameras={f:(x,y) for f,x,y in chart['camera_follow_versions']}
    matrices={f:(co,si) for f,co,si in chart['camera_projection_versions']}
    zooms={f:(z,inv) for f,z,inv in chart['camera_zoom_versions']}
    camera=cameras[0];matrix=matrices[0];zoom=zooms[0];previous=None;events=[];versions=[]
    for frame in range(end+1):
        camera=cameras.get(frame,camera);matrix=matrices.get(frame,matrix);zoom=zooms.get(frame,zoom)
        values=[[t.at(frame) for t in track] for track in tracks]
        if any(abs(a-b)>1e-6 for a,b in zip(*values)):
            raise ValueError(('Independent planet-proxy motion',frame))
        x,y,px,py=values[0]
        pose=(round(camera[0]-24*x-24*px/scale),round(camera[1]+24*y+24*py/scale),
              *(round(v*scale) for v in matrix),round(zoom[0]/scale),round(zoom[1]*scale))
        if not all(-32767<=v<=32767 for v in pose):raise ValueError(('Actor projection range',frame,pose))
        if pose!=previous:
            cx,cy,co,si,z,inv=pose
            events.extend([(frame,10,cx&65535,cy&65535,b''),
                           (frame,15,co&65535,si&65535,b''),
                           (frame,6,z&65535,inv&65535,b'')])
            versions.append([frame,*pose]);previous=pose
    return events,versions


class DecorationTracks:
    def __init__(self, data, chart):
        self.objects = []
        self.planet_proxies = []
        self.pending = []
        self.images = {}
        self.text_contrast=chart.get('decoration_text_contrast',False)
        self.respect_track_depth=chart.get('decoration_depth_order',False)
        self.background_resolution=chart.get('decoration_background_resolution',1)
        self.background_only=chart.get('decoration_background_only',False)
        self.background_brightness=chart.get('decoration_background_brightness',1.)
        self.camera_samples = chart.get('camera_sampling_versions', chart.get('camera_rotation_versions', [[0,256,0]]))
        self.camera_sample_times = [r[0] for r in self.camera_samples]
        self.initial_camera_scale = max(.001, math.hypot(*self.camera_samples[0][1:])/256)
        self.world_origin=(chart['notes'][0]['x'],chart['notes'][0]['y'])
        directory = Path(data['source']).parent
        for event in data.get('featured_actions',[]):
            if event['eventType']=='SetText':
                name='@text:'+event.get('decText','')
                if name not in self.images:self.images[name]=text_image(event.get('decText',''))
        moves = expanded_moves(data, chart)
        for order, dec in enumerate(data.get('featured_decorations', [])):
            gameplay_floor=dec['eventType']=='AddObject' and dec.get('objectType')=='Floor'
            if chart.get('decoration_gameplay_images') and dec.get('decorationImage') not in chart['decoration_gameplay_images']:
                continue
            gameplay_floor=gameplay_floor or bool(chart.get('decoration_gameplay_images'))
            # Performance editions omit only explicitly selected scenery.
            # Native floor objects and PNG track/timing cues remain intact.
            if (dec['eventType']=='AddDecoration' and
                    set(dec.get('tag','').split()).intersection(chart.get('decoration_background_tags',[]))):
                continue
            if dec['eventType']=='AddObject':
                if dec.get('objectType')=='Planet' and dec.get('relativeTo') in ('RedPlanet','BluePlanet','GreenPlanet'):
                    self.planet_proxies.append(dec)
                    continue
                if (dec.get('objectType')=='Floor' and dec.get('trackIcon')=='Portal'
                        and dec.get('trackColor','ffffff')[6:8]=='00'):
                    self.images['@portal']=portal_image()
                    dec=dict(dec,eventType='AddDecoration',decorationImage='@portal')
                elif dec.get('objectType')=='Floor' and dec.get('trackIcon','None')=='None':
                    name='@floor:'+str(dec.get('trackAngle',180))+':'+dec.get('trackType','Normal')
                    if name not in self.images:self.images[name]=floor_image(dec)
                    dec=dict(dec,eventType='AddDecoration',decorationImage=name,
                             color=dec.get('trackColor','ffffff'),opacity=dec.get('trackOpacity',100))
                else:raise ValueError(('Unsupported native decoration object',dec.get('objectType'),dec.get('tag')))
            if dec['eventType']=='AddText':
                name='@text:'+dec.get('decText','')
                self.images[name]=text_image(dec.get('decText',''))
                dec=dict(dec,eventType='AddDecoration',decorationImage=name)
            if dec['eventType'] != 'AddDecoration':
                continue
            if dec.get('relativeTo') in ('RedPlanet', 'BluePlanet', 'GreenPlanet'):
                self.planet_proxies.append(dec)
                continue
            if dec.get('relativeTo', 'Tile') not in ('Tile','Camera','CameraAspect'):
                raise ValueError(('Unsupported decoration placement', dec.get('relativeTo')))
            if dec.get('maskingType', 'None') != 'None':
                raise ValueError(('Unsupported decoration mask', dec.get('tag')))
            if any(v<=0 for v in dec.get('tile',[1,1])):
                raise ValueError(('Nonpositive decoration tiling',dec.get('tag')))
            note = chart['notes'][max(0,min(dec.get('floor',0),len(chart['notes'])-1))]
            offset = note.get('position_track_offset', (0, 0))
            origin = (note['x']+offset[0], note['y']+offset[1])
            placement=dec.get('relativeTo','Tile')
            def placement_base(kind):
                px,py=dec.get('position',(0,0))
                if kind in ('Camera','CameraAspect'):return [px,py]
                ox,oy=origin if kind=='Tile' else self.world_origin
                return [(ox-self.world_origin[0])/16+px*1.5,
                        (self.world_origin[1]-oy)/16+py*1.5]
            base_position=placement_base(placement)
            placements=[(float('-inf'),placement)]
            initial = [*base_position, dec.get('rotation', 0),
                       *dec.get('scale', (100, 100)), dec.get('opacity', 100),
                       *dec.get('parallaxOffset', (0, 0)),
                       *[int(dec.get('color', 'ffffff')[i:i+2],16) for i in (0,2,4)],
                       int(dec.get('color','ffffff')[6:8] or 'ff',16),
                       int(enabled(dec.get('visible',True))) ]
            commands = [[] for _ in initial]
            images = [(float('-inf'), dec.get('decorationImage', ''))]
            tags = set(dec.get('tag', '').split())
            for start, _, duration, move in moves:
                if not tags.intersection(move.get('tag', '').split()):
                    continue
                movement=move.get('relativeTo')
                if movement not in (None,'LastPosition','Tile','Global','Camera','CameraAspect'):
                    raise ValueError(('Unsupported decoration movement space',movement))
                if movement not in (None,'LastPosition'):
                    placement=movement;base_position=placement_base(placement)
                    placements.append((start,placement))
                for key, axes in (('positionOffset', (0, 1)), ('rotationOffset', (2,)),
                                  ('scale', (3, 4)), ('opacity', (5,)), ('parallaxOffset', (6, 7))):
                    if key not in move:
                        continue
                    values = move[key] if len(axes) == 2 else [move[key]]
                    for axis, value in zip(axes, values):
                        if value is not None:
                            if axis<2:
                                base=Tween(initial[axis],commands[axis]).at(start) if movement=='LastPosition' else base_position[axis]
                                target=base+value*1.5
                            else:target=value+initial[axis] if axis==2 else value
                            commands[axis].append((start, duration, target, move.get('ease', 'Linear')))
                if 'decorationImage' in move:
                    images.append((start, move['decorationImage']))
                if 'visible' in move:
                    commands[12].append((start,0,int(enabled(move['visible'])),'Linear'))
                if 'color' in move:
                    commands[11].append((start,duration,int(move['color'][6:8] or 'ff',16),move.get('ease','Linear')))
                    for axis,at in enumerate((0,2,4),8):
                        commands[axis].append((start,duration,int(move['color'][at:at+2],16),move.get('ease','Linear')))
            for _, name in images:
                if name and name not in self.images:
                    self.images[name] = np.asarray(Image.open(directory/name).convert('RGBA'))
            self.objects.append(dict(origin=origin, gameplay_floor=gameplay_floor, text=dec.get('decorationImage','').startswith('@text:'), tracks=[Tween(v, c) for v, c in zip(initial, commands)],
                                     images=images, image_times=[r[0] for r in images],
                                     pivot=dec.get('pivotOffset', [0, 0]), color=dec.get('color', 'ffffff')[:6],
                                     parallax=dec.get('parallax', [0, 0]),
                                     depth=dec.get('depth', 0), order=order,
                                     blend=dec.get('blendMode','None'),
                                     tile=dec.get('tile',[1,1]),
                                     placements=placements,placement_times=[v[0] for v in placements],
                                     lock_rotation=dec.get('lockRotation',False),
                                     lock_scale=dec.get('lockScale',False)))
        self.objects.sort(key=lambda o: (-o['depth'], o['order']))

    def draw(self, image, frame, px, py, top, palette, camera=None):
        layer = np.zeros((*px.shape, 4), dtype=np.uint8)
        under=palette[image[top+1:top+1+px.shape[0]]]
        layer[:,:,:3]=np.stack([(under&31)*8,((under>>5)&31)*8,((under>>10)&31)*8],axis=-1)
        native_rgb=layer[:,:,:3].copy()
        native_mask=image[top+1:top+1+px.shape[0]]!=0
        if self.background_only:layer[native_mask,:3]=0
        floor_mask=np.zeros(px.shape,dtype=bool)
        floor_rgb=layer[:,:,:3].copy()
        restored=False
        def restore_native():
            if self.background_resolution>1:
                # Scenery alone uses a smaller sampling grid. Restore native
                # track pixels afterwards at their original resolution.
                factor=self.background_resolution
                small=Image.fromarray(layer).resize((layer.shape[1]//factor,layer.shape[0]//factor),Image.Resampling.BOX)
                layer[:]=np.asarray(small.resize((layer.shape[1],layer.shape[0]),Image.Resampling.NEAREST))
            if self.background_only:
                layer[:,:,:3]=(layer[:,:,:3].astype(float)*self.background_brightness).astype(np.uint8)
            if self.background_resolution>1 or self.background_only:
                layer[floor_mask,:3]=floor_rgb[floor_mask]
                layer[floor_mask,3]=255
            if self.respect_track_depth:
                layer[native_mask,:3]=native_rgb[native_mask]
                layer[native_mask,3]=0
        left,right,bottom,upper = px.min(),px.max(),py.min(),py.max()
        for obj in self.objects:
            if obj['depth']<0 and not restored and not self.background_only:
                restore_native();restored=True
            x, y, rotation, sx, sy, opacity, parallax_x, parallax_y, red, green, blue, color_alpha, visible = [t.at(frame) for t in obj['tracks']]
            opacity *= color_alpha/255*visible
            if opacity <= 0 or abs(sx) < .001 or abs(sy) < .001:
                continue
            name = obj['images'][bisect.bisect_right(obj['image_times'], frame)-1][1]
            if not name:
                continue
            rgba = self.images[name]
            sample = self.camera_samples[bisect.bisect_right(self.camera_sample_times,frame)-1]
            camera_co,camera_si = sample[1]/256,sample[2]/256
            if obj['lock_rotation']:
                rotation += math.degrees(math.atan2(camera_si,camera_co))
            if obj['lock_scale']:
                factor=math.hypot(camera_co,camera_si)/self.initial_camera_scale
                sx*=factor;sy*=factor
            co, si = math.cos(math.radians(rotation)), math.sin(math.radians(rotation))
            placement=obj['placements'][bisect.bisect_right(obj['placement_times'],frame)-1][1]
            world_x, world_y = self.world_origin[0]+16*x, self.world_origin[1]-16*y
            if placement in ('Camera','CameraAspect'):
                if camera is None:raise ValueError('Screen decoration requires a camera center')
                unit_x=(px.shape[0] if placement=='CameraAspect' else px.shape[1])/20
                dx=(x+obj['pivot'][0])*unit_x
                dy=-(y+obj['pivot'][1])*px.shape[0]/20
                world_x=camera[0]+dx*camera_co+dy*camera_si
                world_y=camera[1]-dx*camera_si+dy*camera_co
            elif any(obj['parallax']):
                if camera is None:
                    raise ValueError('Parallax decorations require the authored camera center')
                world_x += (camera[0]-world_x)*obj['parallax'][0]/100+24*parallax_x
                world_y += (camera[1]-world_y)*obj['parallax'][1]/100-24*parallax_y
            hw,hh = abs(rgba.shape[1]*.0008*sx),abs(rgba.shape[0]*.0008*sy)
            extent_x = abs(co)*hw+abs(si)*hh+24*sum(map(abs,obj['pivot']))
            extent_y = abs(si)*hw+abs(co)*hh+24*sum(map(abs,obj['pivot']))
            if world_x+extent_x<left or world_x-extent_x>right or world_y+extent_y<bottom or world_y-extent_y>upper:
                continue
            # Restrict inverse projection to pixels inside the conservative world
            # bounds. This preserves every sample while avoiding full-screen
            # float transforms for each small authored track decoration.
            bounds = ((px >= world_x-extent_x) & (px <= world_x+extent_x)
                      & (py >= world_y-extent_y) & (py <= world_y+extent_y))
            yy, xx = np.nonzero(bounds)
            dx, dy = px[yy, xx]-world_x, py[yy, xx]-world_y
            # Source images use 100 pixels/Unity unit, and 16 world pixels/unit.
            u = (dx*co-dy*si-24*obj['pivot'][0])/(.0016*sx)+rgba.shape[1]/2
            v = (dx*si+dy*co+24*obj['pivot'][1])/(.0016*sy)+rgba.shape[0]/2
            mask = (u >= 0) & (v >= 0) & (u < rgba.shape[1]) & (v < rgba.shape[0])
            yy, xx = yy[mask], xx[mask]
            uu=(u[mask]*obj['tile'][0])%rgba.shape[1]
            vv=(v[mask]*obj['tile'][1])%rgba.shape[0]
            sample = rgba[vv.astype(int), uu.astype(int)].copy()
            alpha=np.clip(sample[:,3].astype(float)/255*opacity/100,0,1)
            visible = alpha > 0
            yy, xx, sample = yy[visible], xx[visible], sample[visible]
            tint = np.array([red,green,blue])
            # The port uses a dark playfield instead of the beta's white
            # background. Keep neutral dark instructions readable while
            # retaining colored spans and authored opacity transitions.
            if self.text_contrast and obj['text'] and max(tint)<96 and max(tint)-min(tint)<16:
                tint=np.array([240,240,240])
            a=alpha[visible,None]
            source_rgb=sample[:,:3].astype(float)*tint/255
            destination_rgb=layer[yy,xx,:3].astype(float)
            if self.background_only and obj['gameplay_floor']:
                existing=floor_mask[yy,xx]
                destination_rgb[existing]=floor_rgb[yy[existing],xx[existing]]
            if obj['blend']=='Difference':
                # Difference is a color operation, not an opaque foreground.
                # White inverts the underlying track; it must not erase it.
                source_rgb=np.abs(destination_rgb-source_rgb)
            sample[:, :3] = np.clip(source_rgb*a+destination_rgb*(1-a),0,255).astype(np.uint8)
            sample[:,3]=255
            if not (self.background_only and obj['gameplay_floor']):layer[yy, xx] = sample
            if obj['gameplay_floor']:
                floor_mask[yy,xx]=True
                floor_rgb[yy,xx]=sample[:,:3]
        if not restored:restore_native()
        mask = layer[:, :, 3] >= 128
        if not mask.any():
            return image
        used = set(image.ravel())
        available = [i for i in range(32, 128) if i not in used]
        if len(available) < 12:
            raise ValueError('Not enough free source palette entries for decoration art')
        # One shared SNES palette for custom art; native track pixels are intact.
        protected=floor_mask&~native_mask if self.background_only else np.zeros(px.shape,dtype=bool)
        floor_words=np.array([],dtype=np.uint16)
        floor_inverse=np.array([],dtype=np.intp)
        if protected.any():
            rgb=floor_rgb[protected].astype(np.uint16)>>3
            floor_words,floor_inverse=np.unique(rgb[:,0]|(rgb[:,1]<<5)|(rgb[:,2]<<10),return_inverse=True)
        count=min(12,len(available)-len(floor_words))
        if count<1:raise ValueError(('Gameplay floor colors exceed source palette',frame,len(floor_words)))
        colors = Image.fromarray(layer[:, :, :3]).quantize(colors=count, method=Image.Quantize.FASTOCTREE)
        indices = np.asarray(colors)
        rgb = np.array(colors.getpalette(), dtype=np.uint16).reshape(-1, 3)[:count] >> 3
        words = rgb[:, 0] | (rgb[:, 1] << 5) | (rgb[:, 2] << 10)
        slots = np.array(available[:count], dtype=np.uint8)
        palette[slots] = words
        image[top+1:top+1+px.shape[0]][mask] = slots[indices[mask]]
        if protected.any():
            floor_slots=np.array(available[count:count+len(floor_words)],dtype=np.uint8)
            palette[floor_slots]=floor_words
            image[top+1:top+1+px.shape[0]][protected]=floor_slots[floor_inverse]
        return image
