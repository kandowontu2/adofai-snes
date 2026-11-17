import json,struct,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from animation_bulk import HEADER
from projected_snapshots import write
from compact_snapshot_seeds import compact,trim_map
from snapshot_sharing import share
from snapshot_seed_references import reference_seeds
from snapshot_codec import decode_split


class ReferenceSeeds(unittest.TestCase):
    def test_all_formats_restore_identical_pixels_clones_cursor_and_symbols(self):
        for indexed,wide,count in [(False,False,30),(False,True,540),(True,False,30),(True,True,270)]:
            with self.subTest(indexed=indexed,wide=wide),tempfile.TemporaryDirectory() as directory:
                source=Path(directory)/'source';source.mkdir();out=Path(directory)/'out'
                (source/'level1.json').write_text(json.dumps(dict(code='TEST',notes=[dict(frame=129)],
                    pattern_initial=[0]*256,track_palette_versions=[])))
                symbols=struct.pack('<HH',17,42);clones=bytes(range(20))
                animation=(HEADER.pack(0,28,2,len(symbols))+symbols+HEADER.pack(0,43,2,len(clones))+clones
                    +HEADER.pack(65535,255,0,0))
                (source/'animation1.bin').write_bytes(animation)
                stride=64 if indexed else 32
                glyphs=[bytes(32)]+[struct.pack('<H',i)*(stride//2) for i in range(1,count+1)]
                refs={i:(i+1,(64 if indexed else 0)|(16 if i%2 else 32)) for i in range(count)}
                frames=[(refs,((32,33),))]*130
                with patch('projected_copies.actor_events',return_value=[]),patch('projected_copies.palette_events',return_value=[]):
                    write(source,out,1,glyphs,frames,postroll=0,copy_world={'first':0,'last':129})
                index=(out/'stream_index1.bin').read_bytes()
                stream,_=share(index,(out/'stream_data1.bin').read_bytes())
                seeds=trim_map(compact((out/'mode1_seeds1.bin').read_bytes(),wide=wide))
                result=reference_seeds(seeds,index,stream,wide=wide)
                self.assertLess(len(result),len(seeds)//5)
                offsets=list(struct.unpack_from('<'+str(struct.unpack_from('<I',result)[0]//4)+'I',result))
                for i,start in enumerate(offsets):
                    old_at=struct.unpack_from('<I',seeds,i*4)[0]
                    old_cursor,header=struct.unpack_from('<HH',seeds,old_at)
                    self.assertEqual(result[start:start+46],seeds[old_at:old_at+46])
                    size,pointer=struct.unpack_from('<HI',result,start+46)
                    symbol_size=struct.unpack_from('<H',result,start+52)[0]
                    self.assertEqual(result[start+54:start+54+symbol_size],symbols if i else b'')
                    if not i:
                        self.assertEqual(size,0);continue
                    self.assertEqual(result[start+4:start+46],struct.pack('<H',2)+clones+bytes(20))
                    _,kind,chunks,length=HEADER.unpack_from(stream,pointer)
                    self.assertEqual(size,length+14)
                    raw=decode_split(stream[pointer+7:pointer+7+length],chunks)
                    self.assertEqual(kind,47 if indexed else 46)
                    self.assertEqual(seeds[old_at+46:old_at+46+96],raw[:96])
                    self.assertEqual(seeds[old_at+46+96+256:old_at+46+96+1472],raw[96:1312])
                    self.assertEqual(seeds[old_at+46+96+1472+32:old_at+46+96+1472+32+chunks*32],raw[1312:])
                corrupt=bytearray(seeds);at=struct.unpack_from('<I',corrupt,4)[0]
                corrupt[at+46]^=1
                with self.assertRaises(AssertionError):reference_seeds(corrupt,index,stream,wide=wide)


if __name__=='__main__':unittest.main()
