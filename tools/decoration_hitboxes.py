"""Compile the standard-route Workshop maze hitboxes at full frame rate.

Positions are relative to the free-roam root. Visuals and collision use the
same sampled transforms; the cartridge never evaluates decoration tweens.
"""
import base64
import math
import struct
import zlib
from pathlib import Path

from make_assets import FPS
from track_motion import easing, enabled


def standard_route_decoration(data, dec):
    tags = set(dec.get('tag', '').split())
    if ('pp' in tags and not ('mine' in tags and data.get('id')==75)) or 'coincheck' in tags:
        return False
    # The Featured revision retains the old rotating bar as an unused
    # decoration. It belongs to the original Community maze, not this route.
    if data.get('id') == 75 and 'redspinny' in tags:
        return False
    return True


def visual_maze_decorations(data):
    """Keep original PNG hazards that are not represented by collision overlays."""
    selected = []
    for dec in data.get('featured_decorations', []):
        tags = set(dec.get('tag', '').split())
        if not standard_route_decoration(data, dec):
            continue
        if dec.get('decorationImage') not in ('gearmltemp.png', 'pulsebar.png'):
            continue
        if data.get('id') in (75, 251):
            # The free-roam objects already share visuals with collision.
            include = 'minePt2' in tags
        else:
            include = False
        if include:
            selected.append(dec)
    return dict(data, featured_decorations=selected)


def compile_region(data, chart, region):
    if not data.get('featured_decorations'):
        return
    from PIL import Image
    floor = region['step']
    root = chart['notes'][floor]
    actions = data.get('featured_actions', [])
    all_regions = data.get('decoration_hitboxes_all_regions', False)
    if all_regions:
        from track_motion import motion_schedule
        motion_schedule(data, chart)
    objects = []
    for dec in data['featured_decorations']:
        tags = set(dec.get('tag', '').split())
        kills = dec.get('hitbox') == 'Kill' or (
            'hitbox' not in dec and enabled(dec.get('failHitbox', False)))
        if not kills or (not all_regions and dec['floor'] != floor - 1):
            continue
        # These are the optional all-perfect secret route and its failure
        # screen, not obstacles on the normal maze route.
        if not standard_route_decoration(data, dec):
            continue
        if dec.get('relativeTo') != 'Tile' or dec.get('failHitboxType', 'Box') != 'Box':
            raise ValueError(('Unsupported maze hitbox', dec))
        if any(dec.get('failHitboxOffset', (0, 0))) or dec.get('failHitboxRotation', 0):
            raise ValueError(('Unsupported independent hitbox transform', dec))
        image = Image.open(Path(data['source']).parent / dec['decorationImage']).convert('RGBA')
        base = chart['notes'][dec['floor']]
        origin = [base['x'] - root['x'] + 24 * dec['position'][0],
                  base['y'] - root['y'] - 24 * dec['position'][1]]
        if all_regions:
            origin = [v+b-r for v,b,r in zip(origin,base['position_track_offset'],root['position_track_offset'])]
        initial = [0., 0., 0., *dec.get('scale', (100, 100)), dec.get('opacity', 100)]
        commands = [[] for _ in initial]
        for event in actions:
            if event['eventType'] != 'MoveDecorations' or not enabled(event.get('active', True)):
                continue
            if not tags.intersection(event.get('tag', '').split()):
                continue
            # Conditional secret-route relocations must not run unconditionally.
            allowed=('minecolor','stcheck') if 'pp' in tags else ('minecolor',)
            if event.get('eventTag') and event['eventTag'] not in allowed:
                continue
            note = chart['notes'][event['floor']]
            beat = 60 / data['bpm'] / note['speed'] * FPS
            start = note['time'] * FPS + event.get('angleOffset', 0) / 180 * beat
            duration = event.get('duration', 0) * beat
            for key, axes in (('positionOffset', (0, 1)), ('rotationOffset', (2,)),
                              ('scale', (3, 4)), ('opacity', (5,))):
                if key not in event:
                    continue
                values = event[key] if len(axes) == 2 else [event[key]]
                for axis, value in zip(axes, values):
                    if value is not None:
                        commands[axis].append((start, duration, value, event.get('ease', 'Linear')))
        for row in commands:
            row.sort(key=lambda e: e[0])
        def sample(axis, frame):
            value = initial[axis]
            due = [e for e in commands[axis] if e[0] <= frame]
            for index, (start, duration, target, ease) in enumerate(due):
                # Native replacement tweens complete the previous tween.
                if index == len(due)-1 and duration and frame < start + duration:
                    value += (target - value) * easing(ease, (frame - start) / duration)
                    break
                value = target
            return value
        frames = []
        hit_scale = dec.get('failHitboxScale', (100, 100))
        end = region.get('end', region['return_start'])
        for frame in range(region['start'], end):
            x, y, rotation, sx, sy, opacity = [sample(a, frame) for a in range(6)]
            angle = -math.radians(dec.get('rotation', 0) + rotation)
            # Custom sprites use 100 pixels per Unity unit; tiles are 1.5 units.
            width, height = [abs(v * s / 100 * .16) for v, s in zip(image.size, (sx, sy))]
            frames.append([round(origin[0] + x * 24), round(origin[1] - y * 24),
                           round(math.cos(angle) * 256), round(math.sin(angle) * 256),
                           round(width * hit_scale[0] / 200), round(height * hit_scale[1] / 200),
                           width / 2, height / 2, max(0, min(100, opacity))])
        if all_regions:
            left,top,right,bottom=region['bounds']
            # Keep hazards reachable by either planet, including its orbit.
            # Other regions' objects retain their world positions and must
            # not become duplicate local obstacles in this grid.
            if not any(left-30-max(f[4:6]) <= f[0] <= right+30+max(f[4:6]) and
                       top-30-max(f[4:6]) <= f[1] <= bottom+30+max(f[4:6]) for f in frames):
                continue
        objects.append(dict(tag=dec['tag'], perfect_only='pp' in tags, start=region['start'], end=end,
                            size=list(image.size), alpha=base64.b64encode(zlib.compress(image.getchannel('A').tobytes())).decode(),
                            frames=frames))
    if objects:
        region['decoration_hitboxes'] = objects


