"""Legacy chart migration and capacity used by the requested community maps."""
import math,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from import_official import normalize_json
from official_catalog import load_game_json
from campaign_assets import compile_chart

class LegacyCommunity(unittest.TestCase):
    def test_relative_polygon_tokens_follow_original_migration(self):
        raw=dict(pathData='R57',settings=dict(bpm=120,offset=0),actions=[])
        data=normalize_json(raw,dict(id=65,code='TEST',title='TEST',text='test'))
        self.assertAlmostEqual(data['floors'][1]['exitangle'],math.radians(18))
        self.assertAlmostEqual(data['floors'][2]['exitangle'],math.radians(-34))

    def test_legacy_description_newlines_and_trailing_comma(self):
        self.assertEqual(load_game_json('{"description":"one\ntwo",}'),{'description':'one\ntwo'})

    def test_complete_omega_length_fits_without_truncation(self):
        raw=dict(pathData='R'*4283,settings=dict(bpm=240,offset=0),actions=[])
        data=normalize_json(raw,dict(id=65,code='TEST',title='TEST',text='test'))
        chart,blob=compile_chart(data)
        self.assertEqual(len(chart['notes']),4284)
        self.assertEqual(chart['steps'],4283)
        self.assertEqual(len(blob),4284*14)

if __name__=='__main__':unittest.main()
