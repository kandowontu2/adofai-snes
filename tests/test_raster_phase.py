import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import raster_phase

class RasterPhase(unittest.TestCase):
    def test_large_translation_keeps_bitmap_phase_and_screen_position(self):
        movement={0:{i:(0,0) for i in range(40)},8:{i:(0,-5) for i in range(36)},16:{i:(0,13) for i in range(36)}}
        origins=raster_phase.schedule(movement)
        chart=dict(notes=[dict(x=100+i*24,y=200) for i in range(40)],raster_origin_versions=origins)
        shifted=raster_phase.motion(chart,movement)
        camera=raster_phase.camera([[0,200,100],[12,224,100]],origins)
        for frame in (8,16):
            origin=next(r[1:] for r in reversed(origins) if r[0]<=frame)
            old_camera=(200,100) if frame<12 else (224,100)
            new_camera=next(r[1:] for r in reversed(camera) if r[0]<=frame)
            for i in range(40):
                old=movement[frame].get(i,(0,0));new=shifted[frame][i]
                self.assertEqual(tuple(old[j]-old_camera[j] for j in range(2)),tuple(new[j]-new_camera[j] for j in range(2)))
                if i<36:self.assertEqual(new[1]%8,0)
    def test_small_individual_moves_do_not_shift_entire_world(self):
        self.assertEqual(raster_phase.schedule({4:{1:(3,5)}}),[[0,0,0]])

    def test_twenty_tile_platform_keeps_stationary_tiles_and_camera_aligned(self):
        movement={0:{i:(0,0) for i in range(24)}}
        movement.update({f:{i:(0,-f) for i in range(20)} for f in range(1,25)})
        origins=raster_phase.schedule(movement,min_group=8)
        chart=dict(notes=[dict(x=100+i*24,y=200) for i in range(24)],raster_origin_versions=origins)
        shifted=raster_phase.motion(chart,movement)
        cameras=raster_phase.camera([[0,200,100]],origins)
        actual=[(0,0)]*24
        for frame in range(25):
            for i,p in shifted.get(frame,{}).items():actual[i]=p
            camera=next(r[1:] for r in reversed(cameras) if r[0]<=frame)
            for i in range(24):
                y=-frame if i<20 else 0
                self.assertEqual(actual[i][1]-camera[1],y-100)
                if i<20:self.assertEqual(actual[i][1]%8,0)

if __name__=='__main__':unittest.main()
