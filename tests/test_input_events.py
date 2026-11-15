import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from input_event_assets import schedule,ACTION_MASKS
from make_assets import FPS
class InputEventTests(unittest.TestCase):
 def test_source_time_same_frame_and_reenable(self):
  data=dict(bpm=120,featured_actions=[
   dict(eventType='SetInputEvent',floor=0,target='Action1',ignoreInput=True,angleOffset=-90),
   dict(eventType='SetInputEvent',floor=0,target='Action2',ignoreInput=False,angleOffset=-90),
   dict(eventType='SetInputEvent',floor=1,target='Action1',ignoreInput=False)])
  rows=schedule(data,dict(notes=[dict(time=2,speed=1),dict(time=3,speed=1)]))
  self.assertEqual(rows,[(round(1.75*FPS),ACTION_MASKS['Action1']),(round(3*FPS),0)])
 def test_unsupported_callback_is_not_silently_dropped(self):
  with self.assertRaises(ValueError):schedule(dict(featured_actions=[dict(eventType='SetInputEvent',target='Action1',targetEventTag='DO')]),{})
 def test_hand_groups_cover_all_tap_buttons(self):
  self.assertEqual(ACTION_MASKS['Action1']|ACTION_MASKS['Action2'],0xcff0)
  self.assertEqual(ACTION_MASKS['Action1']&ACTION_MASKS['Action2'],0)
if __name__=='__main__':unittest.main()
