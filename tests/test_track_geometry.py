import math,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from track_geometry import piece
class Geometry(unittest.TestCase):
 def test_gem_platform_has_facets_and_tracks_its_center(self):
  notes=[dict(x=100,y=200,gem_platform=True)]
  x,y,im=piece(notes,0)
  self.assertEqual(im.getpixel((100-x,200-y)),128)
  self.assertEqual(set(im.getdata()),{0,128,255})
  self.assertEqual(im.getpixel((100-x+9,200-y+9)),0)
  moved=piece([dict(notes[0],x=124,y=177)],0)
  self.assertEqual(moved[:2],(x+24,y-23));self.assertEqual(moved[2].tobytes(),im.tobytes())
  self.assertIsNone(piece(notes,0,scale=(0,0))[2].getbbox())
  self.assertGreater(piece(notes,0,scale=(2,2))[2].width,im.width)
 def test_separated_sections_do_not_change_authored_piece_angles(self):
  def notes(distance):return [dict(x=0,y=0,exit_angle=0),dict(x=distance,y=0,entry_angle=math.pi,exit_angle=math.pi/2),dict(x=distance,y=24)]
  a=piece(notes(24),1);b=piece(notes(240),1)
  self.assertEqual(a[2].tobytes(),b[2].tobytes())
 def test_zero_scale_emits_no_pixels_and_keeps_pivot(self):
  notes=[dict(x=100,y=200,entry_angle=math.pi,exit_angle=0),dict(x=124,y=200)]
  x,y,image=piece(notes,0,scale=(0,0))
  self.assertEqual((x,y),(100,200));self.assertIsNone(image.getbbox())
if __name__=='__main__':unittest.main()
