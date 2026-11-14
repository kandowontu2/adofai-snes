"""Native track pieces, including detached midspin and full-turn caps."""
import math
import json
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageChops,ImageFilter


STYLE=json.loads((Path(__file__).resolve().parents[1]/"assets/graphics/track-shapes.json").read_text())


def recessed_join(size,coverage,center,angle,shared=False):
    direction=np.array((math.cos(angle),math.sin(angle)))
    normal=np.array((-direction[1],direction[0]))*7
    join=Image.new('L',size);draw=ImageDraw.Draw(join);center=np.array(center)
    for distance,value in (((11,3),) if shared else ((11,3),(12,4))):
        end=center+np.round(direction*distance)
        draw.line([tuple(np.round(end-normal).astype(int)),tuple(np.round(end+normal).astype(int))],fill=value,width=1)
    mask=ImageChops.multiply(coverage.filter(ImageFilter.MinFilter(3)) if shared else coverage,join.point(lambda p:255 if p else 0))
    return join,mask


def surface(notes,index,shared=False):
    """The same one-pixel contour and recessed join used by track rastering."""
    x,y,part=piece(notes,index);coverage=part.point(lambda p:255 if p else 0)
    pixels=Image.new('L',part.size);pixels.paste(1,mask=coverage)
    contour=ImageChops.subtract(coverage,coverage.filter(ImageFilter.MinFilter(3)))
    pixels.paste(3,mask=contour);n=notes[index]
    if n.get('gem_platform'):
        pixels.paste(3,mask=part.point(lambda p:255 if p==128 else 0))
    elif n.get('spin_kind','normal')=='normal' and n.get('hold_length',-1)<0 and n.get('exit_angle') is not None:
        join,mask=recessed_join(part.size,coverage,(n['x']-x,n['y']-y),n['exit_angle'],shared)
        pixels.paste(join,mask=mask)
    return x,y,pixels

def gem_piece(note,rotation,scale):
    """Two-tone faceted Gems platform; 128 marks its bright facets."""
    outer=np.array(STYLE['gem_platform_polygon'],dtype=float)
    inner=outer*STYLE['gem_platform_inset']
    a=-math.radians(rotation);c,s=math.cos(a),math.sin(a)
    matrix=np.array(((c,-s),(s,c)))
    outer=np.round((outer@matrix.T)*scale).astype(int)
    inner=np.round((inner@matrix.T)*scale).astype(int)
    if min(map(abs,scale))<1e-6:return note['x'],note['y'],Image.new('L',(1,1))
    low=outer.min(axis=0)-1;high=outer.max(axis=0)+2
    im=Image.new('L',tuple(high-low));d=ImageDraw.Draw(im)
    out=[tuple(p-low) for p in outer];inside=[tuple(p-low) for p in inner]
    d.polygon(out,fill=255)
    for i in STYLE['gem_platform_bright_facets']:
        j=(i+1)%len(out);d.polygon([out[i],out[j],inside[j],inside[i]],fill=128)
    d.polygon(inside,fill=128);d.line(out+[out[0]],fill=255,width=1)
    return note['x']+int(low[0]),note['y']+int(low[1]),im

