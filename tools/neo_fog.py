"""Mawaru's authored planet clouds and FogBegin/FogFadeOut beat sequence.

The private import retains the installed scene's smoke alpha masks. Clouds
are composited into projected track frames, so no per-frame CPU rasterizer
or additional OBJ load is needed on the cartridge.
"""
import base64
import bisect
import math
import zlib

import numpy as np
from PIL import Image

from make_assets import FPS
from track_motion import easing


def extract(objects, chapter):
    sprites=[];lookup={};groups=[]
    for key in ('fogp1','fogp2','fog_overlay'):
        group=[]
        pointers=chapter[key] if isinstance(chapter[key],list) else [chapter[key]]
        for pointer in pointers:
            obj=objects[pointer['m_PathID']];data=obj.read_typetree()
            go=objects[data['m_GameObject']['m_PathID']].read_typetree()
            renderer=next(objects[c['component']['m_PathID']] for c in go['m_Component']
                          if objects[c['component']['m_PathID']].type.name=='SpriteRenderer')
            sprite=renderer.read().m_Sprite.deref().read();mask=sprite.image.getchannel('A')
            identity=(tuple(mask.size),mask.tobytes(),sprite.m_PixelsToUnits)
            if identity not in lookup:
                lookup[identity]=len(sprites)
                sprites.append(dict(size=list(mask.size),ppunit=sprite.m_PixelsToUnits,
                    alpha=base64.b64encode(zlib.compress(mask.tobytes(),9)).decode()))
            group.append(lookup[identity])
        groups.append(group)
    return dict(version=1,sprites=sprites,groups=groups)


def strength(beat, ex=False):
    """Native DOMoveX sequence; the value controls cloud alpha and growth."""
    targets=((585,4,.8),(593,6,1.3),(599,2,.8),(601,2,1.3),(603,8,1.5)) if ex else (
             (585,4,.6),(593,5,1.1),(598,3,.6),(601,3,1.1),(604,8,1.2))
    value=0
    for start,duration,target in targets:
        if beat<start:break
        phase=max(0,min(1,(beat-start)/duration))
        value+= (target-value)*easing('OutCubic' if start==585 else 'InOutCubic',phase)
        if phase<1:break
    return value*max(0,min(1,(625-beat)/8))


class Fog:
    def __init__(self,chart):
        from neo_mawaru import clock
        self.chart=chart;self.beat=clock(chart);self.times=[n['frame'] for n in chart['notes']]
        self.data=chart['mawaru_fog'];self.cache={}
        from neo_visuals import chapter_time
        self.first=math.floor(chapter_time(chart,585)*FPS)
        self.last=math.ceil(chapter_time(chart,625)*FPS)
        self.sprites=[Image.frombytes('L',tuple(s['size']),zlib.decompress(base64.b64decode(s['alpha'])))
                      for s in self.data['sprites']]

    def mask(self,frame,camera,rotation):
        b=self.beat(frame)
        if not 585<b<625:return None
        amount=strength(b,self.chart['code']=='T3EX-X')
        if not amount:return None
        # Native FogUpdate rotates five clouds around each planet, in
        # opposite phases. Its scale and orbit radius use the same strength.
        chart=self.chart;i=max(0,bisect.bisect_right(self.times,frame)-1);n=chart['notes'][i]
        angle=(n['angle']+n['rate']/256*max(0,frame-n['frame']-n.get('pause',0)))*math.pi/128
        centers=[(n['x'],n['y']),(n['x']+24*math.cos(angle),n['y']+24*math.sin(angle))]
        if i%2:centers.reverse()
        c,s=rotation;inverse=256/(c*c+s*s);pc,ps=c*inverse,s*inverse
        zoom=math.hypot(pc,ps);unit=16
        result=Image.new('L',(256,184));clip=np.zeros((184,256),dtype=np.uint16)
        for orb,group in enumerate(self.data['groups'][:2]):
            x,y=centers[orb]
            for j,index in enumerate(group):
                phase=frame/FPS*6.28+j/len(group)*math.tau+orb*3.14
                dx=x+unit*(1+amount*.3)*math.sin(phase)-camera[0]-128
                dy=y-unit*(1+amount*.3)*math.cos(phase)-camera[1]-chart.get('viewport_center_y',104)
                cx=128+pc*dx-ps*dy;cy=chart.get('viewport_center_y',104)+ps*dx+pc*dy
                spec=self.data['sprites'][index];factor=unit*(1+amount*.6)*zoom/spec['ppunit']
                size=tuple(max(1,round(v*factor)) for v in spec['size']);key=index,size
                if key not in self.cache:self.cache[key]=self.sprites[index].resize(size,Image.Resampling.BILINEAR)
                mask=self.cache[key];result.paste(0,(0,0,256,184));result.paste(mask,(round(cx-size[0]/2),round(cy-size[1]/2)))
                alpha=np.minimum(255,np.array(result,dtype=np.uint16)*min(1,amount)).astype(np.uint16)
                clip=255-((255-clip)*(255-alpha)+127)//255
        # The scene's broad cloud overlay begins twelve beats after FogBegin,
        # reaches full opacity in eight beats, and fades over beats 617..625.
        overlay=max(0,min(1,(b-597)/8))*max(0,min(1,(625-b)/8))
        if overlay:
            index=self.data['groups'][2][0]
            broad=np.array(self.sprites[index].resize((256,184),Image.Resampling.BILINEAR),dtype=np.uint16)
            alpha=np.round(broad*overlay).astype(np.uint16)
            clip=255-((255-clip)*(255-alpha)+127)//255
        clip[:chart.get('viewport_top',32)+1]=0;clip[chart.get('viewport_bottom',176)+1:]=0
        return clip

    def screen(self,frame,image,camera,rotation,palette):
        mask=self.mask(frame,camera,rotation)
        if mask is None:return image
        # Ordered alpha coverage keeps the cartridge's original track colors
        # intact instead of quantizing them to make room for fog blends.
        # Four coverage levels are spatially interleaved, never temporal.
        rank=np.array(((0,8,2,10),(12,4,14,6),(3,11,1,9),(15,7,13,5)))
        # Four-pixel cloud texels and four alpha steps prevent photographic
        # smoke noise from monopolizing the atlas. Track pixels, colors and
        # every authored animation frame retain their original resolution.
        alpha=mask.reshape(46,4,64,4).mean(axis=(1,3))
        alpha=np.repeat(np.repeat(np.round(alpha/64)*64,4,axis=0),4,axis=1)
        cover=alpha>np.tile(rank,(46,64))*16+7
        cover[:self.chart.get('viewport_top',32)+1]=False
        cover[self.chart.get('viewport_bottom',176)+1:]=False
        used={int(palette[i]) for i in np.unique(image) if i}
        index=next((i for i in range(32,128) if int(palette[i])==32767),None)
        if index is None:
            index=next(i for i in range(32,128) if int(palette[i]) not in used);palette[index]=32767
        output=image.copy();output[cover]=index
        return output
