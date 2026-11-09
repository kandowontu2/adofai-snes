import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from viewport_cells import sampled_cells,pixel_masks
class Viewport(unittest.TestCase):
 def test_identity(self):
  cells=sampled_cells(0,0,256,0)
  self.assertEqual(cells,{(x,y) for x in range(32) for y in range(4,22)})
  self.assertTrue(all(v==(1<<64)-1 for v in pixel_masks(0,0,256,0).values()))
 def test_rotated_masks_cover_all_samples(self):
  from viewport_cells import sampled_pixels
  for c,s in [(254,-32),(0,256),(-256,0),(181,181),(128,0)]:
   px,py=sampled_pixels(159,1069,c,s)
   masks=pixel_masks(159,1069,c,s)
   for x,y in zip(px.ravel().tolist(),py.ravel().tolist()):
    self.assertTrue(masks[x//8,y//8]&(1<<((x&7)+8*(y&7))))
 def test_boundary_sharing_preserves_visible_color(self):
  from unittest.mock import patch
  from viewport_cells import share_clipped_patterns
  tiles=[bytes(64)]+[bytes([5,i])+bytes(62) for i in range(256)]
  history={(i,0):[(0,i+1)] for i in range(256)}
  chart=dict(notes=[dict(frame=1)],camera_follow_versions=[[0,0,0]],code='TEST')
  with patch('viewport_cells.pixel_masks',return_value={(i,0):1 for i in range(256)}):
   result=share_clipped_patterns(chart,tiles,history)
  self.assertEqual(len({rows[0][1] for rows in result.values()}),255)
  self.assertTrue(all(tiles[rows[0][1]][0]==5 for rows in result.values()))
 def test_visible_differences_cannot_share(self):
  from unittest.mock import patch
  from viewport_cells import share_clipped_patterns
  tiles=[bytes(64)]+[bytes([5,i])+bytes(62) for i in range(256)]
  history={(i,0):[(0,i+1)] for i in range(256)}
  chart=dict(notes=[dict(frame=1)],camera_follow_versions=[[0,0,0]],code='TEST')
  with patch('viewport_cells.pixel_masks',return_value={(i,0):3 for i in range(256)}):
   result=share_clipped_patterns(chart,tiles,history)
  self.assertEqual(result,history)
if __name__=='__main__':unittest.main()
