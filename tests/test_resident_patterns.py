import io
import json
import struct
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from animation_bulk import HEADER,records
from resident_patterns import compact,changes,future_intervals,prepare


class ResidentPatterns(unittest.TestCase):
    def setUp(self):
        self.pixels=b''.join(bytes([v])*64 for v in range(4))

    def pattern(self,t,slot,raw):
        return HEADER.pack(t,4,slot,raw)+bytes(4)+self.pixels[raw*64:(raw+1)*64]

    def test_tags_preserve_timestamps_and_active_lists(self):
        batch=b''.join(struct.pack('<HH',slot,raw)+self.pixels[raw*64:(raw+1)*64]
                       for slot,raw in ((2,2),(3,3),(4,1)))
        data=(self.pattern(0,1,1)+HEADER.pack(0,14,0,2)+bytes([0,1])+
              HEADER.pack(50,20,0,3)+batch+bytes(14)+
              HEADER.pack(50,14,0,4)+bytes([0,2,3,4])+HEADER.pack(65535,255,0,0))
        output,mapping=compact(data,self.pixels)
        self.assertEqual(list(changes(output)),list(changes(data)))
        self.assertLess(len(output),len(data)//3)
        self.assertEqual({mapping[p] for p,*_ in records(data)},
                         {p for p,*_ in records(output)})

    def test_future_lifetimes_follow_raw_identity_across_slots(self):
        data=(self.pattern(0,1,1)+HEADER.pack(0,14,0,2)+bytes([0,1])+
              self.pattern(50,2,2)+HEADER.pack(50,14,0,3)+bytes([0,1,2])+
              HEADER.pack(54,14,0,2)+bytes([0,1])+HEADER.pack(65535,255,0,0))
        self.assertEqual(future_intervals(data,[0]*256),[[10,2,50,53]])

    def test_checkpoint_cursors_relocate_without_changing_snapshot_pixels(self):
        data=self.pattern(0,1,1)+self.pattern(50,1,2)+HEADER.pack(65535,255,0,0)
        with tempfile.TemporaryDirectory() as folder,redirect_stdout(io.StringIO()):
            p=Path(folder)
            chart=dict(pattern_initial=[0]*256,checkpoints=[{}],animation_bytes=len(data))
            (p/'level23.json').write_text(json.dumps(chart))
            (p/'patterns23.bin').write_bytes(self.pixels)
            (p/'animation23.bin').write_bytes(data)
            snapshot=b'ADS5'+struct.pack('<I',75)+bytes(10)+self.pixels
            cp=p/'animation23-checkpoint-0.bin';cp.write_bytes(snapshot)
            prepare(p,23)
            updated=cp.read_bytes()
            self.assertEqual(struct.unpack_from('<I',updated,4)[0],7)
            self.assertEqual(updated[8:],snapshot[8:])
            once=(p/'animation23.bin').read_bytes();prepare(p,23)
            self.assertEqual((p/'animation23.bin').read_bytes(),once)

    def test_wrong_dictionary_cannot_silently_change_graphics(self):
        data=self.pattern(0,1,1)+HEADER.pack(65535,255,0,0)
        with self.assertRaises(AssertionError):compact(data,bytes(len(self.pixels)))


if __name__=='__main__':unittest.main()
