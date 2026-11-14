import sys,struct,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from animation_bulk import HEADER,records
from animation_catchup import compile_stream,unpack_events,state

class Catchup(unittest.TestCase):
    def test_every_target_keeps_exact_state_and_checkpoint_entries(self):
        chart=dict(id=71,cell_coordinates=[[i,0] for i in range(4)],
                   catchup_every_frame=True,catchup_ranges=[(4,18)],catchup_widths=[2,4,8])
        data=bytearray()
        for t in range(24):
            for i in range(4):data+=HEADER.pack(t,0,i,(t+i)%8)
            data+=HEADER.pack(t,10,t,2*t)
        data+=HEADER.pack(65535,255,0,0)
        out,mapping,report=compile_stream(data,chart)
        self.assertGreater(report['windows'],0)
        for p,e,t,k,i,v in records(data):
            self.assertEqual(out[mapping[p]:mapping[p]+7],data[p:p+7])
        for target in range(24):
            expected=b''.join(data[p:e] for p,e,t,k,i,v in records(data) if t<=target)
            selected=bytearray();p=0
            while p<len(out):
                _,end,t,k,i,v=next(records(out[p:]))
                if t>target:break
                if k==21:p+=7 if target>=i else end
                elif k==22:p+=7+i
                else:selected+=out[p:p+end];p+=end
            self.assertEqual(state(unpack_events(expected,chart)),state(unpack_events(selected,chart)),target)
