import json,struct,sys,tempfile,unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from animation_bulk import HEADER
from projected_snapshots import write,frame_pixels
from snapshot_codec import decode_split
from compact_snapshot_seeds import compact,trim_map
from snapshot_seed_references import reference_seeds


class AlignedSnapshots(unittest.TestCase):
    def test_320_indexed_glyphs_use_external_blank_without_losing_seed_bytes(self):
        glyphs=[bytes(32)]+[struct.pack('<H',i)*16+bytes([0,255])*8+bytes(16) for i in range(1,321)]
        refs={i:(i+1,64) for i in range(320)}
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory);out=source/'out'
            (source/'level1.json').write_text(json.dumps(dict(code='INDEXED320',
                notes=[dict(frame=65)],pattern_initial=[0]*256,
                track_palette_versions=[],snapshot_map_top=16,snapshot_aligned=True)))
            (source/'animation1.bin').write_bytes(HEADER.pack(65535,255,0,0))
            write(source,out,1,glyphs,[(refs,())]*66,postroll=0)
            index=(out/'stream_index1.bin').read_bytes();stream=(out/'stream_data1.bin').read_bytes()
            seeds=trim_map(compact((out/'mode1_seeds1.bin').read_bytes(),wide=True))
            result=reference_seeds(seeds,index,stream,wide=True,map_top=16)
            at=struct.unpack_from('<I',result,4)[0];_,pointer=struct.unpack_from('<HI',result,at+4)
            _,kind,chunks,length=HEADER.unpack_from(stream,pointer)
            self.assertEqual((kind,chunks),(49,640))
            body=decode_split(stream[pointer+7:pointer+7+length],chunks,header_bytes=1440)
            words=struct.unpack_from('<672H',body,96)
            self.assertEqual(words[320:],(1023,)*352)
            local=[bytes(32)]+[body[i:i+64] for i in range(1440,len(body),64)]
            decoded={i:((w&1023)+1,64) for i,w in enumerate(words) if w!=1023}
            self.assertEqual(frame_pixels(decoded,(),local,map_top=16).tobytes(),
                             frame_pixels(refs,(),glyphs,map_top=16).tobytes())

    def test_full_640_cell_frame_and_sparse_successor_keep_pixels_and_restart(self):
        # Every slot is needed in the full frame. The following sparse frame
        # must explicitly clear slot zero, including on checkpoint restore.
        glyphs=[bytes(32)]+[struct.pack('<H',i)*16 for i in range(1,641)]
        full={i:(i+1,0) for i in range(640)}
        sparse={0:(1,0),639:(640,0)}
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory);out=source/'out'
            (source/'level1.json').write_text(json.dumps(dict(code='ALIGNED',
                notes=[dict(frame=129)],pattern_initial=[0]*256,
                track_palette_versions=[],snapshot_map_top=16,snapshot_aligned=True)))
            (source/'animation1.bin').write_bytes(HEADER.pack(65535,255,0,0))
            frames=[(full,(tuple(range(32,47)),))]*65+[(sparse,(tuple(range(32,47)),))]*65
            write(source,out,1,glyphs,frames,postroll=0)
            index=(out/'stream_index1.bin').read_bytes();stream=(out/'stream_data1.bin').read_bytes()
            seeds=trim_map(compact((out/'mode1_seeds1.bin').read_bytes(),wide=True))
            result=reference_seeds(seeds,index,stream,wide=True,map_top=16)
            for seed in (1,2):
                at=struct.unpack_from('<I',result,seed*4)[0]
                size,pointer=struct.unpack_from('<HI',result,at+4)
                _,kind,chunks,length=HEADER.unpack_from(stream,pointer)
                self.assertEqual(kind,48)
                body=decode_split(stream[pointer+7:pointer+7+length],chunks,header_bytes=1440)
                words=struct.unpack_from('<672H',body,96)
                local=[body[i:i+32] for i in range(1440,len(body),32)]
                # Add a separate empty glyph, so the generic independent
                # decoder can address a deliberately nonblank slot zero.
                refs={i:((w&1023)+1,((w>>10)&7)-2) for i,w in enumerate(words) if w}
                actual=frame_pixels(refs,(tuple(range(32,47)),),[bytes(32)]+local,map_top=16)
                expected=frame_pixels(*(frames[64 if seed==1 else 128]),glyphs,map_top=16)
                self.assertEqual(actual.tobytes(),expected.tobytes())
                if seed==2:self.assertEqual(local[0],bytes(32))


if __name__=='__main__':unittest.main()
