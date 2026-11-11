"""Camera event timing, interruption and special authored zooms."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from track_camera import camera_schedule
from track_motion import easing,ease_name
from make_assets import FPS

class Camera(unittest.TestCase):
    def fixture(self):
        return {'bpm':60,'camera_actions':[]},{'notes':[{'time':float(i),'speed':1} for i in range(8)]}
    def at(self,rows,frame):
        return next((m,i) for f,m,i in reversed(rows) if f<=frame)
    def test_native_follow_uses_two_beat_landing_tween(self):
        from track_camera import follow_schedule
        c=dict(bpm=60,native_follow_timing=True,notes=[
            dict(x=0,y=0,frame=0,speed=1),dict(x=240,y=0,frame=round(FPS),speed=1)])
        rows=follow_schedule(c,{})
        value=lambda frame:next((x+128,y+104) for f,x,y in reversed(rows) if f<=frame)
        self.assertLess(value(round(FPS))[0],10)
        self.assertAlmostEqual(value(round(2*FPS))[0],120,delta=4)
        self.assertEqual(value(round(3*FPS))[0],240)

    def test_hold_camera_follows_moving_tail(self):
        from track_camera import follow_schedule
        c=dict(notes=[dict(x=0,y=0,frame=0,hold_length=1,exit_angle=0),
                      dict(x=72,y=0,frame=100)])
        rows=follow_schedule(c,{50:{1:(216,0)}})
        x,y=next((x+128,y+104) for f,x,y in reversed(rows) if f<=50)
        self.assertEqual((x,y),(132,0))

    def test_initial_zoom_and_duration_endpoint(self):
        d,c=self.fixture();d['camera_initial']=2
        d['camera_actions']=[dict(floor=1,eventType='MoveCamera',zoom=100,duration=1)]
        rows=camera_schedule(d,c)
        self.assertEqual(self.at(rows,0),(512,128))
        self.assertEqual(self.at(rows,round(2*FPS)),(256,256))
        self.assertAlmostEqual(self.at(rows,round(1.5*FPS))[0],384,delta=2)
    def test_local_tempo_angle_and_beat_repeats(self):
        d,c=self.fixture();c['notes'][1]['speed']=2
        d['camera_actions']=[dict(floor=1,eventType='MoveCamera',zoom=200,duration=0,angleOffset=180,eventTag='a'),
                             dict(floor=1,eventType='RepeatEvents',tag='a',repetitions=2,interval=2)]
        rows=camera_schedule(d,c)
        self.assertEqual(self.at(rows,round(1.5*FPS)),(512,128))
        self.assertEqual(c['camera_zoom_events'],3)
        self.assertEqual(self.at(rows,round(1.5*FPS)-1),(256,256))
    def test_zero_hides_and_negative_inverts(self):
        d,c=self.fixture();d['camera_actions']=[dict(floor=i,eventType='MoveCamera',zoom=z,duration=0) for i,z in [(1,0),(2,-100)]]
        rows=camera_schedule(d,c)
        self.assertEqual(self.at(rows,round(FPS)),(0,0))
        self.assertEqual(self.at(rows,round(2*FPS)),(-256,-256))
    def test_interrupted_tween_completes_before_new_tween(self):
        d,c=self.fixture();d['camera_actions']=[dict(floor=1,eventType='MoveCamera',zoom=200,duration=4),
                                             dict(floor=2,eventType='MoveCamera',zoom=300,duration=0)]
        rows=camera_schedule(d,c)
        self.assertEqual(self.at(rows,round(2*FPS)),(768,85))
        self.assertEqual(rows[-1][0],round(2*FPS))
    def test_native_enum_easing_and_seconds(self):
        d,c=self.fixture();d['native_camera_effects']=[dict(floor=1,startTime=float('inf'),zoomUsed=True,targetZoom=2,duration=2,ease=6)]
        rows=camera_schedule(d,c)
        self.assertEqual(self.at(rows,round(3*FPS)),(512,128))
        self.assertAlmostEqual(self.at(rows,round(2*FPS))[0],448,delta=2)
        self.assertEqual(ease_name(6),'OutQuad')
    def test_zoom_omitted_and_disabled_events_are_ignored(self):
        d,c=self.fixture();d['camera_actions']=[dict(floor=1,eventType='MoveCamera',duration=1),
                                             dict(floor=2,eventType='MoveCamera',zoom=200,active=False)]
        self.assertEqual(camera_schedule(d,c),[(0,256,256)])
        for name in ['InOutBack','InOutElastic','OutBounce']:
            self.assertAlmostEqual(easing(name,0),0);self.assertAlmostEqual(easing(name,1),1)

if __name__=='__main__':unittest.main()
