import math,sys,unittest
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from track_geometry import piece
from track_motion import rotation_schedule
from make_assets import FPS

class TileRotation(unittest.TestCase):
    def schedule(self,actions):
        chart=dict(motion_step=1,notes=[dict(time=float(i),speed=1) for i in range(8)])
        return rotation_schedule(dict(bpm=60,track_actions=actions),chart)

    def sample(self,rows,tile,time):
        value=0
        for f,updates in sorted(rows.items()):
            if f>round(time*FPS):break
            value=updates.get(tile,value)
        return value

    def test_rotation_without_translation(self):
        rows=self.schedule([dict(floor=1,eventType='MoveTrack',rotationOffset=180,duration=1)])
        self.assertAlmostEqual(self.sample(rows,1,1.5),90,delta=2)
        self.assertEqual(self.sample(rows,1,2.1),180)
        self.assertEqual(self.sample(rows,2,2.1),0)

    def test_ranges_repeats_and_null(self):
        rows=self.schedule([
            dict(floor=1,eventType='MoveTrack',rotationOffset=180,duration=0,startTile=[0,'ThisTile'],endTile=[2,'ThisTile'],gapLength=1,eventTag='turn'),
            dict(floor=1,eventType='RepeatEvents',tag='turn',repeatType='Floor',floorCount=1,gapLength=1,executeOnCurrentFloor=True),
            dict(floor=3,eventType='MoveTrack',rotationOffset=None,duration=0)])
        self.assertEqual([self.sample(rows,i,2.1) for i in range(5)],[0,180,180,180,180])

    def test_interruption_completes_previous_rotation(self):
        rows=self.schedule([dict(floor=0,eventType='MoveTrack',rotationOffset=180,duration=4,startTile=[0,'Start'],endTile=[0,'Start']),
                            dict(floor=1,eventType='MoveTrack',rotationOffset=360,duration=2,startTile=[0,'Start'],endTile=[0,'Start'])])
        self.assertAlmostEqual(self.sample(rows,0,1),180,delta=2)

    def test_turn_keeps_own_pivot_and_returns_to_original_shape(self):
        notes=[dict(x=76,y=100,exit_angle=0),dict(x=100,y=100,exit_angle=-math.pi/2),dict(x=100,y=76,exit_angle=-math.pi/2)]
        def pixels(angle):
            x,y,im=piece(notes,1,rotation=angle)
            ys,xs=np.nonzero(np.array(im));return {(x+int(xx),y+int(yy)) for xx,yy in zip(xs,ys)}
        self.assertEqual(pixels(0),pixels(360))
        self.assertIn((88,100),pixels(0));self.assertNotIn((112,100),pixels(0))
        self.assertIn((112,100),pixels(180));self.assertNotIn((88,100),pixels(180))
        self.assertIn((100,100),pixels(180))

if __name__=='__main__':unittest.main()
