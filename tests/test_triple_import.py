import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from import_official import normalize_json

class TripleImportTests(unittest.TestCase):
    def test_collection_has_one_separate_menu_category(self):
        from import_triple_planet import TRIPLE_PLANET
        from menu_sets import groups
        ids=[m['id'] for m in TRIPLE_PLANET]
        self.assertEqual(len(ids),31)
        self.assertEqual(len({m['workshop'] for m in TRIPLE_PLANET}),31)
        sets=dict(groups([1,*ids,284]))
        self.assertEqual(sets['TRIPLE PLANET WORLDS'],list(range(1,32)))
        self.assertEqual(sets['COMMUNITY'],[32])

    def test_numeric_planet_events_match_named_events_at_midspins(self):
        def chart(values):
            raw=dict(settings=dict(bpm=120,offset=0),angleData=[0,999,120,240,0],
                     actions=[dict(floor=2,eventType='MultiPlanet',planets=values[0]),
                              dict(floor=4,eventType='MultiPlanet',planets=values[1])])
            return normalize_json(raw,dict(id=253,code='TEST',title='TEST',text='test',neo_cosmos=True))
        numeric=chart((3,2));named=chart(('ThreePlanets','TwoPlanets'))
        self.assertEqual(numeric['floors'],named['floors'])
        self.assertEqual([f['numPlanets'] for f in numeric['floors']],[2,3,3,3,2,2])

if __name__=='__main__':unittest.main()
