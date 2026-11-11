import math
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from track_geometry import piece
from neo_visuals import configure


class NeoVisualTests(unittest.TestCase):
    def test_hold_traces_orbit_instead_of_filling_bridge(self):
        notes=[dict(x=64,y=64,entry_angle=math.pi,exit_angle=0,angle=128,hold_length=1,ccw=False),
               dict(x=208,y=64,entry_angle=math.pi,exit_angle=0)]
        x,y,im=piece(notes,0)
        # The curve must travel above and below the pivot's translation,
        # leaving open space along the old full-width filled bridge.
        self.assertLess(y,42)
        self.assertGreater(y+im.height,86)
        self.assertEqual(im.getpixel((124-x,64-y)),0)
        self.assertNotEqual(im.getpixel((208-x,64-y)),0)
        self.assertNotEqual(im.getpixel((64-x,64-y)),0)
        for px in range(40,65):
            self.assertNotEqual(im.getpixel((px-x,64-y)),0)

    def test_warp_marker_keeps_underlying_playable_floor(self):
        notes=[dict(x=64,y=64,entry_angle=math.pi,exit_angle=0,
                    warp_visual=dict(markers=[dict(center=[48,24],link=[[48,24],[96,24]])])),
               dict(x=88,y=64,exit_angle=0)]
        x,y,im=piece(notes,0)
        for px,py in ((64,64),(112,88),(140,88)):
            self.assertNotEqual(im.getpixel((px-x,py-y)),0)

    def test_platform_requires_identical_motion(self):
        notes=[dict(x=100,y=100,hold_length=-1,spin_kind='normal') for _ in range(3)]
        events=[dict(type='ffxMoveFloorPlus',floor=0,start=i,end=i,duration=1,
                     targetPos=dict(x=3 if i<2 else 4,y=0),ease=1) for i in range(3)]
        chart=dict(notes=notes)
        configure(dict(code='T4-X',native_track_effects=events),chart)
        self.assertEqual(notes[0]['platform_group'],[0,1])
        self.assertTrue(notes[1]['platform_hidden'])
        self.assertNotIn('platform_group',notes[2])

    def test_platforms_in_mawaru_and_divine_intervention(self):
        for code in ('T3-X','T3EX-X','T5-X'):
            notes=[dict(x=24*i,y=100,hold_length=-1,spin_kind='normal',time=i,frame=i*60) for i in range(1100)]
            for i in (10,11,12):notes[i]['x']=240
            events=[dict(type='ffxMoveFloorPlus',floor=0,start=10,end=12,duration=1,
                         targetPos=dict(x=3,y=0),ease=1)]
            chart=dict(code=code,notes=notes)
            data=dict(code=code,native_track_effects=events,native_positions=[[0,0]]*1100,native_tile_size=1.5)
            configure(data,chart)
            self.assertEqual(notes[10]['platform_group'],[10,11,12])
            self.assertFalse(notes[10]['platform_hidden'])
            self.assertTrue(notes[11]['platform_hidden'])

    def test_chapter_reveals_hidden_finale_floors(self):
        from neo_visuals import chapter_time
        notes=[dict(x=24*i,y=0,hold_length=-1,spin_kind='normal',time=i,frame=i*60) for i in range(874)]
        chart=dict(code='T3-X',notes=notes)
        configure(dict(code='T3-X',native_track_effects=[],native_positions=[[0,0]]*874,native_tile_size=1.5),chart)
        events=chart['neo_opacity_events']
        self.assertEqual(len(events),16)
        self.assertEqual(events[0]['floor'],812)
        self.assertEqual(events[0]['time'],chapter_time(chart,1008))
        self.assertEqual(events[-1]['floor'],833)

    def test_orbit_phase_lands_on_drawn_path(self):
        from hold_path import sweep
        import numpy as np
        for ccw in (False,True):
            n=dict(x=64,y=64,entry_angle=math.pi,exit_angle=.7,angle=128,hold_length=3,ccw=ccw)
            tail=dict(x=360,y=80,exit_angle=.7)
            x,y,im=piece([n,tail],0)
            ys,xs=np.where(np.array(im)>0);xs+=x;ys+=y
            for q in range(257):
                p=q/256;a=round(n['angle']+sweep(n)*128/math.pi*p)*math.pi/128
                px=64+int((360-64-round(24*math.cos(.7)))*p)+round(24*math.cos(a))
                py=64+int((80-64-round(24*math.sin(.7)))*p)+round(24*math.sin(a))
                self.assertLessEqual(float(np.min((xs-px)**2+(ys-py)**2)),4)

    def test_hold_connects_both_endpoints_in_either_direction(self):
        for ccw in (False,True):
            for angle in range(0,256,32):
                with self.subTest(ccw=ccw,angle=angle):
                    notes=[dict(x=80,y=80,entry_angle=angle*math.pi/128,
                                exit_angle=.7,angle=angle,hold_length=1,ccw=ccw),
                           dict(x=224,y=96,exit_angle=.7)]
                    x,y,im=piece(notes,0)
                    start=(80-x,80-y);end=(224-x,96-y)
                    seen={start};pending=[start]
                    while pending:
                        px,py=pending.pop()
                        for dx,dy in ((1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)):
                            q=(px+dx,py+dy)
                            if (q not in seen and 0<=q[0]<im.width and 0<=q[1]<im.height
                                    and im.getpixel(q)):
                                seen.add(q);pending.append(q)
                    self.assertIn(end,seen)

    def test_hold_tail_tracks_independent_floor_movement(self):
        notes=[dict(x=64,y=64,entry_angle=math.pi,exit_angle=0,angle=128,hold_length=1),
               dict(x=136,y=64,exit_angle=0)]
        for tail in ((136,64),(244,64),(352,80)):
            x,y,im=piece(notes,0,hold_tail=tail)
            self.assertNotEqual(im.getpixel((tail[0]-x,tail[1]-y)),0)
            self.assertNotEqual(im.getpixel((64-x,64-y)),0)

    def test_visible_hold_survives_start_tile_leaving_view(self):
        from track_readability import depth_schedule
        chart=dict(mode7=True,notes=[
            dict(x=0,y=0,frame=0,hold_length=1,exit_angle=0),
            dict(x=72,y=0,frame=100)])
        initial,changes=depth_schedule(chart,[3,3],{},motion={50:{1:(480,0)}})
        visible=initial[0]
        for frame,updates in changes.items():
            if frame<=50:visible=updates.get(0,visible)
        self.assertEqual(visible,3)


if __name__=='__main__':unittest.main()
