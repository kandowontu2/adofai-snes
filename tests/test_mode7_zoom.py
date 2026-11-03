"""Hardware sampling, inverse OBJ projection, and checkpoint zoom state."""
import math,struct,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from track_camera import mode7_zoom_schedule,camera_schedule
from animation_assets import generate

class Mode7Zoom(unittest.TestCase):
    def test_projection_inverts_quantized_sampling_at_rotated_zooms(self):
        for zoom in (128,192,256,384,512,640):
            for angle in (0,31,45,90,137,180,270):
                c=round(math.cos(math.radians(angle))*256)
                s=round(math.sin(math.radians(angle))*256)
                chart=dict(camera_rotation_versions=[[0,c,s]],camera_zoom_versions=[[0,zoom,round(65536/zoom)]])
                mode7_zoom_schedule(chart)
                _,a,b=chart['camera_sampling_versions'][0]
                _,p,q=chart['camera_projection_versions'][0]
                # PPU samples [a b;-b a], OBJ projects [p -q;q p].
                self.assertAlmostEqual((a*p+b*q)/65536,1,delta=.009)
                self.assertAlmostEqual((a*q-b*p)/65536,0,delta=.009)
    def test_zoom_alone_creates_camera_matrices(self):
        c=dict(camera_zoom_versions=[[0,512,128],[10,128,512]])
        mode7_zoom_schedule(c)
        self.assertEqual(c['camera_sampling_versions'],[[0,512,0],[10,128,0]])
        self.assertEqual(c['camera_projection_versions'],[[0,128,0],[10,512,0]])
    def test_unsupported_extremes_fail_instead_of_silently_clamping(self):
        for zoom in (0,-256,32,1024):
            with self.assertRaises(ValueError):mode7_zoom_schedule(dict(camera_zoom_versions=[[0,zoom,0]]))
    def test_minimum_vfx_alternative_does_not_override_zoom(self):
        d=dict(bpm=60,camera_actions=[dict(floor=0,eventType='MoveCamera',zoom=200,minVfxOnly=True)])
        c=dict(notes=[dict(time=0,speed=1)])
        self.assertEqual(camera_schedule(d,c),[(0,256,256)])
    def test_checkpoint_contains_both_matrices_zoom_and_trail_rotation(self):
        with tempfile.TemporaryDirectory() as folder:
            out=Path(folder);(out/'track_map77.bin').write_bytes(b'')
            c=dict(id=77,mode7=True,notes=[],visibility_cells=0,visibility_offsets=[],cell_coordinates=[],map_height=0,
                   checkpoints=[dict(origin_frame=64)],camera_follow_versions=[[0,100,200]],
                   camera_rotation_versions=[[0,0,-256]],camera_rotation_phase_versions=[[0,192]],
                   camera_zoom_versions=[[0,512,128]],track_palette_versions=[[0,0,31]])
            mode7_zoom_schedule(c);generate(out,c,b'',b'')
            snap=(out/'animation77-checkpoint-0.bin').read_bytes()
            self.assertEqual(snap[:4],b'ADS7')
            self.assertEqual(struct.unpack_from('<HHhhHHHhhH',snap,14),(100,200,0,-512,192,512,128,0,-128,31))
            self.assertEqual(len(snap),224)
            self.assertEqual(c['animation_format'],12)

if __name__=='__main__':unittest.main()