def table_source(charts):
    ranges = []; records = []; conditions=[]; tracks = []; geometry = bytearray(); shared = {}
    for chart in charts:
        for region in chart.get('freeroam_regions', []):
            objects = region.get('decoration_hitboxes', [])
            ranges.append((len(records) * 6, len(objects)))
            for obj in objects:
                record = []
                for field in (0, 2, 4):
                    samples = [tuple(f[field:field+2]) for f in obj['frames']]
                    first, last = 0, len(samples)-1
                    while first < last and samples[first] == samples[first+1]:
                        first += 1
                    while last > first and samples[last] == samples[last-1]:
                        last -= 1
                    start, end = obj['start']+first, obj['start']+last
                    if first == last:
                        start = end = 0
                    blob = b''.join(struct.pack('<2h', *s) for s in samples[first:last+1])
                    key = (start, end, blob)
                    if key not in shared:
                        shared[key] = len(tracks)*8
                        offset = len(geometry)
                        tracks.append((start, end, offset & 65535, offset >> 16))
                        geometry.extend(blob)
                    record.append(shared[key])
                records.append(record)
                conditions.append(int(obj.get('perfect_only',False)))
    lines = ['neo_deco_ranges:'] + ['.word ' + ','.join(map(str, r)) for r in ranges]
    lines += ['neo_deco_records:'] + ['.word ' + ','.join(map(str, r)) for r in records]
    lines += ['neo_deco_conditions:'] + ['.word '+str(v)+',0,0' for v in conditions]
    lines += ['neo_deco_tracks:'] + ['.word ' + ','.join(map(str, r)) for r in tracks]
    lines += ['neo_deco_geometry:'] + ['.byte ' + ','.join(map(str, geometry[i:i+32])) for i in range(0, len(geometry), 32)]
    return '\n'.join(lines) + '\n'


class Overlay:
    def __init__(self, chart):
        import numpy as np
        self.objects = []
        for region in chart.get('freeroam_regions', []):
            root = chart['notes'][region['step']]
            for obj in region.get('decoration_hitboxes', []):
                if obj.get('perfect_only'):continue  # Runtime sprites follow the run's actual judgments.
                mask = np.frombuffer(zlib.decompress(base64.b64decode(obj['alpha'])), dtype=np.uint8).reshape(obj['size'][1], obj['size'][0])
                self.objects.append((root, obj, mask))

    def draw(self, image, frame, px, py, top, palette):
        import numpy as np
        active = [(root, obj, mask) for root, obj, mask in self.objects if obj['start'] <= frame < obj['end']]
        if not active:
            return image
        # Allocate from unused source indices, never overwrite a track color.
        used = set(image.ravel())
        unused = [i for i in range(32, 128) if i not in used]
        assert len(unused) >= 2, 'Maze hazard palette capacity'
        red, light = unused[-2:]
        palette[red], palette[light] = 31 | (3 << 5), 31 | (14 << 5) | (12 << 10)
        dest = image[top+1:top+1+px.shape[0]]
        left,right,top_y,bottom_y=px.min(),px.max(),py.min(),py.max()
        for root, obj, mask in active:
            x, y, co, si, _, _, hw, hh, opacity = obj['frames'][frame-obj['start']]
            if hw < .01 or hh < .01 or opacity <= 0:
                continue
            # Authored collision-only boxes are often parked far from the
            # maze. Reject their conservative rotated bounds before making
            # full viewport arrays; this cannot remove an on-screen pixel.
            cx,cy=root['x']+x,root['y']+y
            ex,ey=(abs(co)*hw+abs(si)*hh)/256,(abs(si)*hw+abs(co)*hh)/256
            if cx+ex<left or cx-ex>right or cy+ey<top_y or cy-ey>bottom_y:
                continue
            dx, dy = px-root['x']-x, py-root['y']-y
            lx, ly = (dx*co+dy*si)/256, (-dx*si+dy*co)/256
            inside = (abs(lx) <= hw) & (abs(ly) <= hh)
            yy, xx = np.nonzero(inside)
            u = np.clip(((lx[inside]/hw+1)*.5*mask.shape[1]).astype(int), 0, mask.shape[1]-1)
            v = np.clip(((ly[inside]/hh+1)*.5*mask.shape[0]).astype(int), 0, mask.shape[0]-1)
            visible = mask[v, u].astype(float)*opacity/100 >= 128
            yy, xx = yy[visible], xx[visible]
            dest[yy, xx] = red
            edge = (abs(lx[yy, xx]) > hw-1) | (abs(ly[yy, xx]) > hh-1)
            dest[yy[edge], xx[edge]] = light
        return image


