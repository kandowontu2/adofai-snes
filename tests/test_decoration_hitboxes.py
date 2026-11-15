import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from decoration_hitboxes import compile_region, table_source
from make_assets import FPS


class DecorationHitboxTests(unittest.TestCase):
    def test_authored_bar_rotation_and_null_axis(self):
        with tempfile.TemporaryDirectory() as folder:
            Image.new('RGBA', (10, 10), 'white').save(Path(folder)/'bar.png')
            data = dict(source=str(Path(folder)/'main.adofai'), bpm=60,
                        featured_decorations=[dict(floor=0, hitbox='Kill', relativeTo='Tile',
                            decorationImage='bar.png', position=[3.5,4], rotation=30,
                            scale=[500,40000], tag='bar')], featured_actions=[
                            dict(floor=1,eventType='MoveDecorations',tag='bar',duration=2,
                                 rotationOffset=720,positionOffset=[2,None],ease='Linear')])
            chart = dict(notes=[dict(x=0,y=0,time=0,speed=1),dict(x=24,y=0,time=1,speed=1)])
            region = dict(step=1,start=round(FPS),return_start=round(4*FPS))
            compile_region(data,chart,region)
            obj = region['decoration_hitboxes'][0]
            first, last = obj['frames'][0], obj['frames'][-1]
            self.assertEqual(first[0:2], [60,-96])
            self.assertEqual(last[0:2], [108,-96])
            self.assertEqual(last[4:6], [4,320])
            self.assertAlmostEqual(first[2], last[2], delta=1)
            self.assertAlmostEqual(first[3], last[3], delta=1)
            middle = obj['frames'][round(FPS/2)]
            self.assertLess(middle[2], 0)

    def test_shared_tracks_reconstruct_every_frame(self):
        frames = [[10,20,256,0,4,100]]*3+[[10+i,20,256-i,i,4,100] for i in range(10)]+[[19,20,247,9,4,100]]*3
        objects = [dict(start=100,end=116,frames=frames),dict(start=100,end=116,frames=frames)]
        text = table_source([dict(freeroam_regions=[dict(decoration_hitboxes=objects)])])
        data = bytearray(); labels = {}
        for line in text.splitlines():
            if line.endswith(':'):
                labels[line[:-1]] = len(data)
            elif line.startswith('.word'):
                data += b''.join(struct.pack('<H',int(v)&65535) for v in line[6:].split(','))
            else:
                data += bytes(map(int,line[6:].split(',')))
        self.assertEqual(data[labels['neo_deco_records']:labels['neo_deco_records']+6],
                         data[labels['neo_deco_records']+6:labels['neo_deco_records']+12])
        for time, expected in enumerate(frames,100):
            actual = []
            for off in struct.unpack_from('<3H',data,labels['neo_deco_records']):
                first,last,lo,hi = struct.unpack_from('<4H',data,labels['neo_deco_tracks']+off)
                at = max(first,min(last,time))-first
                actual += struct.unpack_from('<2h',data,labels['neo_deco_geometry']+lo+(hi<<16)+4*at)
            self.assertEqual(actual,expected)

    def test_it_stop_is_only_in_joke_worlds(self):
        from menu_sets import groups
        from import_jokes import JOKES
        self.assertEqual(JOKES[0]['workshop'],'3247303263')
        self.assertEqual(groups([95]),[('JOKE WORLDS',[0])])
        self.assertNotEqual(JOKES[0]['author'],'Firestix')


if __name__ == '__main__':
    unittest.main()
