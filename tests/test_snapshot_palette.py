import json,struct,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from animation_bulk import HEADER,records
from projected_snapshots import write
from snapshot_palette import replace_palette
from projected_tracks import raw_seeds


class SnapshotPaletteTests(unittest.TestCase):
    def test_metadata_only_color_change_is_compiled_and_reindex_keeps_pixels(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);c=dict(code='COLOR',notes=[dict(frame=64)],pattern_initial=[0]*256,
                               track_palette_versions=[[0,0,100],[32,0,200]])
            (p/'level1.json').write_text(json.dumps(c))
            (p/'animation1.bin').write_bytes(HEADER.pack(0,7,0,100)+HEADER.pack(65535,255,0,0))
            write(p,p,1,[bytes(32),bytes([1])*32],[({0:(1,0)},((32,),))]*65,postroll=0)
            index=(p/'stream_index1.bin').read_bytes();data=(p/'stream_data1.bin').read_bytes()
            def colors(idx,stream):
                found=[]
                for _,_,choice in list(struct.iter_unpack('<HHI',idx))[:-1]:
                    _,size,offset=struct.unpack_from('<HHI',stream,choice)
                    found.extend((t,i,v) for a,b,t,k,i,v in records(stream[offset:offset+size]) if k==7)
                return found
            self.assertIn((32,0,200),colors(index,data))
            c.update(mode1_tracks=3,mode1_projected=True,mode1_snapshot=True)
            changed=dict(c,track_palette_versions=c['track_palette_versions']+[[48,0,300]])
            new_index,new_data=replace_palette(index,data,changed)
            self.assertIn((48,0,300),colors(new_index,new_data))
            # Restart atlas, palettes/selectors and map pixels are unchanged.
            before=raw_seeds(index,data,snapshot=True);after=raw_seeds(new_index,new_data,snapshot=True)
            count=struct.unpack_from('<I',before)[0]//4
            a=list(struct.unpack_from('<'+str(count)+'I',before))+[len(before)]
            b=list(struct.unpack_from('<'+str(count)+'I',after))+[len(after)]
            for i in range(count):self.assertEqual(before[a[i]+2:a[i+1]],after[b[i]+2:b[i+1]])
