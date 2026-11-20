"""Sample authored PNG track decorations before screen-pose encoding.

This is an offline renderer, not a replacement floor layout. Planet-relative
images are reported separately because their transforms must follow live input.
"""
import bisect
import collections
import math
import re
import json
from pathlib import Path

import numpy as np
from PIL import Image,ImageDraw,ImageFont,ImageColor

from make_assets import FPS
from track_motion import enabled, easing


def text_image(text, *, stage_punctuation=False):
    """Keep instructional text readable with the project's editable CHR font."""
    text=text.encode('utf-16-le',errors='surrogatepass').decode('utf-16-le',errors='replace')
    text=text.translate(str.maketrans({'“':'"','”':'"','‘':"'",'’':"'",'–':'-','—':'-'}))
    text=text.replace('²','^2').replace('´',"'").replace('\ufffd','?').replace('…','...')
    font=(Path(__file__).resolve().parents[1]/'assets/graphics/campaign/font.chr').read_bytes()
    mathfont=(Path(__file__).resolve().parents[1]/'assets/graphics/campaign/math-font.chr').read_bytes()
    punctuation=(Path(__file__).resolve().parents[1]/'assets/graphics/campaign/stage-punctuation.chr').read_bytes() if stage_punctuation else b''
    # Color is part of instructions such as "blue tiles are twirls".
    # Parse the supported TMP color spans without drawing markup as glyphs.
    lines=[[]];colors=[(255,255,255,255)]
    for token in re.split(r'(<[^<>]*>)',text):
        if token.lower().startswith('<color='):
            value=token[7:-1].strip('\"\'')
            if re.fullmatch(r'[0-9a-fA-F]{6}(?:[0-9a-fA-F]{2})?',value):value='#'+value
            try:colors.append(ImageColor.getcolor(value,'RGBA'))
            except ValueError as exc:raise ValueError(('Unsupported text color',token)) from exc
        elif token.lower()=='</color>':
            if len(colors)>1:colors.pop()
        elif re.fullmatch(r'</?(?:b|i|size(?:=[0-9.]+)?)>',token,re.I):
            # Raster size is controlled by the authored decoration transform.
            # Retain text content when TMP adds an emphasis/size span.
            continue
        elif token.startswith('<') and token.endswith('>'):
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
            elif char in '↓←→➜':
                glyph={'↓':2,'←':3,'→':4,'➜':4}[char]
                raw=font[glyph*16:(glyph+1)*16]
                pixels=np.array([[bool((raw[y*2]|raw[y*2+1])&(128>>x)) for x in range(8)] for y in range(8)])
            elif ord(char)<128 or char in '√×Π':
                glyph='√×Π'.index(char) if char in '√×Π' else ord(char)
                sheet=mathfont if char in '√×Π' else font
                raw=(punctuation["&'".index(char)*16: ("&'".index(char)+1)*16]
                     if stage_punctuation and char in "&'" else sheet[glyph*16:glyph*16+16])
                pixels=np.array([[bool((raw[y*2]|raw[y*2+1])&(128>>x)) for x in range(8)] for y in range(8)])
            else:
                hangul=0x1100<=ord(char)<=0x11ff or 0x3130<=ord(char)<=0x318f or 0xac00<=ord(char)<=0xd7af
                mathematical=0x370<=ord(char)<=0x3ff or 0x2200<=ord(char)<=0x22ff
                if not (0x3000<=ord(char)<=0x9fff or hangul or mathematical or char in '°△±÷'):
                    raise ValueError(('Unsupported instructional text character',char))
                # Keep non-Latin chart titles readable without adding a
                # cartridge font engine. Only these static source glyphs
                # use the host font; ordinary instructions use editable CHR.
                host=Path('C:/Windows/Fonts/malgun.ttf' if hangul else 'C:/Windows/Fonts/msgothic.ttc')
                if not host.exists():raise ValueError('Source text requires its Unicode font: '+str(host))
                glyph=Image.new('L',(64,64));ImageDraw.Draw(glyph).text((0,0),char,font=ImageFont.truetype(str(host),56),fill=255)
                pixels=np.asarray(glyph.resize((8,8),Image.Resampling.BOX))>=64
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


