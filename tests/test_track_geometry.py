import math,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from track_geometry import piece
class Geometry(unittest.TestCase):
 def test_separated_sections_do_not_change_authored_piece_angles(self):
  def notes(distance):return [dict(x=0,y=0,exit_angle=0),dict(x=distance,y=0,entry_angle=math.pi,exit_angle=math.pi/2),dict(x=distance,y=24)]
  a=piece(notes(24),1);b=piece(notes(240),1)
  self.assertEqual(a[2].tobytes(),b[2].tobytes())
 def test_zero_scale_emits_no_pixels_and_keeps_pivot(self):
  notes=[dict(x=100,y=200,entry_angle=math.pi,exit_angle=0),dict(x=124,y=200)]
  x,y,image=piece(notes,0,scale=(0,0))
  self.assertEqual((x,y),(100,200));self.assertIsNone(image.getbbox())
if __name__=='__main__':unittest.main()
