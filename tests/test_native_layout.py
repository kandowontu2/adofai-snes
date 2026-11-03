"""Native scene placement and the controller's effective sticking setting."""
import math,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from campaign_assets import compile_chart
from track_motion import motion_schedule

class NativeLayout(unittest.TestCase):
    def data(self):
        return dict(id=25,title='TEST',bpm=120,offset=0,countdown=4,separate_countdown=True,
            floors=[dict(seqID=i,entryangle=math.pi*1.5,exitangle=math.pi*.5,speed=1.,isCCW=0,
                extraBeats=0.,midSpin=0,holdLength=-1,numPlanets=2) for i in range(4)])

    def test_separate_authored_sections_preserve_judgment_times(self):
        data=self.data();old,_=compile_chart(data)
        data.update(native_layout_version=2,native_tile_size=1.5,
            native_positions=[[10,20],[11.5,20],[11.5,23],[13,23]])
        chart,_=compile_chart(data)
        self.assertEqual([n['frame'] for n in old['notes']],[n['frame'] for n in chart['notes']])
        self.assertEqual([(n['x_float'],n['y_float']) for n in chart['notes']],[(0,0),(24,0),(24,-48),(48,-48)])

    def test_native_controller_overrides_serialized_floor_sticking(self):
        data=self.data();data['native_stick_to_floors']=[False]*4
        data['native_controller_stick_to_floor']=True
        chart,_=compile_chart(data)
        self.assertTrue(all(n['stick_to_floor'] for n in chart['notes']))
        data['native_controller_stick_to_floor']=False;data['native_stick_to_floors']=[True]*4
        chart,_=compile_chart(data)
        self.assertFalse(any(n['stick_to_floor'] for n in chart['notes']))

    def test_native_motion_is_relative_to_authored_position(self):
        data=self.data();data.update(native_layout_version=2,native_tile_size=1.5,
            native_positions=[[0,0],[1.5,0],[1.5,3],[3,3]],native_controller_stick_to_floor=True,
            native_track_effects=[dict(type='ffxMoveFloorPlus',floor=2,start=2,end=2,
                targetPos=dict(x=0,y=1.5),duration=0,positionUsed=True)])
        chart,_=compile_chart(data);motion=motion_schedule(data,chart)
        self.assertEqual(motion[chart['notes'][2]['frame']][2],(0,-24))
        self.assertEqual(chart['notes'][2]['y_float'],-48)

if __name__=='__main__':unittest.main()
