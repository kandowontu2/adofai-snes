import struct,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from compact_snapshot_seeds import compact,trim_map


class CompactSeeds(unittest.TestCase):
    def test_zero_map_tail_round_trips_and_nonzero_tail_is_rejected(self):
        prefix=struct.pack('<HH',9,320)+bytes(96)
        mapping=bytes([7])*1472+bytes(2624);tail=bytes(range(256))*2
        seed=struct.pack('<I',4)+prefix+mapping+tail
        result=trim_map(seed)
        self.assertEqual(result,struct.pack('<I',4)+prefix+mapping[:1472]+tail)
        at=4+len(prefix)+1472
        self.assertEqual(result[:at]+bytes(2624)+result[at:],seed)
        damaged=bytearray(seed);damaged[4+len(prefix)+1500]=1
        with self.assertRaises(AssertionError):trim_map(damaged)

    def test_preserves_visible_pixels_and_trailing_symbols(self):
        for wide,glyph_bytes,flags in ((False,320,0),(False,9000,0x4000),
                                      (False,5000,0x8000),(True,20000,0),(True,19424,1)):
            with self.subTest(wide=wide,glyph_bytes=glyph_bytes,flags=flags):
                atlas=bytes(range(256))*(160 if wide else 128)
                prefix=struct.pack('<HH',123,glyph_bytes|flags)+bytes(42 if flags&0x8000 else 0)+bytes(96+4096)
                tail=struct.pack('<H',4)+b'abcd'
                before=struct.pack('<I',4)+prefix+atlas+tail
                after=compact(before,wide=wide)
                retained=glyph_bytes+32
                self.assertEqual(after,struct.pack('<I',4)+prefix+atlas[:retained]+tail)
                self.assertLess(len(after),len(before))

    def test_upgrades_legacy_aligned_seeds_without_reencoding_any_live_bytes(self):
        for wide,glyph_bytes,flags in ((False,9000,0x4000),(True,19424,1)):
            atlas=bytes(range(256))*(160 if wide else 128)
            prefix=struct.pack('<HH',7,glyph_bytes|flags)+bytes(96+4096)
            tail=struct.pack('<H',4)+b'ABCD'
            aligned=(glyph_bytes+32+4095)&~4095
            old=struct.pack('<I',4)+prefix+atlas[:aligned]+tail
            expected=struct.pack('<I',4)+prefix+atlas[:glyph_bytes+32]+tail
            self.assertEqual(compact(old,wide=wide,previous=True),expected)


if __name__=='__main__':unittest.main()
