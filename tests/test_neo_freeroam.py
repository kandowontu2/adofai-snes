import json
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from neo_freeroam import compile_regions, grid_piece, widen_views
from campaign_assets import compile_chart


class FreeRoamTests(unittest.TestCase):
    def test_disabled_scene_cells_do_not_expand_world(self):
        path=ROOT/'assets/private/level70.json'
        if not path.exists():self.skipTest('Installed DLC import required')
        chart,_=compile_chart(json.loads(path.read_text()))
        regions=chart['freeroam_regions']
        self.assertEqual(len(regions),9)
        self.assertEqual(len(regions[-1]['cells']),68)
        self.assertEqual(regions[-1]['bounds'],[0,-48,552,24])
        for r in regions:
            self.assertLess(r['return_start'],r['unlock'])
            self.assertLess(r['unlock'],r['end'])
            self.assertLessEqual(r['return_start']+r['return_duration'],r['end'])
            self.assertIn([0,0],[list(p) for p in r['cells']])

    def test_destroyed_cell_is_removed_without_changing_its_neighbors(self):
        r=dict(bounds=[0,0,24,0],cells=[(0,0),(24,0)],cell_deaths=[20,65535],render_frame=19)
        self.assertEqual(grid_piece(dict(x=0,y=0),r)[2].getpixel((11,11)),255)
        r['render_frame']=20
        image=grid_piece(dict(x=0,y=0),r)[2]
        self.assertEqual(image.getpixel((11,11)),0)
        self.assertEqual(image.getpixel((35,11)),255)

    def test_authored_laser_routes_avoid_both_planets(self):
        import math
        path=ROOT/'assets/private/level70.json'
        if not path.exists():self.skipTest('Installed DLC import required')
        chart,_=compile_chart(json.loads(path.read_text()))
        for r in chart['freeroam_regions']:
            if 'laser' not in r:continue
            n=chart['notes'][r['step']];at=r['start'];x=y=0;angle=n['angle'];cursor=0
            for frame,(left,top,right,bottom) in enumerate(r['laser']['rectangles'],r['start']):
                route=r['demo_route']
                while cursor<len(route) and route[cursor][0]<=frame:
                    at,x,y,angle=route[cursor];cursor+=1
                a=(angle+(frame-at)*n['rate']/256)*math.pi/128
                for px,py in ((x,y),(x+24*math.cos(a),y+24*math.sin(a))):
                    self.assertFalse(left<=px<=right and top<=py<=bottom,(r['step'],frame,px,py))

    def test_every_reachable_cell_is_preloaded(self):
        r=dict(step=0,start=10,end=100,fade_duration=20,bounds=[0,-48,552,24],cells=[(0,0),(552,24)])
        chart=dict(notes=[dict(x=200,y=200),dict(x=800,y=200)],freeroam_regions=[r])
        views={0:(9,12,32,18),10:(9,12,32,18),100:(84,12,32,18),121:(84,12,32,18)}
        transforms={}
        widen_views(chart,views,transforms)
        x,y,w,h=views[10]
        self.assertLessEqual(x*8,200-128)
        self.assertGreaterEqual((x+w)*8,200+552+128)
        self.assertEqual(views[100],(84,12,32,18))
        self.assertEqual(views[121],(84,12,32,18))

    def test_grid_has_separate_cells_and_holes(self):
        r=dict(bounds=[0,0,48,0],cells=[(0,0),(48,0)])
        x,y,image=grid_piece(dict(x=100,y=100),r)
        self.assertEqual((x,y),(89,89))
        self.assertEqual(image.getpixel((11,11)),255)
        self.assertEqual(image.getpixel((35,11)),0)
        self.assertEqual(image.getpixel((59,11)),255)


if __name__=='__main__':unittest.main()
