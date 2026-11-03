"""Native track pieces, including detached midspin and full-turn caps."""
import math
import json
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw


STYLE=json.loads((Path(__file__).resolve().parents[1]/"assets/graphics/track-shapes.json").read_text())

def piece(notes,i,line_width=None,rotation=0):
    if line_width is None:line_width=STYLE["line_width"]
    p=np.array((notes[i]['x'],notes[i]['y']),dtype=float)
    prev=np.array((notes[max(0,i-1)]['x'],notes[max(0,i-1)]['y']),dtype=float)
    nxt=np.array((notes[min(len(notes)-1,i+1)]['x'],notes[min(len(notes)-1,i+1)]['y']),dtype=float)
    def direction(note,delta):
        if 'exit_angle' in note:
            a=note['exit_angle'];return np.array((math.cos(a),math.sin(a)))
        return delta/np.linalg.norm(delta)
    incoming=direction(notes[i-1],p-prev) if i else direction(notes[i],nxt-p)
    outgoing=direction(notes[i],nxt-p) if i+1<len(notes) else incoming
    if rotation:
        a=-math.radians(rotation);c,s=math.cos(a),math.sin(a)
        matrix=np.array(((c,-s),(s,c)))
        incoming=matrix@incoming;outgoing=matrix@outgoing
    kind=notes[i].get('spin_kind','normal')
    if kind!='normal' and i:
        normal=np.array((-incoming[1],incoming[0]))
        local=STYLE['midspin_polygon' if kind=='midspin' else 'full_turn_polygon']
        path=[tuple((p+np.round(incoming*x+normal*y)).astype(int)) for x,y in local]
    else:
        # Rasterize identical authored angles to identical local shapes. World
        # position rounding must never stretch a tile or change its slope.
        path=[tuple((p+np.round(q)).astype(int)) for q in (-incoming*STYLE['half_segment'],np.zeros(2),outgoing*STYLE['half_segment'])]
    pad=STYLE['spin_padding'] if kind!='normal' and i else STYLE['normal_padding']
    x0=min(q[0] for q in path)-pad;y0=min(q[1] for q in path)-pad
    x1=max(q[0] for q in path)+pad+1;y1=max(q[1] for q in path)+pad+1
    image=Image.new('L',(x1-x0,y1-y0));draw=ImageDraw.Draw(image)
    points=[(x-x0,y-y0) for x,y in path]
    if kind!='normal' and i:draw.polygon(points,fill=255)
    else:draw.line(points,fill=255,width=line_width,joint='curve')
    return x0,y0,image
