import sys,random,struct,unittest
sys.path.insert(0,'tools')
from sa1_stream import pack_time_index,unpack_time_index
class TimeIndexTests(unittest.TestCase):
 def test_all_lengths_and_patterns(self):
  rng=random.Random(834)
  for count in (1,2,63,64,65,1024,16384):
   for kind in range(4):
    values=[(i if kind==0 else i//7 if kind==1 else rng.randrange(65536) if kind==2 else 65535) for i in range(count)]
    raw=struct.pack('<'+'H'*count,*values)
    packed=pack_time_index(raw)
    self.assertEqual(unpack_time_index(packed,count),raw)
 def test_small_run_storage(self):
  raw=struct.pack('<4096H',*range(4096))
  self.assertLess(len(pack_time_index(raw)),1024)
if __name__=='__main__':unittest.main()
