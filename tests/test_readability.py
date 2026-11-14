"""Advance warning, authored visibility and distinct spin silhouettes."""
import math,sys,unittest
from pathlib import Path
import numpy as np
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from track_readability import depth_schedule
from track_geometry import piece
from track_motion import nearby_motion
from campaign_assets import compile_chart
from make_assets import FPS
from track_patterns import cache_patterns
from track_visibility import animated_track
from verify_render import map_reader


class Readability(unittest.TestCase):
    def chart(self):
        return dict(mode7=True,notes=[dict(frame=i*3,x=128+(i%4)*24,y=144) for i in range(70)])

    def at(self,initial,changes,i,frame):
        value=initial[i]
        for at,updates in sorted(changes.items()):
            if at>frame:break
            value=updates.get(i,value)
        return value

    def test_visible_route_is_not_hidden_by_invented_time_or_floor_windows(self):
        c=self.chart();initial,changes=depth_schedule(c,[3]*70,{})
        self.assertTrue(all(v==3 for v in initial))
        for frame in (1,30,120,200):
            self.assertTrue(all(self.at(initial,changes,i,frame)==3 for i in range(70)))

    def test_preview_never_overrides_authored_hidden_tiles(self):
        c=self.chart();authored=[3]*70;authored[60]=0
        initial,changes=depth_schedule(c,authored,{150:{60:3}})
        self.assertEqual(self.at(initial,changes,60,149),0)
        self.assertGreater(self.at(initial,changes,60,150),0)

    def test_simultaneous_floors_survive_their_hit_frame(self):
        c=self.chart()
        for n in c['notes'][20:40]:n['frame']=120
        for n in c['notes'][40:]:n['frame']+=120
        initial,changes=depth_schedule(c,[3]*70,{})
        self.assertTrue(all(self.at(initial,changes,i,120)>0 for i in range(20,40)))

    def test_preview_initializes_motion_then_detailed_tiles_follow_it(self):
        c=self.chart();c['nearby_motion_only']=True
        motion={0:{10:(16,0)},8:{10:(24,0)},16:{10:(32,0)},24:{10:(40,0)}}
        initial=[0]*70;visibility={4:{10:1},12:{10:3}}
        result=nearby_motion(c,motion,initial,visibility)
        self.assertEqual(result[4][10],(16,0))
        self.assertNotIn(10,result.get(8,{}))
        self.assertEqual(result[12][10],(24,0))
        self.assertEqual(result[16][10],(32,0))

    def test_visible_preview_tracks_only_the_authored_moving_floor(self):
        c=self.chart();motion={0:{10:(16,0)},8:{10:(24,0)},16:{10:(32,0)}}
        initial=[1]*70
        result=nearby_motion(c,motion,initial,{})
        self.assertEqual(result[8],{10:(24,0)})
        self.assertEqual(result[16],{10:(32,0)})

    def test_active_nonsticky_route_stays_under_the_planets(self):
        c=self.chart();c['notes'][10]['stick_to_floor']=False
        c['readability_detail_starts']=[12]*70
        result=nearby_motion(c,{0:{10:(96,96)},16:{10:(120,120)}},[1]*70,{})
        self.assertEqual(result[0][10],(96,96))
        self.assertEqual(result[12][10],(0,0))
        self.assertNotIn(10,result.get(16,{}))

    def test_common_preview_pattern_is_loaded_once_across_repeats(self):
        chart=dict(mode7=True,code='TEST')
        tiles=[bytes(64),bytes([127]+[0]*63)]
        _,history=cache_patterns(chart,tiles,{(0,0):[(0,0),(30,1),(40,0),(90,1),(100,0)]})
        self.assertEqual(chart['pattern_pinned_count'],1)
        self.assertEqual(chart['pattern_versions'][1],[(0,1)])
        self.assertEqual(history[(0,0)],[(0,0),(30,1),(40,0),(90,1),(100,0)])


