"""Translation targets, coordinate direction, range repeats and easing."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from track_motion import motion_schedule,easing,nearby_motion,stick_schedule
from campaign_assets import compile_chart
from import_official import normalize_json
from make_assets import FPS

class Motion(unittest.TestCase):
    def test_short_sparse_tween_keeps_intermediate_frames(self):
        d,c=self.fixture();c.update(mode7=True,motion_step=8)
        d['track_actions']=[dict(floor=1,eventType='MoveTrack',positionOffset=[0,3],duration=.13636,ease='Linear')]
        poses=[v[1] for v in motion_schedule(d,c).values() if 1 in v]
        self.assertGreaterEqual(len(set(poses)),8)
        self.assertEqual(poses[-1],(0,-72))

    def test_dense_short_tween_keeps_bounded_upload_cadence(self):
        d,c=self.fixture();c.update(mode7=True,motion_step=8)
        c['notes']=[dict(time=float(i),speed=1) for i in range(8)]
        d['track_actions']=[dict(floor=1,eventType='MoveTrack',startTile=[0,'Start'],
                                endTile=[7,'Start'],positionOffset=[0,3],duration=.13636)]
        poses=[v[1] for v in motion_schedule(d,c).values() if 1 in v]
        self.assertLessEqual(len(set(poses)),3)

    def test_native_world_units_and_recomputed_event_time(self):
        d,c=self.fixture();d['native_tile_size']=1.5
        d['native_track_effects']=[dict(type='ffxMoveFloorPlus',floor=1,start=1,end=1,
            startTime=143.0,degreeOffset=0,duration=0,targetPos=dict(x=3,y=-1.5),positionUsed=True)]
        self.assertEqual(motion_schedule(d,c),{round(FPS):{1:(48,24)}})

    def test_native_component_duration_uses_local_beat(self):
        from track_motion import native_duration
        d,c=self.fixture();d.update(bpm=120,native_component_notation=True);c['notes'][1]['speed']=2
        self.assertEqual(native_duration(d,c,dict(floor=1,duration=4)),1)

    def test_loss_only_scatter_waits_for_the_later_success_trigger(self):
        d,c=self.fixture();d['track_actions']=[
            dict(floor=1,eventType='SetConditionalEvents',lossTag='fail',perfectTag='NONE'),
            dict(floor=1,eventType='MoveTrack',positionOffset=[0,3],duration=0,eventTag='fail'),
            dict(floor=2,eventType='SetConditionalEvents',perfectTag='pass',hitTag='pass',lossTag='fail'),
            dict(floor=2,eventType='MoveTrack',startTile=[1,'Start'],endTile=[1,'Start'],positionOffset=[2,0],duration=0,eventTag='pass')]
        m=motion_schedule(d,c)
        self.assertNotIn(round(FPS),m)
        self.assertEqual(m[round(2*FPS)],{1:(48,0)})

    def test_decorative_motion_does_not_move_nonsticky_planets(self):
        d=dict(track_settings=dict(stickToFloors='Disabled'),track_actions=[
            dict(floor=1,eventType='PositionTrack',stickToFloors='Enabled',justThisTile='Enabled'),
            dict(floor=3,eventType='PositionTrack',stickToFloors='Enabled',justThisTile='Disabled')])
        self.assertEqual(stick_schedule(d,5),[False,True,False,True,True])

    def test_move_targets_use_start_position_after_position_track(self):
        d,c=self.fixture();c['notes']=[dict(n,x=i*24,y=0) for i,n in enumerate(c['notes'])]
        d['track_actions']=[dict(floor=1,eventType='PositionTrack',positionOffset=[0,1],justThisTile=True),
                            dict(floor=1,eventType='MoveTrack',positionOffset=[0,-1],duration=0)]
        m=motion_schedule(d,c)
        self.assertEqual(m[0][1],(0,-24))
        # scnGame.PrepVfx captures startPos after ApplyEventsToFloors.
        self.assertEqual(m[round(FPS)][1],(0,0))
        self.assertNotIn(2,m.get(round(FPS),{}))

    def test_null_axis_does_not_cancel_another_running_axis(self):
        d,c=self.fixture();d['track_actions']=[
            dict(floor=0,eventType='MoveTrack',positionOffset=[2,None],duration=2),
            dict(floor=1,eventType='MoveTrack',startTile=[0,'Start'],endTile=[0,'Start'],positionOffset=[None,1],duration=0)]
        m=motion_schedule(d,c);x=y=0
        for at,ups in m.items():
            if at>round(2*FPS):break
            if 0 in ups:x,y=ups[0]
        self.assertEqual((x,y),(48,-24))

    def fixture(self):return {'bpm':60,'track_settings':{},'track_actions':[]},{'notes':[{'time':float(i),'speed':1} for i in range(4)]}
    def test_range_translation_and_screen_y(self):
        d,c=self.fixture();d['track_actions']=[dict(floor=1,eventType='MoveTrack',startTile=[0,'ThisTile'],endTile=[1,'ThisTile'],positionOffset=[2,1],duration=1,ease='Linear')]
        m=motion_schedule(d,c)
        self.assertEqual(m[round(2*FPS)],{1:(48,-24),2:(48,-24)})
        self.assertTrue(all(1<=i<=2 for updates in m.values() for i in updates))
    def test_a_later_target_is_relative_to_start_not_cumulative(self):
        d,c=self.fixture();d['track_actions']=[dict(floor=i,eventType='MoveTrack',startTile=[1,'Start'],endTile=[1,'Start'],positionOffset=[x,None],duration=0) for i,x in [(1,2),(2,1)]]
        m=motion_schedule(d,c);self.assertEqual(m[round(FPS)][1],(48,0));self.assertEqual(m[round(2*FPS)][1],(24,0))
    def test_easing_endpoints(self):
        for name in ['Linear','InQuad','OutCubic','InOutSine','InExpo','OutCirc','InOutBack']:
            self.assertAlmostEqual(easing(name,0),0);self.assertAlmostEqual(easing(name,1),1)
    def test_nearby_graphics_apply_latest_offset_when_a_floor_approaches(self):
        c={'notes':[dict(frame=i*60) for i in range(10)]}
        full={60:{8:(24,0)},180:{8:(48,0)},300:{8:(72,0)}}
        visible=nearby_motion(c,full)
        self.assertNotIn(8,visible.get(60,{}))
        self.assertEqual(visible[240][8],(48,0))
        self.assertEqual(visible[300][8],(72,0))
        self.assertEqual(full[60][8],(24,0))
    def test_three_planet_arc_uses_original_sixty_degree_correction(self):
        raw=dict(settings=dict(bpm=60,offset=0),angleData=[0,0,0,0],actions=[dict(floor=1,eventType='MultiPlanet',planets='ThreePlanets')])
        d=normalize_json(raw,dict(id=1,code='TEST',title='TEST',text='test'));c,_=compile_chart(d)
        self.assertAlmostEqual(c['notes'][2]['time']-c['notes'][1]['time'],2/3)

if __name__=='__main__':unittest.main()