def demo_route(region, note):
    """Find a timed controller route through the real hazards, not immunity.

    Both pivot and orbit must be safe throughout a wait, including frames
    between taps. A small extra margin tolerates integer orbit rounding.
    """
    import heapq
    import numpy as np
    start, end = region['start'], region['return_start']
    geometry = np.array([o['frames'] for o in region['decoration_hitboxes']])
    cells = set(map(tuple, region['cells']))
    twirls = set(map(tuple, region.get('twirls', [])))
    rate = abs(note['rate']/256)
    initial_sign = 1 if note['rate'] > 0 else -1
    def safe(x, y, time, angle, sign, until):
        times = np.arange(time, min(until+1, end))
        h = geometry[:, times-start, :6]
        angles = (angle+(times-time)*rate*sign)*math.pi/128
        planets=[(x,y),(x+np.round(24*np.cos(angles)),y+np.round(24*np.sin(angles)))]
        if note.get('planets',2)==3:
            third=angles-sign*43*math.pi/128
            planets.append((x+np.round(24*np.cos(third)),y+np.round(24*np.sin(third))))
        for px, py in planets:
            dx, dy = px-h[:,:,0], py-h[:,:,1]
            co, si = h[:,:,2]/256, h[:,:,3]/256
            u = np.maximum(0, abs(np.round(dx*co+dy*si))-h[:,:,4])
            v = np.maximum(0, abs(np.round(-dx*si+dy*co))-h[:,:,5])
            if ((u*u+v*v <= 36) & (h[:,:,4] > 0) & (h[:,:,5] > 0)).any():
                return False
        return True
    queue = [(start, *region['entry'], note['angle'], initial_sign, [])]
    seen = set()
    goal = tuple(region['goal'])
    while queue:
        time, x, y, angle, sign, path = heapq.heappop(queue)
        key = (time, x, y, angle, sign)
        if key in seen:
            continue
        seen.add(key)
        if len(seen) > 100000:
            raise ValueError('Maze controller route exceeds search budget')
        # FreeRoam returns from any occupied cell. The far side is a demo
        # destination, not an extra chart objective or compulsory corner.
        reached=(abs(x-goal[0])+abs(y-goal[1]) <= region['demo_goal_radius']) if 'demo_goal_radius' in region else x >= goal[0]-24
        if reached and safe(x,y,time,angle,sign,end):
            return path
        for dx, dy, direction in ((24,0,0),(0,-24,192),(-24,0,128),(0,24,64)):
            point = (x+dx,y+dy)
            if point not in cells:
                continue
            turn = ((direction-angle)*sign)%256
            if turn < 16:
                turn += 256
            for extra in range(2):
                at = round(time+(turn+extra*256)/rate)
                if at >= end or not safe(x,y,time,angle,sign,at):
                    continue
                next_sign = -sign if point in twirls else sign
                next_angle=((direction^128)+(43*next_sign if note.get('planets',2)==3 else 0))%256
                if safe(*point,at,next_angle,next_sign,at):
                    heapq.heappush(queue,(at,*point,next_angle,next_sign,path+[[at,*point,next_angle]]))
    raise ValueError('No collision-free controller route through authored maze')


def palette_events(folder, level):
    import numpy as np
    from projected_tracks import Source
    source = Source(folder, level)
    runtime = source.palette.copy()
    result = []
    frames = sorted({frame for _,obj,_ in source.hazards.objects for frame in range(obj['start'],obj['end']+1)})
    previous = None
    for frame in frames:
        source.advance(frame)
        if previous is None or frame > previous+1:
            runtime[:] = source.palette
        for index, value in source.color_events.get(frame, []):
            runtime[index] = value
        source.screen(frame)
        for index in np.flatnonzero(runtime[32:128] != source.palette[32:128])+32:
            result.append((frame, 7, int(index)-32, int(source.palette[index]), b''))
        runtime[:] = source.palette
        previous = frame
    return result
