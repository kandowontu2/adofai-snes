"""Sample Mawaru chapter-owned motion on the same clock as its chart.

Equations and beat ranges follow Mawaru and TaroBGScript in the installed
game. These are gameplay presentation, not random decorative camera shakes.
"""
import bisect,math
from make_assets import FPS
from track_motion import easing

def copy_cameras(beat, ex=False):
    """Native VictoryLap camera offsets (Unity units/degrees).

    Keep this independent of SNES projection: track copies and live planet
    copies must consume exactly the same transforms, including their exits.
    """
    if not 850<=beat<882:return []
    amplitude=3*math.sin((beat-850)*math.pi/4)
    count=2 if 854<=beat<858 or 866<=beat<870 or 874<=beat<878 else 4
    result=[]
    for i in range(count):
        angle=0
        if beat<854 or 862<=beat<866 or beat>=878:
            phase=beat*math.pi/2*(-1 if 862<=beat<866 else 1)+i/(6 if beat>=878 else 4)*math.tau
            x,y=amplitude*math.sin(phase),amplitude*math.cos(phase)
            if beat>=878:angle=25*amplitude/3*(1 if i%2==0 else -1)
        elif beat<858:x,y=0,amplitude*(1 if i%2 else -1)
        elif beat<862:x,y=amplitude*(i-1.5),0
        elif beat<870:
            x,y=amplitude*(1 if i%2 else -1),amplitude*(-1 if i%2 else 1)
            angle=10*amplitude
        elif beat<874:
            x,y=amplitude*(1 if i%2 else -1),amplitude*(1 if i in (1,2) else -1)
            angle=(360 if ex else 720)*easing('OutCubic',(beat-870)/4)
        else:
            x,y=0,-10*i+10*easing('InOutCubic',(beat-874)/4)
            angle=-20*amplitude/3
        result.append((x,y,angle))
    return result

def clock(chart):
    from neo_visuals import chapter_time
    times=[chapter_time(chart,b) for b in range(1057)]
    def beat(frame):
        t=frame/FPS;i=max(0,min(1055,bisect.bisect_right(times,t)-1))
        return i+(t-times[i])/(times[i+1]-times[i])
    return beat

def camera(chart):
    if chart.get('code') not in ('T3-X','T3EX-X'):return
    beat=clock(chart);ex=chart['code']=='T3EX-X'
    zoom=dict((f,(z,i)) for f,z,i in chart['camera_zoom_versions'])
    rotation=dict((f,(c,s)) for f,c,s in chart.get('camera_rotation_versions',[(0,256,0)]))
    phase=dict(chart.get('camera_rotation_phase_versions',[(0,0)]))
    z,inv=zoom[0];c,s=rotation[0];angle=phase[0]
    zs=[];rs=[];ps=[]
    for f in range(chart['notes'][-1]['frame']+121):
        z,inv=zoom.get(f,(z,inv));c,s=rotation.get(f,(c,s));angle=phase.get(f,angle)
        b=beat(f);outz=z;outc,outs=c,s;outa=angle
        if 361<b<389:
            if ex:
                degrees=3*math.sin(b*.5*math.pi);factor=1+abs(.2*math.cos(b*.5*math.pi))
            elif b<375 or b>379:
                degrees=5*math.sin(b*math.pi);factor=1+abs(.25*math.sin(b*math.pi))
            else:
                q=b-375
                factor=1+(1.8-1)*easing('OutExpo',q/1.5) if q<1.5 else .8 if q<2 else 1.2-.2*easing('OutCubic',(q-2)/2)
                degrees=0 if q<2 else 20 if q<2.5 else -15 if q<3 else 10*(1-easing('OutCubic',q-3))
            outz=round(factor*256);r=math.radians(degrees)
            outc,outs=round(math.cos(r)*256),round(math.sin(r)*256);outa=round(degrees*256/360)&255
        # Keep approaching rocks inside the SNES playfield. Ease the wider
        # view in before the first target, and restore it at the native exit.
        for start,end in ((489,577),(962,978)):
            if start<=b<end:
                blend=min(1,(b-start)/2,(end-b)/2)
                outz=round(outz*(1+.15*blend))
        zi=(outz,round(65536/max(1,outz)))
        if not zs or tuple(zs[-1][1:])!=zi:zs.append([f,*zi])
        if not rs or tuple(rs[-1][1:])!=(outc,outs):rs.append([f,outc,outs])
        if not ps or ps[-1][1]!=outa:ps.append([f,outa])
    chart['camera_zoom_versions']=zs;chart['camera_rotation_versions']=rs;chart['camera_rotation_phase_versions']=ps
    chart['mawaru_camera_version']=1

