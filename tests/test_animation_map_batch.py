import sys,struct,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from animation_bulk import HEADER,records
from animation_map_batch import batch
from animation_catchup import unpack_events

class MapBatch(unittest.TestCase):
    def test_mixed_rows_preserve_alias_order_and_checkpoint_offsets(self):
        chart={'cell_coordinates':[[126,0],[127,0],[128,0],[126,128]]}
        a=HEADER.pack(10,9,0,3)+struct.pack('<HH',126,0)+bytes([1,2,3])
        b=HEADER.pack(10,0,3,4)
        end=HEADER.pack(65535,255,0,0)
        original=a+b+end
        result,mapping=batch(original,chart)
        self.assertEqual(unpack_events(original,chart),unpack_events(result,chart))
        self.assertEqual(list(records(result))[0][3:6],(29,4,20))
        self.assertEqual(mapping[len(a)],0)
        self.assertEqual(mapping[len(a+b)],27)
    def test_batches_stay_within_shared_buffer_and_timestamp(self):
        chart={'cell_coordinates':[[i,0] for i in range(256)]}
        original=b''.join(HEADER.pack(10,0,i,i%255) for i in range(256))+HEADER.pack(11,0,0,2)+HEADER.pack(65535,255,0,0)
        result,_=batch(original,chart)
        self.assertEqual(unpack_events(original,chart),unpack_events(result,chart))
        self.assertTrue(all(i<=128 and v<=640 for _,_,_,k,i,v in records(result) if k==29))
