import json,struct,sys,tempfile,unittest
from unittest.mock import patch
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from animation_bulk import HEADER,records
from projected_snapshots import write
from projected_tracks import snapshot_pose


class SnapshotTests(unittest.TestCase):
    def test_shared_pose_catchup_and_checkpoint_restore_exact_pixels(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'source';source.mkdir();out=Path(tmp)/'out'
            chart=dict(code='TEST',notes=[dict(frame=149)],pattern_initial=[0]*256)
            (source/'level1.json').write_text(json.dumps(chart))
            (source/'animation1.bin').write_bytes(HEADER.pack(0,28,1,2)+struct.pack('<H',17)+HEADER.pack(65535,255,0,0))
            glyphs=[bytes(32),bytes(range(16))+bytes(16),bytes(16)+bytes(range(16)),bytes(range(32))]
            frames=[({607:(1,0)},((32,33),))]*65+[({607:(2,16)},((34,35),))]*35+[({607:(3,32)},((36,37),))]*50
            write(source,out,1,glyphs,frames,postroll=0)
            index=(out/'stream_index1.bin').read_bytes();data=(out/'stream_data1.bin').read_bytes()
            entries=list(struct.iter_unpack('<HHI',index))[:-1]
            self.assertEqual([e[0] for e in entries],[0,65,100])
            pointers=set();catchup=False
            for _,_,choice in entries:
                for j in range(4):
                    t,size,offset=struct.unpack_from('<HHI',data,choice+j*8)
                    if not size:continue
                    pose_refs=[]
                    for a,b,_,k,i,v in records(data[offset:offset+size]):
                        if k!=42:continue
                        pointer=struct.unpack_from('<I',data,offset+a+7)[0];pointers.add(pointer);pose_refs.append(pointer)
                        pt,pk,count,length=HEADER.unpack_from(data,pointer)
                        self.assertEqual(pk,41);self.assertEqual(length+14,v)
                        pal,words,raw=snapshot_pose(data[pointer+7:pointer+7+length],count)
                        self.assertEqual(raw,[glyphs[{0:1,65:2,100:3}[pt]]])
                        self.assertEqual(struct.unpack_from('<H',words,607*2)[0]&1023,1)
                    if j:catchup=True;self.assertEqual(len(pose_refs),1)
            self.assertTrue(catchup);self.assertEqual(len(pointers),3)
            seeds=(out/'mode1_seeds1.bin').read_bytes()
            for seed,glyph in ((1,1),(2,3)):
                at=struct.unpack_from('<I',seeds,seed*4)[0]
                cursor,byte_count=struct.unpack_from('<HH',seeds,at)
                self.assertEqual(byte_count,32)
                atlas=at+4+96+4096
                self.assertEqual(seeds[atlas+32:atlas+64],glyphs[glyph])
                self.assertEqual(seeds[atlas:atlas+32],bytes(32))
                self.assertEqual(seeds[atlas+32768:atlas+32772],struct.pack('<HH',2,17))

    def test_truncated_or_invalid_pose_is_rejected(self):
        for raw in (bytes(1311),bytes(1312)+bytes([3])+bytes(32),bytes(1312)+bytes([0])+bytes(31)):
            with self.assertRaises((AssertionError,IndexError)):snapshot_pose(raw,1)

    def test_raw_copy_pose_and_checkpoint_keep_all_chr_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'source';source.mkdir();out=Path(tmp)/'out'
            chart=dict(code='TEST',notes=[dict(frame=0)],pattern_initial=[0]*256,track_palette_versions=[])
            (source/'level1.json').write_text(json.dumps(chart))
            (source/'animation1.bin').write_bytes(HEADER.pack(65535,255,0,0))
            glyphs=[bytes(32)]+[bytes([i])*32 for i in range(1,242)]
            frames=[({i-1:(i,0) for i in range(1,242)},((32,33),))]
            with patch('projected_copies.actor_events',return_value=[]),patch('projected_copies.palette_events',return_value=[]):
                write(source,out,1,glyphs,frames,copy_world={'first':0,'last':1},postroll=0)
            data=(out/'stream_data1.bin').read_bytes();index=(out/'stream_index1.bin').read_bytes()
            _,_,choice=struct.unpack_from('<HHI',index);_,size,offset=struct.unpack_from('<HHI',data,choice)
            ref=next((a,b,t,k,i,v) for a,b,t,k,i,v in records(data[offset:offset+size]) if k==42)
            pointer=struct.unpack_from('<I',data,offset+ref[0]+7)[0]
            _,kind,count,length=HEADER.unpack_from(data,pointer)
            self.assertEqual((kind,count,length),(44,241,1312+241*32))
            self.assertEqual(data[pointer+7+1312:pointer+7+length],b''.join(glyphs[1:]))
            seeds=(out/'mode1_seeds1.bin').read_bytes();at=struct.unpack_from('<I',seeds,4)[0]
            self.assertEqual(struct.unpack_from('<H',seeds,at+2)[0],0x8000|241*32)
            atlas=at+4+42+96+4096
            self.assertEqual(seeds[atlas+32:atlas+32+241*32],b''.join(glyphs[1:]))

    def test_final_note_and_postroll_are_included(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'source';source.mkdir();out=Path(tmp)/'out'
            (source/'level1.json').write_text(json.dumps(dict(code='TEST',notes=[dict(frame=1)],pattern_initial=[0]*256)))
            (source/'animation1.bin').write_bytes(HEADER.pack(65535,255,0,0))
            glyphs=[bytes(32),bytes([85])*32,bytes([170])*32]
            opening=({0:(1,0)},((32,33),));ending=({0:(2,0)},((32,33),))
            with self.assertRaises(AssertionError):write(source,out,1,glyphs,[opening])
            write(source,out,1,glyphs,[opening]+[ending]*121)
            chart=json.loads((out/'level1.json').read_text())
            self.assertEqual((chart['snapshot_frames'],chart['snapshot_postroll']),(122,120))
            seeds=(out/'mode1_seeds1.bin').read_bytes();at=struct.unpack_from('<I',seeds,4)[0]
            self.assertEqual(seeds[at+4+96+4096+32:at+4+96+4096+64],glyphs[2])
