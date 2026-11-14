"""Native rectangular free-roam regions (generated cells are not chart notes).

Coordinates are relative to the region's root, so later map-origin shifts do
not detach the grid. Return timing follows scrController.UpdateFreeroam.
"""
import math
from collections import deque
from make_assets import FPS


def compile_regions(data, chart):
    regions = []
    for i, floor in enumerate(data['floors'][:-1]):
        if not floor.get('freeroam'):
            continue
        if data.get('freeroam_angle_interval', 90) != 90 or data.get('freeroam_angle_offset', 0) != 0:
            raise ValueError('Unsupported non-cardinal free-roam grid')
        cells = [c for c in data['freeroam_cells'] if c['freeroamRegion'] == floor['freeroamRegion']]
        if any(c.get('unstable') for c in cells):
            raise ValueError('Unsupported unstable free-roam cell')
        root = data['native_positions'][i]
        scale = 24 / data.get('native_tile_size', 1.5)
        # Disabled cells are parked far offscreen in the Unity scene. Their
        # serialized world positions must not expand the map by 100,000 units.
        points = sorted({(round((c['freeroamPosition']['x']+floor['freeroamOffset']['x'])*24),
                          round(-(c['freeroamPosition']['y']+floor['freeroamOffset']['y'])*24)) for c in cells})
        landable = sorted({(round((c['position'][0]-root[0])*scale),
                            round(-(c['position'][1]-root[1])*scale)) for c in cells if c.get('isLandable')})
        xs = sorted({p[0] for p in points}); ys = sorted({p[1] for p in points})
        entry=tuple(floor.get('freeroamEntry',(0,0)))
        assert len(points) == len(xs)*len(ys) and entry in landable,('Free-roam entry is not landable',i,entry)
        assert all(b-a == 24 for a,b in zip(xs,xs[1:])) and all(b-a == 24 for a,b in zip(ys,ys[1:]))
        beat = 60/data['bpm']/floor['speed']*FPS
        end = chart['notes'][i+1]['frame']
        early = floor['freeroamEndEarlyBeats']
        begin = round(end-beat*early)
        unlock = round(end-.8*beat) if .8*beat/FPS >= .05 else begin
        angle = floor['exitangle']-math.pi/2
        regions.append(dict(step=i, start=chart['notes'][i]['frame'], return_start=begin,
                            return_duration=max(1, round(beat*early*.5)), unlock=unlock, end=end,
                            fade_duration=max(1, round(60/data['bpm']*FPS)),
                            ease=floor['freeroamEndEase'], move_camera=bool(floor['moveCamAtFreeroamEnd']),
                            bounds=[xs[0],ys[0],xs[-1],ys[-1]], cells=landable,entry=list(entry),
                            twirls=[[round((c['position'][0]-root[0])*scale),round(-(c['position'][1]-root[1])*scale)] for c in cells if c.get('isLandable') and c.get('isSwirl')],
                            exit_offset=[round(-24*math.cos(angle)),round(-24*math.sin(angle))]))
    chart['freeroam_regions'] = regions
    chart['neo_freeroam_runtime'] = 1
    entities=data.get('native_chapter_entities',[])
    for r in regions:
        r['coins']=[];r['hazards']=[]
        n=chart['notes'][r['step']]
        beat=60/data['bpm']/n['speed']*FPS
        if data['id'] in (68,73):
            chapter=next((e for e in entities if e['type']=='Mawaru'),None)
            if chapter:
                ids={p['m_PathID'] for p in chapter['data']['collect_coins']}
                root=data['native_positions'][r['step']];scale=24/data['native_tile_size']
                r['coins']=[[round((e['position'][0]-root[0])*scale),round(-(e['position'][1]-root[1])*scale)] for e in entities if e['path_id'] in ids]
                r['coin_check']=round(r['start']+29.9*beat)
        elif data['id']==70:
            index=data['floors'][r['step']]['freeroamRegion']
            if index==8:r['goal']=[552,0]
            lists=[[0,1,4,5],list(range(8,16)),[0,1,2,3,4,5,8,9,12,13],
                   [0,3,4,7,8,9,10,11,12,13,14,15]]
            specs=[(0,7.5,lists[index])] if index<4 else [(0,7,[i for i in range(32) if i%4<2]),(7,14,[i for i in range(32) if i%4>=2])] if index==4 else []
            offset=data['floors'][r['step']]['freeroamOffset']
            for warn,check,indices in specs:
                r['hazards'].append(dict(warn=round(r['start']+warn*beat),check=round(r['start']+check*beat),
                    end=round(r['start']+(check+1)*beat),
                    cells=[[round((i%4+offset['x'])*24),round(-(i//4+offset['y'])*24)] for i in indices]))
        if data['id']==70:
            compile_laser(data,r,beat)
        if data.get('featured_classic') and r.get('twirls'):
            # Autoplay traverses the reachable maze. Isolated decorative
            # edge cells must not become invented mandatory objectives.
            cells=set(r['cells']);seen={tuple(r['entry'])};queue=deque(seen)
            while queue:
                x,y=queue.popleft()
                for p in ((x+24,y),(x,y-24),(x-24,y),(x,y+24)):
                    if p in cells and p not in seen:seen.add(p);queue.append(p)
            r['goal']=list(max(seen,key=lambda p:(p[0],p[1])))
        r['demo_route']=demo_route(r,n)


def compile_laser(data, region, beat):
    """Chapter laser colliders, transformed from the authored scene geometry."""
    from track_motion import easing
    specs={97:(17202,15,[(0,8,0,3,5),(8,7,0,6,1)]),
           150:(18190,12,[(0,6,3,0,5),(6,6,5,0,1)]),
           151:(18212,12,[(0,6,3,0,5),(6,6,6.5,0,1)]),
           152:(18205,12,[(0,7,3,0,5),(7,5,6.5,0,1)]),
           405:(18186,62,[(0,12,2,0,5),(12,50,34,0,1)])}
    if region['step'] not in specs:return
    ident,duration,moves=specs[region['step']]
    entity=next(e for e in data['native_chapter_entities'] if e['path_id']==ident)
    m=entity['matrix'];parent=entity['parent_matrix'];c=entity['collider']
    root=data['native_positions'][region['step']];scale=24/data['native_tile_size']
    corners=[]
    for sx in (-.5,.5):
        for sy in (-.5,.5):
            x=c['m_Offset']['x']+sx*c['m_Size']['x'];y=c['m_Offset']['y']+sy*c['m_Size']['y']
            corners.append(((m[0][0]*x+m[0][1]*y+m[0][3]-root[0])*scale,
                            -(m[1][0]*x+m[1][1]*y+m[1][3]-root[1])*scale))
    left=min(x for x,y in corners);right=max(x for x,y in corners)
    top=min(y for x,y in corners);bottom=max(y for x,y in corners)
    start=region['start'];end=min(region['return_start'],round(start+duration*beat))
    rectangles=[]
    for frame in range(start,end):
        t=(frame-start)/beat;dx=dy=0
        for at,length,x,y,ease in moves:
            v=easing(ease,max(0,min(1,(t-at)/length)))
            dx+=(parent[0][0]*x+parent[0][1]*y)*scale*v
            dy-=(parent[1][0]*x+parent[1][1]*y)*scale*v
        rectangles.append([round(left+dx),round(top+dy),round(right+dx),round(bottom+dy)])
    region['laser']=dict(start=start,end=end,rectangles=rectangles,axis=1 if right-left>bottom-top else 0)
    region['cell_deaths']=[next((start+i for i,(l,t,r,b) in enumerate(rectangles) if l-3<=x<=r+3 and t-3<=y<=b+3),65535) for x,y in region['cells']]
    if region['step'] in (150,151,152):
        region['goal']=list(max((tuple(p) for p in region['cells']),key=lambda p:(p[0],-abs(p[1]))))


def demo_route(region,note,reverse=False):
    """A legal controller route for autoplay and independent manual replays."""
    cells={tuple(p) for p in region['cells']}
    goals=[(round(x/24)*24,round(y/24)*24) for x,y in region.get('coins',[])]
    goals=[p for p in goals if p in cells][:3]
    if region.get('goal'):goals=[tuple(region['goal'])]
    if reverse:goals.reverse()
    current=tuple(region.get('entry',(0,0)));angle=note['angle'];at=region['start'];result=[]
    rate=note['rate']/256;sign=1 if rate>0 else -1
    # For hazard-only regions, occupy a safe cell before each check.
    tasks=[(p,region['return_start']) for p in goals]
    if not tasks:
        for hazard_index,h in enumerate(region.get('hazards',[])):
            safe=cells-{tuple(p) for p in h['cells']}
            target=(48,-96) if hazard_index==0 else (24,-144) if region['step']==97 else None
            if region['step']!=97:target=min(safe,key=lambda p:abs(p[0]-current[0])+abs(p[1]-current[1]))
            tasks.append((target,h['check']))
    for target,deadline in tasks:
        queue=deque([(current,[])]);seen={current};path=None
        while queue:
            p,walk=queue.popleft()
            if p==target:path=walk;break
            for dx,dy,direction in ((24,0,0),(0,-24,192),(-24,0,128),(0,24,64)):
                q=(p[0]+dx,p[1]+dy)
                if q in cells and q not in seen:seen.add(q);queue.append((q,walk+[(q,direction)]))
        if path is None:raise ValueError('Unreachable free-roam objective')
        for p,direction in path:
            turn=((direction-angle)*sign)%256
            if turn<16:turn+=256
            at=round(at+turn/abs(rate))
            if at>=deadline:raise ValueError('Free-roam demo route misses objective deadline')
            result.append([at,*p,direction^128]);angle=direction^128;current=p
            if list(p) in region.get('twirls',[]):rate=-rate;sign=-sign
        if not goals:
            # Keep this safe position through the check before seeking the
            # next safe region (whose safe half may be the current hazard).
            at=max(at,deadline+2)
            angle=round(angle+(at-(result[-1][0] if result else region['start']))*rate)&255
    return result


def grid_piece(note, region):
    from PIL import Image, ImageDraw
    left, top, right, bottom = region['bounds']
    # Native free cells are isolated squares, not joined track ribbons.
    image = Image.new('L', (right-left+23, bottom-top+23))
    draw = ImageDraw.Draw(image)
    for index,(x,y) in enumerate(region['cells']):
        if region.get('render_frame',-1)>=region.get('cell_deaths',[65535]*len(region['cells']))[index]:continue
        draw.rectangle((x-left,y-top,x-left+22,y-top+22),fill=255)
    return note['x']+left-11,note['y']+top-11,image


def widen_views(chart, views, transforms):
    """Preload the union of possible player views, not one invented route."""
    regions = chart.get('freeroam_regions', [])
    if not regions:
        return
    frames = set(views)
    for r in regions:
        frames.update((max(0,r['start']-1), r['end']))
    old = sorted(views.items()); cursor=0
    for frame in sorted(frames):
        while cursor+1<len(old) and old[cursor+1][0]<=frame:cursor+=1
        x,y,w,h=old[cursor][1]
        for r in regions:
            if not r['start']-1<=frame<r['end']:continue
            n=chart['notes'][r['step']]; following=chart['notes'][r['step']+1]
            fx=following['x']+following.get('position_track_offset',(0,0))[0]
            fy=following['y']+following.get('position_track_offset',(0,0))[1]
            a,b,c,d=r['bounds']
            left=min(x*8,n['x']+a-160,fx-160)
            top=min(y*8,n['y']+b-120,fy-120)
            right=max((x+w)*8,n['x']+c+160,fx+160)
            bottom=max((y+h)*8,n['y']+d+120,fy+120)
            x=left//8;y=top//8;w=(right+7)//8-x;h=(bottom+7)//8-y
            transforms[frame]=(256,0,0,0) # union is already in world space
        views[frame]=(x,y,w,h)
