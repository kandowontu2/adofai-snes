import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from neo_mawaru import copy_cameras,clock,camera
from neo_visuals import chapter_time
from make_assets import FPS


class MawaruTests(unittest.TestCase):
    def test_native_copy_count_and_exit(self):
        self.assertEqual(copy_cameras(849.99),[])
        for beat,count in ((850,4),(854,2),(858,4),(862,4),(866,2),(870,4),(874,2),(878,4)):
            self.assertEqual(len(copy_cameras(beat)),count)
        self.assertEqual(copy_cameras(882),[])

    def test_native_copy_offsets_and_ex_rotation(self):
        self.assertAlmostEqual(copy_cameras(855)[0][1],3/2**.5)
        self.assertAlmostEqual(copy_cameras(855)[1][1],-3/2**.5)
        self.assertEqual(copy_cameras(876)[0][1],5)
        self.assertEqual(copy_cameras(876)[1][1],-5)
        self.assertEqual(copy_cameras(872)[0][2],630)
        self.assertEqual(copy_cameras(872,True)[0][2],315)

    def test_chapter_clock_inverts_bpm_boundaries(self):
        for code in ('T3-X','T3EX-X'):
            chart={'code':code,'notes':[{}, {'time':1.25}]}
            sample=clock(chart)
            for beat in (0,41,117,213,341,505,569,721,787,788,850,882,962,994,1055):
                self.assertAlmostEqual(sample(chapter_time(chart,beat)*FPS),beat)

    def test_camera_keeps_authored_state_outside_native_windows(self):
        chart={'code':'T3-X','notes':[{}, {'time':1,'frame':800}],
               'camera_zoom_versions':[[0,300,218]],
               'camera_rotation_versions':[[0,200,160]],
               'camera_rotation_phase_versions':[[0,28]]}
        camera(chart)
        self.assertEqual(chart['camera_zoom_versions'],[[0,300,218]])
        self.assertEqual(chart['camera_rotation_versions'],[[0,200,160]])
        self.assertEqual(chart['camera_rotation_phase_versions'],[[0,28]])
