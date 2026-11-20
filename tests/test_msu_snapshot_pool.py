import io,json,struct,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from animation_bulk import HEADER,records
from projected_snapshots import write
from compact_snapshot_seeds import compact,trim_map
from snapshot_seed_references import reference_seeds
from msu_snapshot_pool import SnapshotPool
from native_packet_codec import expand_packet


class GlobalSnapshotPool(unittest.TestCase):
    def test_native_compression_preserves_all_reachable_events_and_pose_references(self):
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/'source';source.mkdir();out=Path(directory)/'out'
            (source/'level1.json').write_text(json.dumps(dict(code='TEST',notes=[dict(frame=129)],pattern_initial=[0]*256)))
            (source/'animation1.bin').write_bytes(HEADER.pack(0,28,0,1024)+bytes(1024)+HEADER.pack(65535,255,0,0))
            glyphs=[bytes(32),bytes([85])*32]
            write(source,out,1,glyphs,[({0:(1,0)},((32,33),))]*130,postroll=0)
            index=(out/'stream_index1.bin').read_bytes();stream=(out/'stream_data1.bin').read_bytes()
            seeds=reference_seeds(trim_map(compact((out/'mode1_seeds1.bin').read_bytes())),index,stream)
            data=io.BytesIO();pool=SnapshotPool(io.BytesIO(),native_lz4=True)
            base,seed_base=pool.write_variant(data,index,stream,seeds)
            report=pool.finish(data);image=data.getvalue();mapping={}
            self.assertGreater(report['native_saved_bytes'],0)
            self.assertGreater(report['native_lz4_blocks'],0)
            for entry,(_,_,choice) in enumerate(list(struct.iter_unpack('<HHI',index))[:-1]):
                for j in range(4):
                    time,size,offset=struct.unpack_from('<HHI',stream,choice+j*8)
                    actual_time,actual_size,actual_offset=struct.unpack_from('<HHI',image,base+entry*32+j*8)
                    self.assertEqual((actual_time,actual_offset>>28),(time,offset>>28))
                    if not size:continue
                    offset&=0xfffffff;actual_offset&=0xfffffff
                    self.assertFalse(size&32768)
                    actual=expand_packet(image[base+actual_offset:base+actual_offset+actual_size])
                    expected=bytearray(stream[offset:offset+size])
                    for a,b,t,kind,_,value in records(expected):
                        if kind!=42:continue
                        local=struct.unpack_from('<I',expected,a+7)[0]
                        runtime=struct.unpack_from('<I',actual,a+7)[0]
                        self.assertEqual(image[base+runtime:base+runtime+value],bytes(2)+stream[local+2:local+value])
                        struct.pack_into('<I',expected,a+7,runtime);mapping[local]=runtime
                    self.assertEqual(actual,expected)
            expected=bytearray(seeds)
            count=struct.unpack_from('<I',seeds)[0]//4
            for at in struct.unpack_from('<'+str(count)+'I',seeds):
                size,local=struct.unpack_from('<HI',seeds,at+4)
                if size:struct.pack_into('<I',expected,at+6,mapping[local])
            self.assertEqual(image[seed_base:seed_base+len(expected)],expected)

    def test_shared_runtime_references_preserve_all_choices_and_restart_poses(self):
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/'source';source.mkdir();out=Path(directory)/'out'
            (source/'level1.json').write_text(json.dumps(dict(code='TEST',notes=[dict(frame=129)],pattern_initial=[0]*256)))
            (source/'animation1.bin').write_bytes(HEADER.pack(0,28,1,2)+b'\x17\x00'+HEADER.pack(65535,255,0,0))
            glyphs=[bytes(32),bytes([85])*32,bytes([170])*32]
            write(source,out,1,glyphs,[({0:(1,0)},((32,33),))]*65+[({607:(2,16)},((34,35),))]*65,postroll=0)
            index=(out/'stream_index1.bin').read_bytes();stream=(out/'stream_data1.bin').read_bytes()
            seeds=reference_seeds(trim_map(compact((out/'mode1_seeds1.bin').read_bytes())),index,stream)
            data=io.BytesIO(b'HEADER');data.seek(6)
            pool=SnapshotPool(io.BytesIO())
            first=pool.write_variant(data,index,stream,seeds)
            second=pool.write_variant(data,index,stream,seeds)
            report=pool.finish(data);image=data.getvalue()
            self.assertGreater(report['saved_bytes'],0)
            removed=(len(index)//8)*512
            self.assertEqual(report['directory_saved_bytes'],removed*2)
            for base,seed_base in (first,second):
                for entry,(_,_,choice) in enumerate(list(struct.iter_unpack('<HHI',index))[:-1]):
                    for j in range(4):
                        _,size,offset=struct.unpack_from('<HHI',stream,choice+8*j)
                        if not size:continue
                        time,new_size,new_offset=struct.unpack_from('<HHI',image,base+entry*32+8*j)
                        self.assertEqual(new_size,size)
                        self.assertEqual(new_offset&0x0fffffff,(offset&0x0fffffff)-removed)
                        for a,b,t,k,_,v in records(stream[offset:offset+size]):
                            if k!=42:continue
                            local=struct.unpack_from('<I',stream,offset+a+7)[0]
                            pointer=struct.unpack_from('<I',image,base+offset-removed+a+7)[0]+base
                            self.assertEqual(image[pointer:pointer+v],bytes(2)+stream[local+2:local+v])
                            self.assertEqual(struct.unpack_from('<H',image,pointer)[0],0)
                count=struct.unpack_from('<I',seeds)[0]//4
                for start in struct.unpack_from('<'+str(count)+'I',seeds):
                    size,local=struct.unpack_from('<HI',seeds,start+4)
                    if not size:continue
                    pointer=struct.unpack_from('<I',image,seed_base+start+6)[0]+base
                    self.assertEqual(image[pointer:pointer+size],bytes(2)+stream[local+2:local+size])
            self.assertEqual(len(image),report['msu_bytes'])


if __name__=='__main__':unittest.main()
