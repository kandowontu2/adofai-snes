import struct,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from compact_snapshot_seeds import compact


class CompactSeeds(unittest.TestCase):
    def test_preserves_visible_pixels_and_trailing_symbols(self):
        for wide,glyph_bytes,flags in ((False,320,0),(False,9000,0x4000),
                                      (False,5000,0x8000),(True,20000,0)):
            with self.subTest(wide=wide,glyph_bytes=glyph_bytes,flags=flags):
                atlas=bytes(range(256))*(160 if wide else 128)
                prefix=struct.pack('<HH',123,glyph_bytes|flags)+bytes(42 if flags&0x8000 else 0)+bytes(96+4096)
                tail=struct.pack('<H',4)+b'abcd'
                before=struct.pack('<I',4)+prefix+atlas+tail
                after=compact(before,wide=wide)
                retained=(glyph_bytes+32+4095)&~4095
                self.assertEqual(after,struct.pack('<I',4)+prefix+atlas[:retained]+tail)
                self.assertLess(len(after),len(before))


if __name__=='__main__':unittest.main()
