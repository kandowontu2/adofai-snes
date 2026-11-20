import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from build_sa1 import load_build_chart


class BuildMetadataTests(unittest.TestCase):
    def test_expanded_viewport_counters_do_not_overwrite_worker_code(self):
        from verify_sa1_layout import verify_icon_scratch
        verify_icon_scratch(32,0x100,0x220,0x1e2)
        verify_icon_scratch(16,0x100,0x240,0x1e2)
        with self.assertRaisesRegex(AssertionError,'counters overlap'):
            verify_icon_scratch(16,0x100,0x220,0x1e2)
        with self.assertRaisesRegex(AssertionError,'copy-parent'):
            verify_icon_scratch(16,0x100,0x240,0x241)

    def test_snapshot_build_omits_only_offline_pixel_history_in_memory(self):
        data=dict(id=1,mode1_snapshot=True,projection_cells=[[1,2,[[0,4]]]],
                  projected_spill_frames=[dict(frame=1,glyphs='00')],render_viewports={'0':[0,0,32,24]},
                  notes=[dict(frame=30)],snapshot_map_top=16,stream_packets=42)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'level1.json';path.write_text(json.dumps(data))
            before=path.read_bytes();actual=load_build_chart(path)
            self.assertEqual(actual,{k:v for k,v in data.items() if k not in
                                   ('projection_cells','projected_spill_frames','render_viewports')})
            self.assertEqual(path.read_bytes(),before)
            from msu_assets import write_chart_metadata
            actual['stream_msu_base']=1234
            write_chart_metadata(Path(directory),actual)
            self.assertEqual(json.loads(path.read_text()),dict(data,stream_msu_base=1234))
