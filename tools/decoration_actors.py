"""Song-clock actor anchors for authored scenery attached to a planet.

Live gameplay planets remain cartridge sprites. This sampler is only for
background decorations, which cannot depend on the player's input timing.
"""
import bisect
import math
from hold_path import sweep
from neo_runtime_assets import phase,planet_roles,twirl_curve
from track_motion import motion_schedule,planet_offset


class ActorAnchors:
    def __init__(self,data,chart):
        self.data=data;self.chart=chart;self.notes=chart['notes']
        self.times=[n['frame'] for n in self.notes]
        self.roles=planet_roles(self.notes)
        self.moves=motion_schedule(data,chart)
        self.offsets=[n.get('position_track_offset',(0,0)) for n in self.notes]
        self.frames=iter(sorted(self.moves));self.next=next(self.frames,None)
        self.frame=-1;self.last=None

    def at(self,frame):
        if frame==self.frame:return self.last
        if frame<self.frame:raise ValueError('Actor anchors require chronological frames')
        while self.next is not None and self.next<=frame:
            for i,p in self.moves[self.next].items():self.offsets[i]=p
            self.next=next(self.frames,None)
        i=max(0,bisect.bisect_right(self.times,frame)-1)
        n=self.notes[i];following=self.notes[min(i+1,len(self.notes)-1)]
        floor=self.data['floors'][i];duration=max(1,following['frame']-n['frame'])
        progress=max(0,min(1,(frame-n['frame'])/duration))
        progress=phase(floor.get('planetEase',1),progress,floor.get('planetEaseParts',1),floor.get('planetEasePartBehavior',0)==0)
        offset=self.offsets[i] if n.get('stick_to_floor',True) else planet_offset(n)
        x,y=n['x']+offset[0],n['y']+offset[1]
        radius=24*(floor.get('radiusScale',1)+(self.data['floors'][min(i+1,len(self.notes)-1)].get('radiusScale',1)-floor.get('radiusScale',1))*progress)
        if n.get('hold_length',-1)>=0:
            angle=n['angle']*math.pi/128+sweep(n)*progress
            target=self.offsets[min(i+1,len(self.notes)-1)] if following.get('stick_to_floor',True) else planet_offset(following)
            x+=(following['x']+target[0]-x-radius*math.cos(n['exit_angle']))*progress
            y+=(following['y']+target[1]-y-radius*math.sin(n['exit_angle']))*progress
        else:
            delta=max(0,frame-n['frame']-n.get('pause_frames',0)) if i else frame-self.chart['first_frame']+self.chart['first_arc_frames']
            angle=(n['angle']+delta*n['rate']/256)*math.pi/128
        curve=twirl_curve(n,following,self.chart['bpm']) if n['planets']==3 and n.get('flags',0)&4 else []
        reflection=curve[min(len(curve)-1,max(0,frame-n['frame']))] if curve else (256,0,256)
        def orbit(a):
            dx,dy=radius*math.cos(a),radius*math.sin(a);aa,b,dd=reflection
            return (x+(aa*dx+b*dy)/256,y+(b*dx+dd*dy)/256)
        pivot,active,trailing=self.roles[i]
        points=[None]*3;points[pivot]=(x,y);points[active]=orbit(angle)
        if n['planets']==3:points[trailing]=orbit(angle+(43 if n['ccw'] else -43)*math.pi/128)
        self.frame=frame;self.last=dict(zip(('RedPlanet','BluePlanet','GreenPlanet'),points))
        return self.last