def piece(notes,i,line_width=None,rotation=0,scale=(1.,1.),hold_tail=None):
    if notes[i].get('platform_hidden') or notes[i].get('scene_hidden'):
        return notes[i]['x'],notes[i]['y'],Image.new('L',(1,1))
    if notes[i].get('gem_platform'):
        return gem_piece(notes[i],rotation,scale)
    if notes[i].get('freeroam_grid'):
        from neo_freeroam import grid_piece
        return grid_piece(notes[i],notes[i]['freeroam_grid'])
    if notes[i].get('scene_visual'):
        v=notes[i]['scene_visual'];x,y=v['offset']
        return notes[i]['x']+x,notes[i]['y']+y,Image.frombytes('1',tuple(v['size']),bytes.fromhex(v['bits'])).convert('L')
    if notes[i].get('warp_visual'):
        markers=notes[i]['warp_visual']['markers']
        original=dict(notes[i]);original.pop('warp_visual')
        bx,by,base=piece(notes[:i]+[original]+notes[i+1:],i,line_width,rotation,scale,hold_tail)
        bx-=notes[i]['x'];by-=notes[i]['y']
        points=[(bx,by),(bx+base.width,by+base.height)]
        for v in markers:
            cx,cy=v['center'];points+=v['link']+[(cx-12,cy-12),(cx+12,cy+12)]
        x0=min(x for x,y in points)-2;y0=min(y for x,y in points)-2
        im=Image.new('L',(max(x for x,y in points)-x0+3,max(y for x,y in points)-y0+3));d=ImageDraw.Draw(im)
        im.paste(base,(bx-x0,by-y0))
        for v in markers:
            cx,cy=v['center'];link=v['link']
            if link:d.line([(x-x0,y-y0) for x,y in link],fill=255,width=1)
            d.rectangle((cx-11-x0,cy-11-y0,cx+11-x0,cy+11-y0),outline=255,width=2)
            d.rectangle((cx-8-x0,cy-8-y0,cx+8-x0,cy+8-y0),fill=255)
        return notes[i]['x']+x0,notes[i]['y']+y0,im
    if line_width is None:line_width=STYLE["line_width"]
    p=np.array((notes[i]['x'],notes[i]['y']),dtype=float)
    prev=np.array((notes[max(0,i-1)]['x'],notes[max(0,i-1)]['y']),dtype=float)
    nxt=np.array((notes[min(len(notes)-1,i+1)]['x'],notes[min(len(notes)-1,i+1)]['y']),dtype=float)
    def direction(note,delta):
        if 'exit_angle' in note:
            a=note['exit_angle'];return np.array((math.cos(a),math.sin(a)))
        return delta/np.linalg.norm(delta)
    incoming=(-np.array((math.cos(notes[i]['entry_angle']),math.sin(notes[i]['entry_angle'])))
              if 'entry_angle' in notes[i] else direction(notes[i-1],p-prev) if i else direction(notes[i],nxt-p))
    outgoing=direction(notes[i],nxt-p) if i+1<len(notes) else incoming
    if 'platform_angle' in notes[i]:
        a=notes[i]['platform_angle'];incoming=outgoing=np.array((math.cos(a),math.sin(a)))
    hold_end=nxt-outgoing*24
    if rotation:
        a=-math.radians(rotation);c,s=math.cos(a),math.sin(a)
        matrix=np.array(((c,-s),(s,c)))
        incoming=matrix@incoming;outgoing=matrix@outgoing
        hold_end=p+matrix@(hold_end-p)
    if hold_tail is not None:
        # The tail is an independent moving floor. Keep the line attached
        # even when the hold's own visual rotation/scale changes.
        tail=np.array(hold_tail,dtype=float)
        for axis,factor in enumerate(scale):
            if abs(factor)>1e-6:tail[axis]=p[axis]+(tail[axis]-p[axis])/factor
        hold_end=tail-outgoing*24
    kind=notes[i].get('spin_kind','normal')
    hold=notes[i].get('hold_length',-1)>=0 and i+1<len(notes)
    polygon=False
    if hold:
        # scrHoldRenderer traces the orbit as its pivot travels to the tail.
        # A wide straight ribbon conceals the turns and resembles extra floors.
        from hold_path import sweep
        entry=notes[i].get('angle',0)*math.pi/128-math.radians(rotation)
        arc=sweep(notes[i])
        samples=max(16,math.ceil(abs(arc)*16))
        path=[tuple(p.astype(int))]+[tuple(np.round(p+(hold_end-p)*t+24*np.array((math.cos(entry+arc*t),math.sin(entry+arc*t)))).astype(int)) for t in np.linspace(0,1,samples+1)]
        cap=[tuple(np.round(p+q).astype(int)) for q in (-incoming*STYLE['half_segment'],np.zeros(2),outgoing*STYLE['half_segment'])]
    elif kind!='normal' and i:
        normal=np.array((-incoming[1],incoming[0]))
        local=STYLE['midspin_polygon' if kind=='midspin' else 'full_turn_polygon']
        path=[tuple((p+np.round(incoming*x+normal*y)).astype(int)) for x,y in local]
    else:
        # Rasterize identical authored angles to identical local shapes. World
        # position rounding must never stretch a tile or change its slope.
        path=[tuple((p+np.round(q)).astype(int)) for q in (-incoming*STYLE['half_segment'],np.zeros(2),outgoing*STYLE['half_segment'])]
        # FloorMesh uses intersecting straight edges for wide interior
        # angles (>=120 degrees). A round polyline joint removes the corner
        # pointing toward a diagonal midspin and obscures its connection.
        dot=float(np.dot(incoming,outgoing))
        if dot>=.5-1e-6 and dot<1-1e-6:
            ni=np.array((-incoming[1],incoming[0]))*(line_width-1)/2
            no=np.array((-outgoing[1],outgoing[0]))*(line_width-1)/2
            join=(ni+no)/(1+dot)
            a=-incoming*STYLE['half_segment'];b=outgoing*STYLE['half_segment']
            path=[tuple((p+np.round(q)).astype(int)) for q in (a+ni,join,b+no,b-no,-join,a-ni)]
            polygon=True
    pad=STYLE['spin_padding'] if kind!='normal' and i else STYLE['normal_padding']
    bounds=path+cap if hold else path
    x0=min(q[0] for q in bounds)-pad;y0=min(q[1] for q in bounds)-pad
    x1=max(q[0] for q in bounds)+pad+1;y1=max(q[1] for q in bounds)+pad+1
    image=Image.new('L',(x1-x0,y1-y0));draw=ImageDraw.Draw(image)
    points=[(x-x0,y-y0) for x,y in path]
    if hold:
        draw.line(points,fill=255,width=2,joint='curve')
        draw.line([(x-x0,y-y0) for x,y in cap],fill=255,width=line_width,joint='curve')
    elif polygon or kind!='normal' and i:draw.polygon(points,fill=255)
    else:draw.line(points,fill=255,width=line_width,joint='curve')
    if scale!=(1.,1.):
        sx,sy=scale
        if abs(sx)<1e-6 or abs(sy)<1e-6:return int(p[0]),int(p[1]),Image.new('L',(1,1))
        left,right=sorted(p[0]+(v-p[0])*sx for v in (x0,x1))
        top,bottom=sorted(p[1]+(v-p[1])*sy for v in (y0,y1))
        left,top=math.floor(left),math.floor(top)
        size=(max(1,math.ceil(right)-left),max(1,math.ceil(bottom)-top))
        image=image.transform(size,Image.Transform.AFFINE,(1/sx,0,(left-p[0])/sx+p[0]-x0,0,1/sy,(top-p[1])/sy+p[1]-y0),Image.Resampling.NEAREST)
        x0,y0=left,top
    return x0,y0,image
