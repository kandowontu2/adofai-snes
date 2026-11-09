import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from import_official import normalize_json
from campaign_assets import compile_chart

class Multitap(unittest.TestCase):
    def test_authored_count_is_local_to_its_floor(self):
        raw=dict(settings=dict(bpm=120,offset=0),angleData=[0,0,0],
                 actions=[dict(floor=1,eventType='Multitap',taps=2)])
        data=normalize_json(raw,dict(id=1,code='TEST',title='TEST',text='test'))
        chart,blob=compile_chart(data)
        self.assertEqual([n['taps_needed'] for n in chart['notes']],[1,2,1,1])
        self.assertEqual(chart['hits'],3,'Multitap grades one completed landing')
        self.assertEqual(blob[11*len(chart['notes'])+1]&248,8)
        self.assertEqual(chart['notes'][1]['frame'],compile_chart(normalize_json(dict(raw,actions=[]),dict(id=1,code='TEST',title='TEST',text='test')))[0]['notes'][1]['frame'])

if __name__=='__main__':unittest.main()
