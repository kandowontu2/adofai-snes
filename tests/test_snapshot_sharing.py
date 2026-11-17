import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from animation_bulk import HEADER
from projected_snapshots import write
from projected_tracks import raw_seeds
from snapshot_sharing import share


class SnapshotSharing(unittest.TestCase):
    def test_repeated_pose_keeps_every_timestamp_and_identical_checkpoint_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)
            (p/'level1.json').write_text(json.dumps(dict(code='REPEAT',notes=[dict(frame=128)],pattern_initial=[0]*256)))
            (p/'animation1.bin').write_bytes(HEADER.pack(65535,255,0,0))
            glyphs=[bytes(32),bytes([1])*32,bytes([2])*32]
            a=({0:(1,0)},((32,),));b=({0:(2,0)},((32,),))
            frames=[a]*32+[b]*32+[a]*65
            write(p,p,1,glyphs,frames,postroll=0)
            index=(p/'stream_index1.bin').read_bytes();before=(p/'stream_data1.bin').read_bytes()
            after,saved=share(index,before)
            self.assertGreater(saved,0)
            self.assertEqual(raw_seeds(index,after,snapshot=True),raw_seeds(index,before,snapshot=True))
            again,removed=share(index,after)
            self.assertEqual(again,after);self.assertEqual(removed,0)


if __name__=='__main__':unittest.main()
