"""Original trigger timing, opacity ranges, and repeated-floor behavior."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from track_visibility import visibility_schedule
from make_assets import FPS

class Visibility(unittest.TestCase):
    def test_zero_scale_stays_hidden_despite_opacity_restore(self):
        data,chart=self.fixture()
        data['native_track_effects']=[dict(type='ffxMoveFloorPlus',floor=1,start=0,end=0,
            startTime=99,duration=0,scaleUsed=True,targetScale=0,opacityUsed=True,targetOpacity=1)]
        initial,changes=visibility_schedule(data,chart)
        self.assertEqual(self.value(initial,changes,0,2),0)

    def fixture(self):
        return {'bpm':60},{'notes':[{'time':float(i),'speed':1} for i in range(4)]}
    def value(self,initial,changes,i,t):
        value=initial[i]
        for frame,updates in changes.items():
            if frame>round(t*FPS):break
            value=updates.get(i,value)
        return value
    def test_original_beats_ahead_and_next_floor_disappearance(self):
        data,chart=self.fixture()
        data['track_settings']={'trackAnimation':'Fade','trackDisappearAnimation':'Fade','beatsAhead':1,'beatsBehind':0}
        initial,changes=visibility_schedule(data,chart)
        self.assertEqual(initial,[0]*4)
        self.assertEqual(self.value(initial,changes,2,.9),0)
        self.assertEqual(self.value(initial,changes,2,1.4),2)
        self.assertEqual(self.value(initial,changes,2,1.6),3)
        self.assertEqual(self.value(initial,changes,2,3.6),0)
        self.assertEqual(self.value(initial,changes,3,4),3) # Final portal persists.
    def test_native_floor_effects_have_the_same_timing(self):
        data,chart=self.fixture()
        data['native_track_effects']=[{'floor':2,'type':'ffxChangeTrack','animationType':6,'animationType2':6,'tilesAhead':1,'tilesBehind':0}]
        initial,changes=visibility_schedule(data,chart)
        self.assertEqual(initial,[3,3,0,3])
        self.assertEqual(self.value(initial,changes,2,.9),0)
        self.assertEqual(self.value(initial,changes,2,1.6),3)
        self.assertEqual(self.value(initial,changes,2,3.6),0)
    def test_move_track_ranges_and_floor_repetitions(self):
        data,chart=self.fixture();data['track_settings']={}
        data['track_actions']=[{'floor':1,'eventType':'MoveTrack','opacity':0,'startTile':[0,'ThisTile'],'endTile':[0,'ThisTile'],'duration':0,'eventTag':'hide'},
          {'floor':1,'eventType':'RepeatEvents','repeatType':'Floor','floorCount':2,'executeOnCurrentFloor':True,'tag':'hide'}]
        # JSON charts have a settings block even if its animations are None.
        data['track_settings']={'trackAnimation':'None'}
        initial,changes=visibility_schedule(data,chart)
        self.assertEqual(self.value(initial,changes,2,1.5),3)
        self.assertEqual(self.value(initial,changes,2,2.1),0)
        self.assertEqual(self.value(initial,changes,3,3.1),0)
    def test_native_initial_opacity_stays_hidden_until_its_trigger(self):
        data,chart=self.fixture();data['native_track_initial']=[1,0,1,1]
        data['native_track_effects']=[{'floor':2,'type':'ffxMoveFloorPlus','start':1,'end':1,'targetOpacity':1,'opacityUsed':True,'startTime':2,'duration':0}]
        initial,changes=visibility_schedule(data,chart)
        self.assertEqual(self.value(initial,changes,1,1.9),0)
        self.assertEqual(self.value(initial,changes,1,2.1),3)

    def test_ce_tx_outcirc_disappears_before_linear_fade(self):
        data,chart=self.fixture();data['track_settings']={'trackAnimation':'None'}
        data['track_actions']=[dict(floor=1,eventType='MoveTrack',startTile=[-1,'ThisTile'],endTile=[-1,'ThisTile'],duration=12,opacity=0,ease='OutCirc')]
        initial,changes=visibility_schedule(data,chart)
        self.assertEqual(self.value(initial,changes,0,4),1)
        self.assertEqual(self.value(initial,changes,0,7),0)

    def test_interrupted_opacity_completes_prior_target(self):
        data,chart=self.fixture();data['track_settings']={'trackAnimation':'None'}
        data['track_actions']=[dict(floor=0,eventType='MoveTrack',startTile=[0,'Start'],endTile=[0,'Start'],duration=4,opacity=0),dict(floor=1,eventType='MoveTrack',startTile=[0,'Start'],endTile=[0,'Start'],duration=1,opacity=100)]
        initial,changes=visibility_schedule(data,chart)
        self.assertEqual(self.value(initial,changes,0,1.02),0)
        self.assertEqual(self.value(initial,changes,0,2),3)

if __name__=='__main__':unittest.main()
