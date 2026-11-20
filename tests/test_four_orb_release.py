import math,sys,tempfile,unittest
from pathlib import Path
from PIL import Image,ImageDraw
sys.path.insert(0,'tools')
from verify_four_orb_release import inspect


class FourPlanetImageTests(unittest.TestCase):
    def scene(self,centers=None,missing=(),markers=False):
        image=Image.new('RGB',(256,224),(8,8,24));draw=ImageDraw.Draw(image)
        centers=centers or [(116,104),(140,104),(116,80),(140,80)]
        for name,color,(x,y) in zip(('red','green','blue','yellow'),
                ((255,0,0),(0,255,0),(0,70,255),(255,255,0)),centers):
            if name not in missing:draw.ellipse((x-5,y-5,x+5,y+5),fill=color)
        if markers:
            for x in (20,25,30):draw.rectangle((x,103,x+2,105),fill=(255,0,0))
        return image

    def measure(self,image):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'screen.png';image.save(path);return inspect(path)

    def test_four_bodies_have_authored_square_radius(self):
        result=self.measure(self.scene())
        self.assertAlmostEqual(result['diameter'],24*math.sqrt(2))
        self.assertEqual(result['centers']['red'],[116,104])

    def test_separate_red_tile_markers_do_not_shift_planet_centroid(self):
        result=self.measure(self.scene(markers=True))
        self.assertEqual(result['centers']['red'],[116,104])
        self.assertEqual(result['ignored_pixels']['red'],27)
        self.assertAlmostEqual(result['diameter'],24*math.sqrt(2))

    def test_tile_markers_cannot_replace_a_missing_planet(self):
        with self.assertRaisesRegex(AssertionError,'planet missing/clipped'):
            self.measure(self.scene(missing=('red',),markers=True))

    def test_oversized_orbit_still_fails(self):
        with self.assertRaisesRegex(AssertionError,'four-orb orbit radius'):
            self.measure(self.scene([(96,104),(156,104),(96,44),(156,44)]))

    def test_group_detached_from_track_still_fails(self):
        with self.assertRaisesRegex(AssertionError,'detached from playfield'):
            self.measure(self.scene([(30,104),(54,104),(30,80),(54,80)]))


if __name__=='__main__':unittest.main()
