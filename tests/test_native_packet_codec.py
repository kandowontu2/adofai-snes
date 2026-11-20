import struct,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from animation_bulk import HEADER,records
from native_packet_codec import compress_packet,expand_packet,compact_prefix,coordinate_filter,END


class NativePacketCompression(unittest.TestCase):
    def test_coordinate_predictions_wrap_and_reset_for_each_independent_run(self):
        scalars=b''.join(HEADER.pack(5,kind,i,value) for kind,i,value in
            [(2,4,65530),(3,4,4),(2,5,10),(3,5,65530)])
        values=[65530,10,26,42,58]
        bulk=HEADER.pack(6,17,7,len(values))+struct.pack('<5H',*values)+bytes(7*(len(values)-1)-10)
        raw=scalars+bulk+END
        filtered=coordinate_filter(raw)
        self.assertEqual(struct.unpack_from('<H',filtered,2*7+5)[0],16)
        self.assertEqual(struct.unpack_from('<5H',filtered,len(scalars)+7),(65530,16,16,16,16))
        self.assertEqual(coordinate_filter(filtered,restore=True),raw)
        self.assertEqual(coordinate_filter(filtered,restore=True),raw)

    def test_predicted_lengths_are_restored_before_walking_payloads(self):
        first=HEADER.pack(10,17,2,5)+struct.pack('<5H',100,110,120,130,140)+bytes(18)
        second=HEADER.pack(10,17,9,3)+struct.pack('<3H',65530,4,14)+bytes(8)
        palette=b''.join(HEADER.pack(10,7,i,0x1234+i) for i in range(32,42))
        raw=first+palette+second+END
        filtered=coordinate_filter(raw)
        self.assertEqual(HEADER.unpack_from(filtered,len(first)+len(palette))[3],65534)
        self.assertEqual(coordinate_filter(filtered,restore=True),raw)
        packed,_=compress_packet(raw)
        self.assertEqual(expand_packet(packed),raw)

    def test_all_native_records_survive_on_both_sides_of_patchable_pose_references(self):
        native=HEADER.pack(9,28,0,1024)+bytes(1024)
        pose=HEADER.pack(9,42,0,100)+struct.pack('<I',12345)
        raw=native+pose+native+END
        packed,count=compress_packet(raw)
        self.assertEqual(count,2)
        self.assertLess(len(packed),len(raw)//3)
        self.assertEqual(expand_packet(packed),raw)
        refs=[a for a,b,t,k,i,v in records(packed) if k==42]
        self.assertEqual(len(refs),1)
        changed=bytearray(packed);struct.pack_into('<I',changed,refs[0]+7,98765)
        self.assertEqual(expand_packet(changed),native+HEADER.pack(9,42,0,100)+struct.pack('<I',98765)+native+END)

    def test_due_times_skip_counts_and_all_chained_chunks_survive_relocation(self):
        raw=HEADER.pack(10,28,0,1024)+bytes(1024)+END
        tail=HEADER.pack(11,28,0,1024)+bytes([1])*1024+END
        prefix=bytearray(64)
        first=len(prefix);prefix+=raw+struct.pack('<H',len(tail))+tail
        for j in range(4):struct.pack_into('<HHI',prefix,j*8,11,len(raw)|32768,first|(3<<28))
        packed,patches,stats=compact_prefix(prefix,2)
        self.assertFalse(patches)
        self.assertLess(len(packed),len(prefix))
        for j in range(4):
            time,size,tagged=struct.unpack_from('<HHI',packed,j*8)
            self.assertEqual((time,tagged>>28),(11,3))
            at=tagged&0xfffffff;length=size&32767
            self.assertTrue(size&32768)
            self.assertEqual(expand_packet(packed[at:at+length]),raw)
            at+=length;size=struct.unpack_from('<H',packed,at)[0];at+=2
            self.assertFalse(size&32768)
            self.assertEqual(expand_packet(packed[at:at+size]),tail)
        self.assertEqual(stats['native_lz4_blocks'],2)


if __name__=='__main__':unittest.main()
