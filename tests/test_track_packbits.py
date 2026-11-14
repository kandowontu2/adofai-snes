import sys,unittest,random
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from track_packbits import encode,decode

class TrackPackbits(unittest.TestCase):
    def test_round_trip_runs_and_literal_boundaries(self):
        rng=random.Random(3)
        for data in (b'',bytes(129),bytes(range(256))*2,bytes([7])*16384,
                     bytes(rng.randrange(4) for _ in range(1000))):
            self.assertEqual(decode(encode(data)),data)

    def test_encoding_matches_exhaustive_shortest_cost(self):
        rng=random.Random(9)
        for size in range(1,150):
            data=bytes(rng.randrange(3) for _ in range(size));cost=[0]*(size+1)
            for i in range(size-1,-1,-1):
                candidates=[1+n+cost[i+n] for n in range(1,min(128,size-i)+1)]
                candidates += [2+cost[i+n] for n in range(1,min(128,size-i)+1)
                               if data[i:i+n]==data[i:i+1]*n]
                cost[i]=min(candidates)
            self.assertEqual(len(encode(data)),cost[0])
