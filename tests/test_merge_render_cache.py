import json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from merge_render_cache import merge


class RenderCacheMergeTests(unittest.TestCase):
    def test_snapshot_files_with_digits_and_off_reference_are_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'source';source.mkdir()
            target=Path(tmp)/'target';target.mkdir()
            chart=dict(id=111,steps=1,hits=1,checkpoints=[],offset=0,duration=2,
                       notes=[dict(frame=0),dict(frame=1)],last_frame=1,
                       mode1_snapshot=True,snapshot_postroll=120,snapshot_frames=122,
                       compact_snapshot_seeds=1,stream_packets=1,stream_msu_base=100,
                       mode1_seed_base=200,mode1_glyph_count=0)
            for folder in (source,target):
                (folder/'level111.json').write_text(json.dumps(chart))
                (folder/'level111.brr').write_bytes(b'music')
                for prefix in ('mode1_seeds','stream_data','stream_index','patterns','timeline','track_map','chart'):
                    (folder/f'{prefix}111.bin').write_bytes(folder.name.encode())
            merge(source,target,111,preserve_vfx_off=True)
            self.assertEqual((target/'mode1_seeds111.bin').read_bytes(),b'source')
            self.assertEqual((target/'mode1_seeds_vfx_off111.bin').read_bytes(),b'target')
            self.assertEqual((target/'vfx-off-111/patterns111.bin').read_bytes(),b'target')
            merge(source,target,111,preserve_vfx_off=True)
            self.assertEqual((target/'mode1_seeds_vfx_off111.bin').read_bytes(),b'target')
            self.assertEqual(json.loads((target/'level111.json').read_text())['vfx_off']['stream_msu_base'],100)


if __name__=='__main__':unittest.main()