def motion(data,chart,updates):
    if chart.get('code') not in ('T3-X','T3EX-X'):return updates
    beat=clock(chart);ex=chart['code']=='T3EX-X';notes=chart['notes'];unit=24/data['native_tile_size']
    ranges=((346,403),(405,450),(452,481),(680,717)) if ex else ((275,309),(312,339),(341,367),(508,545))
    sections=((360.5,389.5),(409,441),(457,489),(632.5,664.5))
    original={};last={};result={f:dict(v) for f,v in updates.items()}
    def envelope(b,points):
        previous=0
        for start,duration,target,ease in points:
            if b<start:return previous
            if b<start+duration:return previous+(target-previous)*easing(ease,(b-start)/duration)
            previous=target
        return previous
    drift=((409,2,.5,'OutCubic'),(420,4.5,0,'InOutCubic'),(424.9,.2,1,'Linear'),(425.1,2.4,0,'InQuad'),
           (427.9,.2,-1.3,'Linear'),(428.1,2.4,0,'InQuad'),(430.9,.2,1.6,'Linear'),(431.1,2.4,0,'InQuad'),
           (433.9,.2,-1.6,'Linear'),(434.1,6.8,0,'InOutCubic'))
    for f in range(notes[-1]['frame']+121):
        original.update(updates.get(f,{}));b=beat(f)
        for group,((lo,hi),(start,end)) in enumerate(zip(ranges,sections)):
            active=start<b<end and not (group==0 and ex)
            for i in range(lo,hi+1):
                if not active and i not in last:continue
                dx=dy=0
                if active:
                    n=notes[i];a=n['entry_angle'];q=n['exit_angle']
                    sweep=(a-q)%(2*math.pi) if not n['ccw'] else -((q-a)%(2*math.pi))
                    middle=a-sweep/2;px,py=math.cos(middle),math.sin(middle)
                    if group in (0,3):
                        phase=(b+.2)%1;amount=0
                        if phase<.5:
                            amount=(phase/.2)**2 if phase<.2 else 1-((phase-.2)/.3)**2
                            amount*=.5*(-1 if int(b+.2)%2 else 1)*(-1 if i%2 else 1)*(.75 if group==0 else .25)
                        dx,dy=px*amount,py*amount
                    else:
                        index=i-2 if i and notes[i-1]['spin_kind']=='midspin' else i
                        phase=(index+f/FPS*2)/8*math.tau
                        amount=envelope(b,drift) if group==1 else envelope(b,((457,16,.4,'Linear'),(483,6,0,'InOutCubic')))
                        if group==1:dx,dy=px*amount*.5*math.sin(phase),py*amount*.5*math.sin(phase)
                        else:dx,dy=amount*.5*math.sin(phase+math.pi/2),-amount*.5*math.sin(phase)
                base=original.get(i,(0,0));value=(base[0]+round(dx*unit),base[1]+round(dy*unit))
                if value!=last.get(i,base):result.setdefault(f,{})[i]=value
                if active:last[i]=value
                else:last.pop(i,None)
    chart['mawaru_motion_version']=1
    return dict(sorted(result.items()))
