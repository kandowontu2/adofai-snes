import json,struct,tempfile,unittest,sys
from pathlib import Path
sys.path.insert(0,'tools')
from projected_snapshots import write
from animation_bulk import HEADER
class WideAtlasTests(unittest.TestCase):
 def test_complete_viewport_and_checkpoint(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp);(p/'level1.json').write_text(json.dumps(dict(code='WIDE',notes=[dict(frame=64)],pattern_initial=[0]*256)))
   (p/'animation1.bin').write_bytes(HEADER.pack(65535,255,0,0))
   glyphs=[bytes(32)]+[struct.pack('<H',i)*16 for i in range(1,609)]
   frame=({i:(i+1,0) for i in range(608)},((32,33),))
   write(p,p,1,glyphs,[frame]*65,postroll=0)
   chart=json.loads((p/'level1.json').read_text());self.assertTrue(chart['wide_snapshot_atlas']);self.assertEqual(chart['mode1_glyph_count'],640)
   seeds=(p/'mode1_seeds1.bin').read_bytes();start=struct.unpack_from('<I',seeds,4)[0]
   self.assertEqual(struct.unpack_from('<H',seeds,start+2)[0],608*32)
   atlas=start+4+96+4096
   self.assertEqual(seeds[atlas+32:atlas+609*32],b''.join(glyphs[1:]))
   self.assertEqual(struct.unpack_from('<H',seeds,atlas+40960)[0],0)
if __name__=='__main__':unittest.main()
