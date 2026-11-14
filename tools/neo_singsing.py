"""Imported scene visuals and authored timing for Sing Sing Red Indigo."""
import numpy as np


def extract(objects,chapter,world,by_object):
    from UnityPy.classes import PPtr
    lookup={o.path_id:o for o,_ in objects}
    output={}
    pointers={'cubicle':chapter['cubicle']}
    for j,p in enumerate(chapter.get('notefields',[])):
        field=lookup[p['m_PathID']].read_typetree()
        for key in ('backboard','planet'):
            pointers[f'lane{j}_{key}']=field[key]
        for k,p in enumerate(field['midspins']):pointers[f'lane{j}_midspin{k}']=p
    for name,ptr in pointers.items():
        if not ptr['m_PathID']:continue
        obj=lookup[ptr['m_PathID']];d=obj.read_typetree();go=d['m_GameObject']['m_PathID']
        render=next(o for o,_ in objects if o.type.name=='SpriteRenderer' and o.read_typetree()['m_GameObject']['m_PathID']==go)
        frames=d.get('frames',[])
        sprites=[PPtr(m_FileID=p['m_FileID'],m_PathID=p['m_PathID'],assetsfile=obj.assets_file) for p in frames] or [render.read().m_Sprite]
        matrix=world(by_object[go]);items=[]
        for pointer in sprites:
            if not pointer.m_PathID:continue
            sprite=pointer.deref().read();im=sprite.image.convert('RGBA');ppu=sprite.m_PixelsToUnits;pv=sprite.m_Pivot
            local=np.array([[1/ppu,0,-im.width/ppu*pv.x],[0,-1/ppu,im.height/ppu*(1-pv.y)],[0,0,1.]])
            affine=matrix[np.ix_([0,1,3],[0,1,3])]@local
            mask=im.getchannel('A');box=(0,0,im.width,im.height) if name=='cubicle' else mask.getbbox()
            if box is None:continue
            mask=mask.crop(box);affine=affine@np.array([[1,0,box[0]],[0,1,box[1]],[0,0,1.]])
            items.append(dict(size=list(mask.size),alpha=mask.tobytes().hex(),matrix=affine.tolist()))
        output[name]=dict(frames=items,animation=d)
    return output


