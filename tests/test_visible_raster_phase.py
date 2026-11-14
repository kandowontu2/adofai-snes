import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from raster_phase import schedule


class VisibleRasterPhaseTests(unittest.TestCase):
    def test_offscreen_motion_cannot_rephase_visible_track(self):
        notes=[dict(x=120,y=100)]*10+[dict(x=2000,y=2000)]*40
        motion={1:{i:(3,5) for i in range(10,50)},2:{i:(4,6) for i in range(10,50)}}
        self.assertEqual(schedule(motion,8,chart=dict(notes=notes),initial=[3]*50,changes={},cameras=[[0,0,0]]),[[0,0,0]])

    def test_hidden_motion_cannot_rephase_visible_track(self):
        notes=[dict(x=120,y=100)]*50
        motion={1:{i:(3,5) for i in range(10,50)}}
        self.assertEqual(schedule(motion,8,chart=dict(notes=notes),initial=[3]*10+[0]*40,changes={},cameras=[[0,0,0]]),[[0,0,0]])

    def test_dominant_visible_motion_keeps_texture_phase(self):
        notes=[dict(x=120,y=100)]*10
        motion={1:{i:(3,5) for i in range(10)},2:{i:(4,6) for i in range(10)}}
        self.assertEqual(schedule(motion,8,chart=dict(notes=notes),initial=[3]*10,changes={},cameras=[[0,0,0]]),[[0,0,0],[1,3,5],[2,4,6]])

if __name__=='__main__':unittest.main()
