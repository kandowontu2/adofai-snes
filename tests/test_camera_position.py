import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from track_camera import position_schedule
from track_events import gameplay_actions
from make_assets import FPS

class CameraPosition(unittest.TestCase):
    def fixture(self):
        chart={'notes':[dict(x=128+i*24,y=144,time=i,frame=round(i*FPS),speed=1) for i in range(4)]}
        data=dict(bpm=60,track_settings=dict(relativeTo='Player',position=[0,0]),camera_actions=[])
        return data,chart,[(0,0,40),(round(FPS),24,40),(round(2*FPS),48,40)]
    def at(self,rows,frame):return next(r[1:] for r in reversed(rows) if r[0]<=frame)
    def test_tile_camera_holds_authored_floor_instead_of_following_player(self):
        d,c,f=self.fixture();d['camera_actions']=[dict(floor=1,eventType='MoveCamera',relativeTo='Tile',position=[1,0],duration=0)]
        self.assertEqual(self.at(position_schedule(d,c,{},f),round(2*FPS)),(48,40))
    def test_player_camera_resumes_with_authored_offset(self):
        d,c,f=self.fixture();d['camera_actions']=[dict(floor=1,eventType='MoveCamera',relativeTo='Player',position=[1,1],duration=0)]
        self.assertEqual(self.at(position_schedule(d,c,{},f),round(2*FPS)),(72,16))
    def test_low_effects_alternative_is_not_run_with_full_effects(self):
        a=dict(floor=0,eventType='MoveCamera',minVfxOnly=True)
        self.assertEqual(gameplay_actions({'track_actions':[a]}),[])
    def test_last_position_adds_offset_once(self):
        d,c,f=self.fixture();d['camera_actions']=[dict(floor=1,eventType='MoveCamera',relativeTo='Tile',position=[0,0],duration=0),dict(floor=2,eventType='MoveCamera',relativeTo='LastPosition',position=[2,0],duration=0)]
        self.assertEqual(self.at(position_schedule(d,c,{},f),round(2*FPS)),(72,40))
    def test_native_upward_offset_is_not_clamped_to_player(self):
        d,c,f=self.fixture()
        d['native_camera_effects']=[dict(floor=1,targetPos=dict(x=0,y=7.5),
            movementType=0,positionUsed=True,movementTypeUsed=True,duration=0,ease='Linear')]
        self.assertEqual(self.at(position_schedule(d,c,{},f),round(2*FPS)),(48,-80))
    def test_native_tile_camera_stays_fixed_until_player_event(self):
        d,c,f=self.fixture()
        d['native_camera_effects']=[dict(floor=1,targetPos=dict(x=3.75,y=0),
            movementType=1,positionUsed=True,movementTypeUsed=True,duration=0,ease='Linear')]
        self.assertEqual(self.at(position_schedule(d,c,{},f),round(2*FPS)),(84,40))
    def test_last_position_preserves_player_follow_mode(self):
        d,c,f=self.fixture()
        d['camera_actions']=[dict(floor=1,eventType='MoveCamera',relativeTo='LastPosition',position=[1,0],duration=0)]
        self.assertEqual(self.at(position_schedule(d,c,{},f),round(2*FPS)),(72,40))

if __name__=='__main__':unittest.main()
