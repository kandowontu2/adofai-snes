"""Resolution changes preserve lifetimes and independent gameplay coordinates."""
import struct, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from track_mipmaps import mipmap_history
from track_camera import mode7_zoom_schedule
from animation_assets import generate

class TrackMipmaps(unittest.TestCase):
    def test_resolution_transition_clears_old_cells_and_preserves_disappearance(self):
        chart = dict(camera_raster_shift_versions=[[0, 0], [10, 1], [30, 0]])
        tiles, history = mipmap_history(chart, [bytes(64), bytes([2])*64], {(4, 2): [(0, 1), (20, 0)]})
        def state(frame):
            result = {}
            for cell, rows in history.items():
                value = 0
                for at, candidate in rows:
                    if at <= frame: value = candidate
                if value: result[cell] = tiles[value]
            return result
        self.assertEqual(set(state(9)), {(4, 2)})
        self.assertEqual(set(state(10)), {(2, 1)})
        self.assertEqual(sum(v != 0 for v in state(10)[(2, 1)]), 16)
        self.assertEqual(state(20), {})
        self.assertEqual(state(30), {})

    def test_hysteresis_does_not_change_world_projection(self):
        chart = dict(adaptive_raster=True, camera_zoom_versions=[[0,256,256],[10,512,128],[20,300,218],[30,288,228]])
        mode7_zoom_schedule(chart)
        self.assertEqual(chart['camera_raster_shift_versions'], [[0,0],[10,1],[30,0]])
        self.assertEqual(chart['camera_sampling_versions'][1], [10,256,0])
        self.assertEqual(chart['camera_world_sampling_versions'][1], [10,512,0])
        self.assertEqual(chart['camera_projection_versions'][1], [10,128,0])
        chart['raster_min_shift']=1
        mode7_zoom_schedule(chart)
        self.assertEqual(chart['camera_raster_shift_versions'], [[0,1]])
        self.assertEqual(chart['camera_sampling_versions'][0], [0,128,0])
        self.assertEqual(chart['camera_projection_versions'][0], [0,256,0])

    def test_checkpoint_restores_raster_scale_and_nonsticky_start_position(self):
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder); (out/'track_map77.bin').write_bytes(b'')
            chart = dict(id=77, mode7=True, adaptive_raster=True,
                         notes=[dict(x=100,y=200,stick_to_floor=False,position_track_offset=[20,-30])],
                         visibility_cells=0,visibility_offsets=[],cell_coordinates=[],map_height=0,
                         checkpoints=[dict(origin_frame=64)],camera_follow_versions=[[0,100,200]],
                         camera_rotation_versions=[[0,256,0]],camera_zoom_versions=[[0,512,128]])
            mode7_zoom_schedule(chart); generate(out,chart,b'',b'')
            data = (out/'animation77-checkpoint-0.bin').read_bytes()
            self.assertEqual(data[:4], b'ADS8')
            self.assertEqual(struct.unpack_from('<8H',data,18), (256,0,0,512,128,128,0,1))
            self.assertEqual(struct.unpack_from('<HHB',data,226), (120,170,3))
            self.assertEqual(chart['animation_format'],13)

if __name__ == '__main__': unittest.main()