class Scene:
    """Screen-space chapter art, transformed into the same world raster as floors."""
    def __init__(self,data,chart):
        from PIL import Image
        from make_assets import FPS
        import bisect,math
        self.chart=chart;self.FPS=FPS;self.ex=data['code']=='T2EX-X'
        self.start=chart['notes'][1]['time'];self.bpm=data['bpm']
        self.first=math.floor((self.start+28*60/self.bpm)*FPS)
        self.last=math.ceil((self.start+84*60/self.bpm)*FPS)
        self.art=data['native_singsing_visuals']
        needed={'lane0_midspin0'} if self.ex else {'cubicle'}
        self.masks={k:[Image.frombytes('L',tuple(f['size']),bytes.fromhex(f['alpha'])) for f in v['frames']]
                    for k,v in self.art.items() if k in needed}
        self.frames=range(self.first,self.last+1)
        self.transforms=chart['render_transforms'];self.times=sorted(map(int,self.transforms))
        self.cache={}
        self.hits=[41,44,47.5,50.5,53.25,56.25,58.5,60,61.5,63,65,65.5,68,68.5,70.5,71.25,71.5,73.5,74.25,74.5,77,77.25,77.5]
        # backBar's neutral vertical strokes are ordinary floor landings.
        # The colored midspin sprites are additional events, not replacements
        # for that timing grid. Use chart deadlines, including the last row's
        # changed rhythm, instead of inventing evenly spaced metronome ticks.
        self.standard_hits=standard_hits(chart,self.hits)
        chart['singsing_standard_hit_beats']=self.standard_hits

    def layers(self,frame):
        from PIL import Image,ImageDraw
        import bisect,math
        if frame<self.first or frame>self.last:return []
        if frame in self.cache:return self.cache[frame]
        beat=(frame/self.FPS-self.start)*self.bpm/60
        screens=[]
        def layer(slot,front=False):
            im=Image.new('L',(256,144));screens.append((slot,front,im));return im
        if not self.ex and 33.5<=beat<84:
            transitions=[b for b in (44,56,62,68,74) if beat>=b]
            # Mawaru_Sprite stops on frames 0 and 15. Each room transition
            # advances only to the next stop, rather than looping forever.
            advanced=0 if not transitions else min(15,int((beat-transitions[-1])*60/self.bpm/.033333335))
            which=(15+15*max(0,len(transitions)-1)+advanced)%30 if transitions else 15
            mask=self.masks['cubicle'][which]
            # CubicleTile uses _TexOffset.zw=(20,20): the sprite is a
            # repeated room texture, not one enlarged sprite. Preserve its
            # transparent margins so the repeated walls keep their spacing.
            scale=144/(10*1.2);size=(max(1,round(mask.width*.2*scale/20)),max(1,round(mask.height*.2*scale/20)))
            mask=mask.resize(size,Image.Resampling.NEAREST)
            # SingSing.CubicleTransition changes the room's scroll direction.
            hot=len(transitions)%2==0;dx,dy=(3.5,0) if hot else (0,3.5)
            if transitions:
                t=min(1,(beat-transitions[-1]));ease=0 if t==0 else 1 if t==1 else 2**(20*t-11) if t<.5 else 1-2**(-20*t+9)
                dx=(3.5 if hot else 0)*ease+(0 if hot else 3.5)*(1-ease)
                dy=(0 if hot else 3.5)*ease+(3.5 if hot else 0)*(1-ease)
            canvas=layer(44 if hot else 45)
            # Update integrates room velocity into the shader's UV offset.
            # The easing is symmetric, so a completed one-beat transition
            # contributes the average of its two endpoint velocities.
            ux=3.5*max(0,beat-34);uy=0.
            for j,at in enumerate(transitions):
                age=max(0,beat-at);t=min(1,age)
                import math
                integral=(2**(20*t-11)-2**-11)/(20*math.log(2)) if t<=.5 else t-.5+(2**(-20*t+9))/(20*math.log(2))
                integral+=max(0,age-1)
                sign=1 if j%2==0 else -1
                ux-=sign*3.5*integral;uy+=sign*3.5*integral
            ox=round(-ux*60/self.bpm*size[0])%size[0]
            oy=round(uy*60/self.bpm*size[1])%size[1]
            for y in range(oy-size[1],144,size[1]):
                for x in range(ox-size[0],256,size[0]):canvas.paste(mask,(x,y))
        if self.ex:
            for start in range(34,79,6):
                age=beat-(start-6)
                vertical=1.
                if start==34:
                    if not 32<=beat<40:continue
                    t=max(0,min(1,beat-32));size=1-(1-t)**3;y=-3.2+size
                    if beat>=33:size=1;y=-2.2
                    if beat>=39:vertical=(40-beat)**3;y=-2.2+.4*(1-vertical)
                else:
                    if not 0<=age<12:continue
                    t=max(0,min(1,age));ease=4*t*t*t if t<.5 else 1-(-2*t+2)**3/2;size=.6*ease;y=-3.2
                    if age>=5:
                        t=min(1,age-5);ease=4*t*t*t if t<.5 else 1-(-2*t+2)**3/2;size=.6+.4*ease;y=-3.2+ease
                    if age>=11:
                        t=age-11;ease=4*t*t*t if t<.5 else 1-(-2*t+2)**3/2
                        vertical=1-ease;y=-2.2+.4*ease
                if size<=0:continue
                # Keep the authored current/upcoming row motion, but place
                # both below the track rather than across its lower tiles.
                unit=14*size;cy=100-(y+.8)*14
                canvas=layer(47,True);draw=ImageDraw.Draw(canvas)
                width=max(1,round(9.74*unit));height=max(2,round(.45*unit*vertical))
                left=round(128-width/2);top=round(cy-height/2)
                draw.rounded_rectangle((left,top,left+width-1,top+height-1),
                                       radius=min(2,height//2),fill=96,outline=200)
                for hit in self.standard_hits:
                    if not start<=hit<start+6:continue
                    x=round(128+(hit-start-3)*unit)
                    half=max(1,round(.33*unit*vertical))
                    draw.line((x,round(cy)-half,x,round(cy)+half),fill=255,width=1)
                for hit in self.hits:
                    if not start<=hit<start+6 or beat>=hit+.6:continue
                    slot=44 if hit%1==0 else 45 if hit%1==.5 else 46
                    target=layer(slot,True);marker=self.masks['lane0_midspin0'][0]
                    # Quarter-beat clusters must remain separate at SNES
                    # resolution; keep their authored x/timing and height.
                    neighbors=[abs(other-hit) for other in self.hits if other!=hit and start<=other<start+6]
                    spacing=min(neighbors,default=1)*unit
                    width=min(max(1,round(.88*.66*unit)),max(1,round(spacing)-1))
                    marker=marker.resize((width,max(1,round(.96*.66*unit*vertical))),Image.Resampling.NEAREST)
                    x=128+(hit-start-3)*unit;dy=max(0,min(.4,(beat-hit)*.8))*unit
                    target.paste(marker,(round(x-marker.width/2),round(cy-marker.height/2-dy)))
                xpos=beat-start-3
                if -4<xpos<4:
                    target=layer(44 if (start-34)%12==0 else 45,True);draw=ImageDraw.Draw(target);x=128+xpos*unit;r=max(1,round(.22*unit))
                    draw.ellipse((round(x-r),round(cy-r),round(x+r),round(cy+r)),fill=255)
        at=self.times[bisect.bisect_right(self.times,frame)-1];c,s,cx,cy=self.transforms[at] if at in self.transforms else self.transforms[str(at)]
        c/=256;s/=256;norm=c*c+s*s
        corners=[((c*x+s*y)/norm+cx,(-s*x+c*y)/norm+cy) for x in (-128,128) for y in (-72,72)]
        x0=math.floor(min(x for x,y in corners))-1;y0=math.floor(min(y for x,y in corners))-1
        size=(math.ceil(max(x for x,y in corners))-x0+2,math.ceil(max(y for x,y in corners))-y0+2)
        result=[]
        for slot,front,im in screens:
            world=im.transform(size,Image.Transform.AFFINE,(c,-s,c*(x0-cx)-s*(y0-cy)+128,s,c,s*(x0-cx)+c*(y0-cy)+72),Image.Resampling.NEAREST)
            result.append((slot,front,x0,y0,world))
        self.cache={frame:result}
        return result

    def palette(self):
        colors=((1,.7,.7,.8),(.7,.7,1,.8),(1,1,.7,.8),(1,1,1,.4)) if self.ex else ((1,.4,0,.3),(0,.4,1,.3),(1,1,.7,.8),(1,1,1,.6))
        return [(0,(44+k)*2+j,sum(round(v*a*strength*31)<<(5*i) for i,v in enumerate((r,g,b))))
                for k,(r,g,b,a) in enumerate(colors) for j,strength in enumerate((.35,1.))]


def standard_hits(chart,midspins):
    origin=chart['notes'][1]['time'];bpm=chart['bpm'];beats=[]
    for note in chart['notes']:
        if note.get('spin_kind','normal')!='normal':continue
        beat=(note['time']-origin)*bpm/60
        if 34-.005<=beat<84 and not any(abs(beat-m)<.005 for m in midspins):beats.append(round(beat,5))
    return sorted(set(beats))
