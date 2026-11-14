"""Camera event timing, interruption and special authored zooms."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from track_camera import camera_schedule
from track_motion import easing,ease_name
from make_assets import FPS

class Camera(unittest.TestCase):
    def test_projected_zero_zoom_disables_projection_and_recovers(self):
        from track_camera import mode7_zoom_schedule
        c=dict(code='TEST',projected_zoom_range=True,camera_zoom_versions=[
            [0,256,256],[1,7,9362],[2,0,0],[3,1536,43]])
        mode7_zoom_schedule(c)
        self.assertIn([2,0,0],c['camera_projection_versions'])
        self.assertIn([2,0,0],c['camera_sampling_versions'])
        self.assertEqual(c['camera_sampling_versions'][-1],[3,1536,0])

    def test_free_return_reveals_exit_before_next_landing(self):
        from track_camera import position_schedule,follow_schedule
        c=dict(bpm=60,native_follow_timing=True,notes=[
            dict(x=0,y=0,time=0,frame=0,speed=1),
            dict(x=300,y=0,time=10,frame=600,speed=1)],
            freeroam_regions=[dict(step=0,start=0,return_start=480,
                return_duration=60,end=600,move_camera=True,ease=1,exit_offset=[-24,0])])
        d=dict(bpm=60)
        follow=follow_schedule(c,{})
        rows=position_schedule(d,c,{},follow)
        at=lambda f:next(x+128 for t,x,y in reversed(rows) if t<=f)
        self.assertEqual(at(480),0)
        self.assertEqual(at(510),150)
        self.assertEqual(at(540),300)
        self.assertEqual(at(599),300)
        anchor=lambda f:next(x+128 for t,x,y in reversed(follow) if t<=f)
        self.assertEqual(anchor(599),276)
        self.assertLessEqual(abs(anchor(600)-anchor(599)),1)

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
        before_release=next(x for f,x,y in reversed(rows) if f<100)
        on_release=next(x for f,x,y in reversed(rows) if f<=100)
        self.assertGreaterEqual(on_release,before_release)
        self.assertLessEqual(on_release-before_release,2)

    def test_native_adjacent_camera_tweens_share_rounded_endpoint(self):
        from track_camera import position_schedule
        c=dict(notes=[dict(x=0,y=0,time=0,frame=0,speed=1),
                      dict(x=0,y=0,time=10.6/FPS,frame=11,speed=1),
                      dict(x=0,y=0,time=15.4/FPS,frame=15,speed=1)])
        d=dict(bpm=60,native_camera_effects=[
            dict(floor=1,positionUsed=True,movementTypeUsed=True,movementType=0,
                 targetPos=dict(x=1.5,y=0),duration=4.8/FPS,ease=1),
            dict(floor=2,positionUsed=True,movementTypeUsed=True,movementType=0,
                 targetPos=dict(x=1.5,y=0),duration=1,ease=1)])
        rows=position_schedule(d,c,{},[(0,-128,-104)])
        value=lambda frame:next(x+128 for f,x,y in reversed(rows) if f<=frame)
        self.assertEqual([value(f) for f in range(11,16)],[0,6,12,18,24])

    def test_native_hold_offset_is_inside_landing_tween(self):
        from track_camera import follow_schedule
        c=dict(bpm=60,native_follow_timing=True,notes=[
            dict(x=0,y=0,frame=0,speed=1,hold_length=0,exit_angle=0),
            dict(x=72,y=0,frame=round(2*FPS),speed=1)])
        rows=follow_schedule(c,{})
        value=lambda frame:next(x+128 for f,x,y in reversed(rows) if f<=frame)
        # Halfway through the hold, its 24-pixel offset is itself halfway
        # through the camera's two-beat interpolation: about 12, not 24.
        self.assertAlmostEqual(value(round(FPS)),12,delta=1)
        release=c['notes'][1]['frame']
        self.assertLessEqual(abs(value(release)-value(release-1)),1)

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