class SpinShapes(unittest.TestCase):
    def test_shared_contour_does_not_merge_crossing_surfaces(self):
        notes=[dict(x=64,y=64,entry_angle=math.pi,exit_angle=0,frame=0),
               dict(x=64,y=64,entry_angle=-math.pi/2,exit_angle=math.pi/2,frame=10),
               dict(x=88,y=64,exit_angle=0,frame=20)]
        c=dict(id=77,code='CROSSING',notes=notes,mode7=True,authored_visibility=True,
               shared_track_contour=True,map_offset_shift=2)
        raw,compressed,_=animated_track(c,[3]*3,{})
        read=map_reader(compressed,c['map_height'],2)
        def pixel(x,y):return raw[read(x//8,y//8)*64+(y%8)*8+x%8]
        # The foreground horizontal floor has an unbroken one-pixel edge
        # across the lower vertical floor, and no hidden edge through its fill.
        for x in range(59,70):self.assertEqual(pixel(x,57),35)
        self.assertEqual(pixel(64,64),33)
        self.assertEqual(pixel(64,65),33)

    def test_shared_outline_preserves_connected_step_boundaries(self):
        notes=[dict(x=64+24*i,y=64,exit_angle=0,frame=10*i) for i in range(4)]
        c=dict(id=77,code='SEAMS',notes=notes,mode7=True,authored_visibility=True,
               shared_track_contour=True,map_offset_shift=2)
        raw,compressed,_=animated_track(c,[3]*4,{})
        read=map_reader(compressed,c['map_height'],2)
        def pixel(x,y):return raw[read(x//8,y//8)*64+(y%8)*8+x%8]
        for x in (75,99,123):
            self.assertNotEqual(pixel(x,64),pixel(x-2,64))
            self.assertEqual(pixel(x,64),pixel(64,57))
        self.assertEqual(pixel(64,64),pixel(88,64))

    def test_earlier_tile_occludes_outline_of_lower_crossing_tile(self):
        notes=[dict(x=64,y=64,exit_angle=0,frame=0),
               dict(x=64,y=64,exit_angle=math.pi/2,frame=10),
               dict(x=88,y=64,exit_angle=0,frame=20)]
        c=dict(id=77,code='LAYER',notes=notes,mode7=True,authored_visibility=True,map_offset_shift=2)
        raw,compressed,_=animated_track(c,[3]*3,{})
        read=map_reader(compressed,c['map_height'],2)
        def pixel(x,y):return raw[read(x//8,y//8)*64+(y%8)*8+x%8]
        self.assertEqual(pixel(64,64),33)
        self.assertEqual(pixel(57,64),33)
        self.assertEqual(pixel(64,57),35)

    def test_identical_authored_angles_keep_identical_shape_at_every_grid_phase(self):
        for angle in (math.pi/6,math.pi/3,math.pi*3/4):
            reference=None
            for dx in range(8):
                for dy in range(8):
                    notes=[dict(x=100+dx,y=100+dy,exit_angle=angle),
                           dict(x=124+dx,y=112+dy,exit_angle=angle+math.pi/2),
                           dict(x=112+dx,y=136+dy)]
                    x,y,im=piece(notes,1)
                    value=(x-dx,y-dy,im.size,im.tobytes())
                    if reference is None:reference=value
                    self.assertEqual(value,reference)

    def fixture(self,kind):
        return [dict(x=100,y=100),dict(x=124,y=100,spin_kind=kind),dict(x=100,y=100),dict(x=76,y=100)]

    def bitmap(self,notes):
        canvas=Image.new('L',(160,160))
        for i in range(len(notes)):
            x,y,im=piece(notes,i);canvas.paste(im,(x,y),im)
        return np.array(canvas)

    def test_both_spins_have_a_gap_and_different_tips(self):
        mid=self.bitmap(self.fixture('midspin'));full=self.bitmap(self.fixture('full'))
        for im in (mid,full):
            self.assertTrue(im[100,124])
            self.assertFalse(im[100,113:115].any())
        self.assertGreater(np.count_nonzero(full[:,131]),np.count_nonzero(mid[:,131]))
        self.assertFalse(np.array_equal(mid,full))

    def test_rotation_keeps_the_exact_landing_center(self):
        for angle in (0,math.pi/4,math.pi/2,3*math.pi/4):
            p=dict(x=131,y=149,spin_kind='midspin')
            q=dict(x=131-round(24*math.cos(angle)),y=149-round(24*math.sin(angle)))
            x,y,im=piece([q,p,q],1)
            self.assertTrue(im.getpixel((131-x,149-y)))

    def test_diagonal_connector_preserves_pointed_outer_corner(self):
        notes=[dict(x=76,y=100,exit_angle=0),
               dict(x=100,y=100,entry_angle=math.pi,exit_angle=math.pi/4),
               dict(x=117,y=117,spin_kind='midspin')]
        x,y,im=piece(notes,1)
        self.assertTrue(im.getpixel((103-x,93-y)))

    def test_compiler_distinguishes_full_turn_from_automatic_midspin(self):
        floors=[dict(seqID=i,entryangle=math.pi*1.5,exitangle=math.pi*.5,speed=1.,isCCW=0,
                     extraBeats=0.,midSpin=0,holdLength=-1,numPlanets=2) for i in range(4)]
        floors[1]['exitangle']=floors[1]['entryangle']
        data=dict(id=1,title='TEST',bpm=120,offset=0,countdown=4,separate_countdown=True,floors=floors)
        c,_=compile_chart(data)
        self.assertEqual(c['notes'][1]['spin_kind'],'full')
        self.assertFalse(c['notes'][1]['flags']&8)
        floors[1]['numPlanets']=3;c,_=compile_chart(data)
        self.assertEqual(c['notes'][1]['spin_kind'],'full')
        floors[1]['midSpin']=1;c,_=compile_chart(data)
        self.assertEqual(c['notes'][1]['spin_kind'],'midspin')
        self.assertTrue(c['notes'][1]['flags']&8)


if __name__=='__main__':unittest.main()