def swirl_image(red=False):
    return object_icon_image(36 if red else 38,144 if red else 160)


def object_icon_image(base,bank):
    root=Path(__file__).resolve().parents[1]/'assets/graphics/campaign'
    sheet=(root/'objects.chr').read_bytes();palette=np.frombuffer((root/'palette.bin').read_bytes(),dtype='<u2')
    canvas=np.zeros((16,16,4),dtype=np.uint8)
    for y in range(16):
        for x in range(16):
            offset=(base+x//8+(y//8)*16)*32
            value=sum(((sheet[offset+(b//2)*16+(y%8)*2+b%2]>>(7-x%8))&1)<<b for b in range(4))
            if value:
                word=int(palette[bank+value])
                canvas[y,x]=[(word&31)*8,((word>>5)&31)*8,((word>>10)&31)*8,255]
    return np.asarray(Image.fromarray(canvas).resize((100,100),Image.Resampling.NEAREST))


def planet_image():
    """Tintable planet artwork from the editable OBJ sheet, at native size."""
    root=Path(__file__).resolve().parents[1]/'assets/graphics/campaign'
    sheet=(root/'objects.chr').read_bytes()
    palette=np.frombuffer((root/'palette.bin').read_bytes(),dtype='<u2')
    canvas=np.zeros((16,16,4),dtype=np.uint8)
    for y in range(16):
        for x in range(16):
            tile=6+x//8+(y//8)*16;offset=tile*32
            value=sum(((sheet[offset+(b//2)*16+(y%8)*2+b%2]>>(7-x%8))&1)<<b for b in range(4))
            if value:
                word=int(palette[192+value]);light=max((word>>s)&31 for s in (0,5,10))
                shade=255 if light>=24 else 190 if light>=12 else 125
                canvas[y,x]=[shade,shade,shade,255]
    # The ordinary 16-pixel planet occupies one Unity unit. Custom PNGs
    # use 100 pixels/unit, so retain that scale for AddObject planets.
    return np.asarray(Image.fromarray(canvas).resize((100,100),Image.Resampling.NEAREST))


def replacement_images(level,directory=None):
    root=Path(__file__).resolve().parents[1]/'assets/graphics'
    entries=json.loads((root/'community-image-replacements.json').read_text(encoding='utf-8')).get(str(level),{})
    result={}
    for name,entry in entries.items():
        kind=entry['kind']
        if kind=='planet':pixels=planet_image()
        elif kind=='portal':pixels=portal_image()
        elif kind=='text':pixels=text_image(entry['text'])
        elif kind=='source':
            assert directory is not None,'Source artwork replacement needs the chart directory'
            pixels=np.asarray(Image.open(Path(directory)/entry['image']).convert('RGBA'))
        elif kind=='warning':
            raw=(root/'mode7/freeroam.chr').read_bytes()[5*32:6*32]
            pixels=np.zeros((8,8,4),dtype=np.uint8)
            for y in range(8):
                for x in range(8):
                    value=sum(((raw[(b//2)*16+y*2+b%2]>>(7-x))&1)<<b for b in range(4))
                    if value:pixels[y,x]=[255,80,64,255]
        else:raise ValueError(('Unknown replacement artwork',kind))
        if 'size' in entry:pixels=np.asarray(Image.fromarray(pixels).resize(tuple(entry['size']),Image.Resampling.NEAREST))
        result[name]=pixels
    return result


def floor_image(dec):
    """Draw native AddObject floors with the same geometry as playable tiles."""
    from track_geometry import surface
    angle=float(dec.get('trackAngle',180))
    kind='midspin' if dec.get('trackType')=='Midspin' else 'full' if angle in (0,360) else 'normal'
    note=dict(x=24,y=24,entry_angle=math.pi,exit_angle=-math.radians(180-angle),spin_kind=kind)
    note['gem_platform']=dec.get('trackStyle')=='Gems'
    x,y,part=surface([note,note,note],1)
    pixels=Image.new('L',(48,48));pixels.paste(part,(x,y))
    p=np.asarray(pixels);rgba=np.zeros((48,48,4),dtype=np.uint8)
    if note['gem_platform']:
        from track_geometry import STYLE
        rgba[p>0]=[*[round(v*255) for v in STYLE['gem_platform_dark']],255]
        rgba[p>=3]=[*[round(v*255) for v in STYLE['gem_platform_light']],255]
    else:
        rgba[p>0]=[215,215,215,255]
        rgba[p>=3]=[255,255,255,255]
    return np.asarray(Image.fromarray(rgba).resize((300,300),Image.Resampling.NEAREST))


def planet_object_color(event):
    kind=event.get('planetColorType','Custom')
    if kind=='Custom':return event.get('planetColor','ffffff')
    presets={'DefaultRed':'ff0000','DefaultBlue':'0000ff','DefaultGreen':'00ff00'}
    if kind not in presets:raise ValueError(('Unsupported scripted planet color preset',kind))
    return presets[kind]


def expanded_moves(data, chart):
    actions = list(data.get('featured_actions', []))
    for event in data.get('featured_actions', []):
        if event['eventType']=='SetText':
            actions.append(dict(event,eventType='MoveDecorations',duration=0,
                                decorationImage='@text:'+event.get('decText','')))
        if event['eventType']=='SetObject':
            converted=dict(event,eventType='MoveDecorations')
            if 'trackColor' in event:converted['color']=event['trackColor']
            if 'planetColor' in event or 'planetColorType' in event:
                converted['planet_color']=planet_object_color(event)
            if 'trackOpacity' in event:converted['opacity']=event['trackOpacity']
            actions.append(converted)
    moves = [a for a in actions if a['eventType'] == 'MoveDecorations' and enabled(a.get('active', True))]
    conditions = {a['floor']: a for a in actions if a['eventType'] == 'SetConditionalEvents'}
    conditional_tags = {tag for c in conditions.values() for k,v in c.items() if k.endswith('Tag')
                        for tag in str(v).split() if tag!='NONE'}
    touch_tags={tag for d in data.get('featured_decorations',[]) if d.get('hitbox')=='Event'
                for tag in d.get('hitboxEventTag','').split()} if chart.get('conditional_visual_success_route') else set()
    def beat(floor):
        return 60 / data['bpm'] / chart['notes'][floor]['speed'] * FPS
    result = []
    for order, move in enumerate(moves):
        if set(move.get('eventTag','').split()) & (conditional_tags|touch_tags):
            continue
        floor = move['floor']
        start = chart['notes'][floor]['time'] * FPS + move.get('angleOffset', 0) / 180 * beat(floor)
        result.append((round(start,8), order, move.get('duration', 0) * beat(floor), move))
    if chart.get('conditional_visual_success_route'):
        # Valid rhythm input can activate an event declared on another floor.
        # Sample the successful route on the song clock; failed inputs still
        # follow the cartridge's judgment/death rules. Touch collectibles are
        # handled by the live objective layer and must never fire on load.
        tagged=collections.defaultdict(list)
        for order,move in enumerate(moves):
            for tag in set(move.get('eventTag','').split()) & conditional_tags:tagged[tag].append((order,move))
        condition={}
        for floor,note in enumerate(chart['notes']):
            condition=conditions.get(floor,condition)
            if not floor or note.get('flags',0)&8:continue
            for tag in {condition.get(k,'NONE') for k in ('perfectTag','hitTag')} - {'','NONE'}:
                for order,move in tagged[tag]:
                    start=note['time']*FPS+move.get('angleOffset',0)/180*beat(floor)
                    result.append((round(start,8),order,move.get('duration',0)*beat(floor),move))
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
                result.append((round(start,8), order, move.get('duration', 0)*beat(origin), move))
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
    # Converted charts can retain a legacy PNG and its native Planet
    # replacement under the same tag. They are one logical actor.
    selected={}
    for proxy in sorted(proxies,key=lambda d:d.get('objectType')!='Planet'):
        key=proxy['relativeTo']
        if key in selected:
            previous=selected[key]
            for field,default in (('position',[0,0]),('parallax',[0,0]),('parallaxOffset',[0,0])):
                if proxy.get(field,default)!=previous.get(field,default):
                    raise ValueError(('Independent duplicate planet proxy',key,field))
            if set(proxy.get('tag','').split())!=set(previous.get('tag','').split()):
                raise ValueError(('Independent duplicate planet proxy tags',key))
        else:selected[key]=proxy
    proxies=list(selected.values())
    if len(proxies)!=2 or {d['relativeTo'] for d in proxies}!={'RedPlanet','BluePlanet'}:
        raise ValueError('A replacement track needs one visible proxy per primary planet')
    moves=expanded_moves(data,chart);tracks=[]
    for dec in proxies:
        initial=[*dec.get('position',(0,0)),*dec.get('parallaxOffset',(0,0))]
        commands=[[] for _ in initial];tags=set(dec.get('tag','').split())
        for start,_,duration,event in moves:
            if not tags.intersection(event.get('tag','').split()):continue
            if 'opacity' in event and event['opacity'] not in (0,100):
                raise ValueError('Partial planet-proxy opacity needs live sprite support')
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
        if data.get('id')==284:
            from overclocked_readability import title_actions
            data=dict(data,featured_actions=title_actions(data.get('featured_actions',[])))
        self.objects = []
        self.planet_proxies = []
        self.pending = []
        self.images = {}
        self.text_contrast=chart.get('decoration_text_contrast',False)
        self.respect_track_depth=chart.get('decoration_depth_order',False)
        self.background_resolution=chart.get('decoration_background_resolution',1)
        self.background_only=chart.get('decoration_background_only',False)
        self.background_brightness=chart.get('decoration_background_brightness',1.)
        self.local_pivots=chart.get('local_decoration_pivots',False)
        self.backdrop=chart.get('decoration_backdrop')
        self.backdrop_colors=[]
        if chart.get('authored_decoration_backdrop'):
            self.backdrop=data.get('track_settings',{}).get('backgroundColor','000000')
            for event in data.get('featured_actions',[]):
                if event['eventType']!='CustomBackground' or event.get('eventTag') or not enabled(event.get('active',True)):continue
                note=chart['notes'][event['floor']]
                when=round((note['time']+event.get('angleOffset',0)/180*60/data['bpm']/note['speed'])*FPS)
                self.backdrop_colors.append((when,event.get('color',self.backdrop)))
            self.backdrop_colors.sort(key=lambda row:row[0])
        self.camera_samples = chart.get('camera_sampling_versions', chart.get('camera_rotation_versions', [[0,256,0]]))
        self.camera_sample_times = [r[0] for r in self.camera_samples]
        self.initial_camera_scale = max(.001, math.hypot(*self.camera_samples[0][1:])/256)
        self.world_origin=(chart['notes'][0]['x'],chart['notes'][0]['y'])
        self.camera_view_height=144 if chart.get('snapshot_map_top',32)==16 else None
        self.protect_gameplay=chart.get('protect_gameplay_from_vfx',False)
        directory = Path(data['source']).parent
        self.images.update({name:pixels for name,pixels in replacement_images(data.get('id'),directory).items()
                            if not (directory/name).exists()})
        for event in data.get('featured_actions',[]):
            if event['eventType']=='SetText':
                name='@text:'+event.get('decText','')
                if name not in self.images:self.images[name]=text_image(event.get('decText',''))
        moves = expanded_moves(data, chart)
        self.actor_anchors=None
        if any(move.get('relativeTo') in ('RedPlanet','BluePlanet','GreenPlanet') for _,_,_,move in moves):
            from decoration_actors import ActorAnchors
            self.actor_anchors=ActorAnchors(data,chart)
        moves_by_tag=collections.defaultdict(list)
        for move in moves:
            for tag in set(move[3].get('tag','').split()):moves_by_tag[tag].append(move)
        decorations=[]
        for dec in data.get('featured_decorations',[]):
            icon=dec.get('trackIcon','None')
            if dec['eventType']=='AddObject' and dec.get('objectType')=='Floor' and (icon in ('Swirl','Rabbit','Snail','DoubleRabbit','Checkpoint') or icon=='Portal' and dec.get('trackColor','ffffff')[6:8]!='00'):
                name='@object-icon:'+icon+':'+str(bool(dec.get('trackRedSwirl',False)))
                pixels=swirl_image(dec.get('trackRedSwirl',False)) if icon=='Swirl' else object_icon_image(32,144) if icon in ('Rabbit','DoubleRabbit') else object_icon_image(34,160) if icon=='Snail' else portal_image() if icon=='Portal' else object_icon_image(74,176)
                if icon=='DoubleRabbit':
                    small=Image.fromarray(pixels).resize((50,50),Image.Resampling.NEAREST)
                    pair=Image.new('RGBA',(100,100));pair.alpha_composite(small,(0,25));pair.alpha_composite(small,(50,25));pixels=np.asarray(pair)
                self.images.setdefault(name,pixels)
                decorations.append(dict(dec,trackIcon='None'))
                decorations.append(dict(dec,eventType='AddDecoration',decorationImage=name,color='ffffff',
                                        rotation=dec.get('rotation',0)-dec.get('trackIconAngle',0),
                                        depth=dec.get('depth',0)-.001,_floor_icon=True))
            else:decorations.append(dec)
        for order, dec in enumerate(decorations):
            from gameplay_decorations import is_gameplay,is_scripted_planet
            required=is_gameplay(dec,chart)
            if chart.get('decoration_vfx_off') and not required:continue
            if data.get('id')==284 and dec.get('decorationImage') in ('triangle.png','square.png'):
                from overclocked_readability import shortcut_image
                self.images[dec['decorationImage']]=shortcut_image(dec['decorationImage'])
                # These PNGs replace playable floors. Drawing them behind
                # the native floor erased their identifying center symbols.
                dec=dict(dec,depth=-2)
            gameplay_planet=is_scripted_planet(dec)
            gameplay_floor=(dec['eventType']=='AddObject' and dec.get('objectType')=='Floor') or required
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
                if dec.get('objectType')=='Planet':
                    self.images.setdefault('@planet',planet_image())
                    dec=dict(dec,eventType='AddDecoration',decorationImage='@planet',
                             color=planet_object_color(dec))
                elif (dec.get('objectType')=='Floor' and dec.get('trackIcon')=='Portal'
                        and dec.get('trackColor','ffffff')[6:8]=='00'):
                    self.images['@portal']=portal_image()
                    dec=dict(dec,eventType='AddDecoration',decorationImage='@portal')
                elif dec.get('objectType')=='Floor' and dec.get('trackIcon','None')=='None':
                    name='@floor:'+str(dec.get('trackAngle',180))+':'+dec.get('trackType','Normal')+':'+dec.get('trackStyle','Standard')
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
            if dec.get('relativeTo', 'Tile') not in ('Tile','Global','Camera','CameraAspect'):
                raise ValueError(('Unsupported decoration placement', dec.get('relativeTo')))
            if dec.get('maskingType','None') not in ('None','Mask','VisibleInsideMask','VisibleOutsideMask'):
                raise ValueError(('Unsupported decoration mask',dec.get('tag')))
            if any(v<=0 for v in dec.get('tile',[1,1])):
                raise ValueError(('Nonpositive decoration tiling',dec.get('tag')))
            note = chart['notes'][max(0,min(dec.get('floor',0),len(chart['notes'])-1))]
            offset = note.get('position_track_offset', (0, 0))
            origin = (note['x']+offset[0], note['y']+offset[1])
            placement=dec.get('relativeTo','Tile')
            def placement_base(kind):
                px,py=dec.get('position',(0,0))
                if kind in ('Camera','CameraAspect'):return [px,py]
                if kind in ('RedPlanet','BluePlanet','GreenPlanet'):return [px*1.5,py*1.5]
                ox,oy=origin if kind=='Tile' else self.world_origin
                return [(ox-self.world_origin[0])/16+px*1.5,
                        (self.world_origin[1]-oy)/16+py*1.5]
            base_position=placement_base(placement)
            placements=[(float('-inf'),placement)]
            scale=dec.get('scale',(100,100))
            if isinstance(scale,(int,float)):scale=[scale,scale]
            initial = [*base_position, dec.get('rotation', 0),
                       *scale, dec.get('opacity', 100),
                       *dec.get('parallaxOffset', (0, 0)),
                       *[int(dec.get('color', 'ffffff')[i:i+2],16) for i in (0,2,4)],
                       int(dec.get('color','ffffff')[6:8] or 'ff',16),
                       int(enabled(dec.get('visible',True))) ]
            commands = [[] for _ in initial]
            images = [(float('-inf'), dec.get('decorationImage', ''))]
            tags = set(dec.get('tag', '').split())
            matching={id(move):move for tag in tags for move in moves_by_tag[tag]}
            for start, _, duration, move in sorted(matching.values(),key=lambda row:(row[0],row[1])):
                movement=move.get('relativeTo')
                if movement not in (None,'LastPosition','Tile','Global','Camera','CameraAspect','RedPlanet','BluePlanet','GreenPlanet'):
                    raise ValueError(('Unsupported decoration movement space',movement))
                if movement not in (None,'LastPosition'):
                    placement=movement;base_position=placement_base(placement)
                    placements.append((start,placement))
                for key, axes in (('positionOffset', (0, 1)), ('rotationOffset', (2,)),
                                  ('scale', (3, 4)), ('opacity', (5,)), ('parallaxOffset', (6, 7))):
                    if key not in move:
                        continue
                    values = move[key] if len(axes) == 2 else [move[key]]
                    if key=='scale' and isinstance(values,(int,float)):values=[values,values]
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
                if 'color' in move and not dec.get('_floor_icon'):
                    commands[11].append((start,duration,int(move['color'][6:8] or 'ff',16),move.get('ease','Linear')))
                    for axis,at in enumerate((0,2,4),8):
                        commands[axis].append((start,duration,int(move['color'][at:at+2],16),move.get('ease','Linear')))
                if gameplay_planet and 'planet_color' in move:
                    value=move['planet_color']
                    commands[11].append((start,duration,int(value[6:8] or 'ff',16),move.get('ease','Linear')))
                    for axis,at in enumerate((0,2,4),8):
                        commands[axis].append((start,duration,int(value[at:at+2],16),move.get('ease','Linear')))
            for _, name in images:
                if name and name not in self.images:
                    self.images[name] = np.asarray(Image.open(directory/name).convert('RGBA'))
            parallax=dec.get('parallax',[0,0])
            if isinstance(parallax,(int,float)):parallax=[parallax,parallax]
            self.objects.append(dict(source=dec,origin=origin, gameplay_floor=gameplay_floor, gameplay_planet=gameplay_planet, text=dec.get('decorationImage','').startswith('@text:'), tracks=[Tween(v, c) for v, c in zip(initial, commands)],
                                     header=data.get('id')==284 and dec.get('tag') in ('game','game2','game3'),
                                     images=images, image_times=[r[0] for r in images],
                                     pivot=dec.get('pivotOffset', [0, 0]), color=dec.get('color', 'ffffff')[:6],
                                     parallax=parallax,
                                     depth=dec.get('depth', 0), order=order,
                                     blend=dec.get('blendMode','None'),
                                     tile=dec.get('tile',[1,1]),
                                     placements=placements,placement_times=[v[0] for v in placements],
                                     lock_rotation=dec.get('lockRotation',False),
                                     lock_scale=dec.get('lockScale',False),
                                     masking=dec.get('maskingType','None'),
                                     mask_depths=sorted((dec.get('maskingFrontDepth',-32768),dec.get('maskingBackDepth',32767)))
                                         if dec.get('useMaskingDepth',False) else [-32768,32767]))
        self.objects.sort(key=lambda o: (o['masking']!='Mask',-o['depth'],o['order']))

    def draw(self, image, frame, px, py, top, palette, camera=None):
        layer = np.zeros((*px.shape, 4), dtype=np.uint8)
        under=palette[image[top+1:top+1+px.shape[0]]]
        layer[:,:,:3]=np.stack([(under&31)*8,((under>>5)&31)*8,((under>>10)&31)*8],axis=-1)
        native_rgb=layer[:,:,:3].copy()
        native_mask=image[top+1:top+1+px.shape[0]]!=0
        if self.backdrop:
            color=next((color for when,color in reversed(self.backdrop_colors) if when<=frame),self.backdrop)
            value=color.lstrip('#')
            background=np.array([int(value[i:i+2],16) for i in (0,2,4)],dtype=np.uint8)
            layer[~native_mask,:3]=background
            layer[~native_mask,3]=255
        if self.background_only:layer[native_mask,:3]=0
        floor_mask=np.zeros(px.shape,dtype=bool)
        planet_mask=np.zeros(px.shape,dtype=bool)
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
        masks=[]
        for obj in self.objects:
            if obj['masking']!='Mask' and obj['depth']<0 and not restored and not self.background_only:
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
            if obj['header']:
                width=rgba.shape[1]*.0016*abs(sx)/max(.001,math.hypot(camera_co,camera_si))
                fit=min(1,(px.shape[1]-16)/max(1,width))
                sx*=fit;sy*=fit
            co, si = math.cos(math.radians(rotation)), math.sin(math.radians(rotation))
            placement=obj['placements'][bisect.bisect_right(obj['placement_times'],frame)-1][1]
            world_x, world_y = self.world_origin[0]+16*x, self.world_origin[1]-16*y
            if placement in ('RedPlanet','BluePlanet','GreenPlanet'):
                point=self.actor_anchors.at(frame)[placement]
                if point is None:continue
                world_x,world_y=point[0]+16*x,point[1]-16*y
            elif placement in ('Camera','CameraAspect'):
                if camera is None:raise ValueError('Screen decoration requires a camera center')
                camera_height=self.camera_view_height or px.shape[0]
                unit_x=(camera_height if placement=='CameraAspect' else px.shape[1])/20
                dx=(x+obj['pivot'][0])*unit_x
                dy=-(y+obj['pivot'][1])*camera_height/20
                world_x=camera[0]+dx*camera_co+dy*camera_si
                world_y=camera[1]-dx*camera_si+dy*camera_co
            elif any(obj['parallax']):
                if camera is None:
                    raise ValueError('Parallax decorations require the authored camera center')
                world_x += (camera[0]-world_x)*obj['parallax'][0]/100+24*parallax_x
                world_y += (camera[1]-world_y)*obj['parallax'][1]/100-24*parallax_y
            local_pivot=self.local_pivots and placement not in ('Camera','CameraAspect')
            if local_pivot:
                # scrDecoration.SetPosition offsets the child sprite, then
                # pivotTrans applies scale and rotation to that offset.
                # The four-orb chart uses +/-4 tile units at 12% scale.
                pivot_x=24*obj['pivot'][0]*sx/100
                pivot_y=24*obj['pivot'][1]*sy/100
                world_x+=co*pivot_x-si*pivot_y
                world_y-=si*pivot_x+co*pivot_y
            hw,hh = abs(rgba.shape[1]*.0008*sx),abs(rgba.shape[0]*.0008*sy)
            pivot_extent=0 if local_pivot else 24*sum(map(abs,obj['pivot']))
            extent_x = abs(co)*hw+abs(si)*hh+pivot_extent
            extent_y = abs(si)*hw+abs(co)*hh+pivot_extent
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
            offset_x=0 if local_pivot else 24*obj['pivot'][0]
            offset_y=0 if local_pivot else 24*obj['pivot'][1]
            u = (dx*co-dy*si-offset_x)/(.0016*sx)+rgba.shape[1]/2
            v = (dx*si+dy*co+offset_y)/(.0016*sy)+rgba.shape[0]/2
            mask = (u >= 0) & (v >= 0) & (u < rgba.shape[1]) & (v < rgba.shape[0])
            yy, xx = yy[mask], xx[mask]
            uu=(u[mask]*obj['tile'][0])%rgba.shape[1]
            vv=(v[mask]*obj['tile'][1])%rgba.shape[0]
            sample = rgba[vv.astype(int), uu.astype(int)].copy()
            alpha=np.clip(sample[:,3].astype(float)/255*opacity/100,0,1)
            if self.protect_gameplay and not obj['gameplay_floor'] and obj['masking']!='Mask':
                # Optional foreground textures must not repaint track pixels
                # or mix extra colors into the exact gameplay tile atlas.
                alpha[(native_mask|floor_mask|planet_mask)[yy,xx]]=0
            if obj['masking']=='Mask':
                coverage=np.zeros(px.shape,dtype=bool);coverage[yy,xx]=alpha>0
                masks.append((obj['mask_depths'],coverage))
                continue
            if obj['masking'] in ('VisibleInsideMask','VisibleOutsideMask'):
                coverage=np.zeros(px.shape,dtype=bool)
                for depths,part in masks:
                    if depths[0]<=obj['depth']<=depths[1]:coverage|=part
                allowed=coverage[yy,xx]
                if obj['masking']=='VisibleOutsideMask':allowed=~allowed
                alpha*=allowed
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
            if obj['gameplay_planet']:
                planet_mask[yy,xx]=True
                floor_rgb[yy,xx]=sample[:,:3]
        if not restored:restore_native()
        mask = layer[:, :, 3] >= 128
        if not mask.any():
            return image
        # Covered source pixels will be replaced below. Reserving their
        # palette slots can exhaust the palette even though those colors
        # never reach the final image (Flow's foreground pattern cards).
        retained=image.copy()
        retained[top+1:top+1+px.shape[0]][mask]=0
        used = set(retained.ravel())
        # A long animated track can use all 96 numeric source indices for
        # a handful of identical RGB555 colors. Coalesce those aliases,
        # preserving opacity and every native pixel, before allocating art.
        canonical={};translation=np.arange(256,dtype=np.uint8)
        for index in sorted(used-{0}):
            translation[index]=canonical.setdefault(int(palette[index]),index)
        image=translation[image];retained=translation[retained]
        used=set(retained.ravel())
        available = [i for i in range(32, 128) if i not in used]
        # One shared SNES palette for custom art; native track pixels are intact.
        protected=(floor_mask&~native_mask if self.background_only else np.zeros(px.shape,dtype=bool))|planet_mask
        floor_words=np.array([],dtype=np.uint16)
        floor_inverse=np.array([],dtype=np.intp)
        if protected.any():
            rgb=floor_rgb[protected].astype(np.uint16)>>3
            floor_words,floor_inverse=np.unique(rgb[:,0]|(rgb[:,1]<<5)|(rgb[:,2]<<10),return_inverse=True)
        count=12
        colors = Image.fromarray(layer[:, :, :3]).quantize(colors=count, method=Image.Quantize.FASTOCTREE)
        indices = np.asarray(colors)
        rgb = np.array(colors.getpalette(), dtype=np.uint16).reshape(-1, 3)[:count] >> 3
        words = rgb[:, 0] | (rgb[:, 1] << 5) | (rgb[:, 2] << 10)
        # Art often uses colors already present in the track. Share those
        # exact RGB555 values before allocating a new slot; unused quantizer
        # swatches do not consume slots. Native pixels remain untouched.
        by_color={int(palette[i]):i for i in sorted(used,reverse=True) if i}
        free=iter(available)
        def allocate(word):
            word=int(word)
            if word not in by_color:
                slot=next(free,None)
                if slot is None:raise ValueError(('Decoration colors exceed source palette',frame,len(by_color)))
                by_color[word]=slot;palette[slot]=word
            return by_color[word]
        slots=np.zeros(count,dtype=np.uint8)
        for index in np.unique(indices[mask]):slots[index]=allocate(words[index])
        image[top+1:top+1+px.shape[0]][mask] = slots[indices[mask]]
        if protected.any():
            floor_slots=np.array([allocate(word) for word in floor_words],dtype=np.uint8)
            image[top+1:top+1+px.shape[0]][protected]=floor_slots[floor_inverse]
        return image
