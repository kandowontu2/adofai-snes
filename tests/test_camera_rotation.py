import math,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from track_camera import rotation_schedule
from make_assets import FPS

class CameraRotation(unittest.TestCase):
    def sample(self,actions,at,initial=0,native=None):
        d=dict(bpm=60,camera_actions=actions,camera_rotation_initial=initial,native_camera_effects=native or [])
        c=dict(notes=[dict(time=float(i),speed=1) for i in range(10)])
        rows=rotation_schedule(d,c)
        return next((a,b) for f,a,b in reversed(rows) if f<=round(at*FPS))
    def test_cardinal_and_negative_angles(self):
        for a,expected in [(0,(256,0)),(90,(0,256)),(-90,(0,-256)),(180,(-256,0)),(360,(256,0))]:
            self.assertEqual(self.sample([],0,initial=a),expected)
    def test_full_turn_is_not_shortest_path(self):
        actions=[dict(floor=0,eventType='MoveCamera',rotation=360,duration=4)]
        c,s=self.sample(actions,1)
        self.assertAlmostEqual(c,0,delta=2);self.assertAlmostEqual(s,256,delta=1)
        self.assertEqual(self.sample(actions,4),(256,0))
    def test_last_position_is_additive(self):
        actions=[dict(floor=1,eventType='MoveCamera',rotation=90,duration=0,relativeTo='LastPosition'),dict(floor=2,eventType='MoveCamera',rotation=90,duration=0,relativeTo='LastPosition')]
        self.assertEqual(self.sample(actions,2),( -256,0))
    def test_interruption_completes_previous_target(self):
        actions=[dict(floor=0,eventType='MoveCamera',rotation=90,duration=4),dict(floor=1,eventType='MoveCamera',rotation=180,duration=2)]
        self.assertEqual(self.sample(actions,1),(0,256))
    def test_native_rotation_without_zoom(self):
        n=[dict(floor=1,startTime=1,rotationUsed=True,zoomUsed=False,targetRot=-90,duration=0,movementTypeUsed=False)]
        self.assertEqual(self.sample([],1,native=n),(0,-256))
    def test_native_saved_editor_time_is_recalculated(self):
        n=[dict(floor=1,startTime=129.1462,rotationUsed=True,targetRot=180,duration=0,movementTypeUsed=False)]
        self.assertEqual(self.sample([],1,native=n),(-256,0))
    def test_loss_only_and_disabled_events_ignored(self):
        actions=[dict(floor=1,eventType='SetConditionalEvents',lossTag='lost'),dict(floor=1,eventType='MoveCamera',rotation=90,eventTag='lost'),dict(floor=2,eventType='MoveCamera',rotation=180,active=False)]
        self.assertEqual(self.sample(actions,3),(256,0))
    def test_repeat_relative_turns(self):
        actions=[dict(floor=1,eventType='MoveCamera',rotation=90,duration=0,relativeTo='LastPosition',eventTag='spin'),dict(floor=1,eventType='RepeatEvents',tag='spin',interval=1,repetitions=2)]
        self.assertEqual(self.sample(actions,3),(0,-256))

if __name__=='__main__':unittest.main()
