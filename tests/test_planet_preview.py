import math
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from neo_runtime_assets import planet_previews
from graphics_sources import neo_objects,ROOT


class PlanetPreviewTests(unittest.TestCase):
    def test_only_new_third_planets_have_a_preview(self):
        notes=[dict(planets=p,entry_angle=math.pi,ccw=False) for p in (2,3,3,2,3)]
        rows=planet_previews(notes,[{}]*len(notes))
        self.assertEqual([r[0] for r in rows],[1,4])
        self.assertEqual(rows[0][1:],(-24,0,-12,-21))

    def test_direction_and_scaled_orbit_define_the_triangle(self):
        notes=[dict(planets=2),dict(planets=3,entry_angle=math.pi,ccw=True)]
        self.assertEqual(planet_previews(notes,[{},dict(radiusScale=2)])[0],(1,-48,0,-24,42))

    def test_initial_three_planets_and_pause_tiles_get_no_insertion_preview(self):
        notes=[dict(planets=3),dict(planets=3,flags=32),dict(planets=2,flags=32)]
        self.assertEqual(planet_previews(notes,[{}]*3),[])

    def test_preview_dash_does_not_replace_other_contributor_graphics(self):
        original=(ROOT/'mode7/freeroam.chr').read_bytes();updated=neo_objects()
        self.assertEqual(updated[:24*32],original[:24*32])
        self.assertEqual(updated[25*32:],original[25*32:])
        self.assertNotEqual(updated[24*32:25*32],bytes(32))
