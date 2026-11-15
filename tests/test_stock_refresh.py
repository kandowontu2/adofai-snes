import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from official_catalog import load_game_json
from import_official import normalize_json
from campaign_assets import compile_chart
from import_yangsy import YANGSY
from decoration_hitboxes import standard_route_decoration, visual_maze_decorations


class StockRefreshTests(unittest.TestCase):
    def test_maze_visuals_keep_revisions_separate(self):
        objects=[dict(tag=tag,decorationImage=image) for tag,image in
                 [('redspinny','pulsebar.png'),('mine','gearmltemp.png'),
                  ('minePt2','gearmltemp.png'),('mine','triangle.png'),
                  ('pp mine','gearmltemp.png')]]
        def tags(level):
            return [d['tag'] for d in visual_maze_decorations(
                dict(id=level,featured_decorations=objects))['featured_decorations']]
        self.assertEqual(tags(75),['minePt2'])
        self.assertEqual(tags(251),['minePt2'])

    def test_original_endless_reality_is_in_community(self):
        from menu_sets import groups
        sets=dict(groups([75,251]))
        self.assertEqual(sets['COMMUNITY'],[1])
        self.assertNotIn(0,sets['COMMUNITY'])

    def test_rotating_bar_is_not_on_featured_maze_route(self):
        bar = {'tag': 'ppnt redspinny'}
        self.assertFalse(standard_route_decoration({'id': 75}, bar))
        self.assertTrue(standard_route_decoration({'id': 251}, bar))
        for tag in ('mine', 'redsweep rs1'):
            self.assertTrue(standard_route_decoration({'id': 75}, {'tag': tag}))

    def test_selected_yangsy_charts_only(self):
        wanted={*(f'YS{i}-X' for i in (11,12,15,18,26,27,29,32,35,36,37,40,41,42,43,45,47)),
                'YA16-X','YA17-X','YA18-X'}
        self.assertEqual({r['code'] for r in YANGSY},wanted)

    def test_embedded_json_extra_commas_preserve_strings(self):
        self.assertEqual(load_game_json('{"x":false, , "text":", ,",}'),
                         dict(x=False,text=', ,'))

    def test_gems_style_applies_outside_named_neo_chapters(self):
        raw=dict(settings=dict(bpm=120,offset=0,trackStyle='Standard'),
                 angleData=[0]*6,actions=[
                     dict(floor=1,eventType='ColorTrack',trackStyle='Gems',justThisTile=True),
                     dict(floor=3,eventType='ColorTrack',trackStyle='Gems',justThisTile=False),
                     dict(floor=5,eventType='ColorTrack',trackStyle='Standard',justThisTile=False)])
        data=normalize_json(raw,dict(id=999,code='CUSTOM',title='Custom',text='test'))
        data.update(track_settings=raw['settings'],track_actions=raw['actions'])
        chart,_=compile_chart(data)
        self.assertEqual([i for i,n in enumerate(chart['notes']) if n.get('gem_platform')],
                         [1,3,4])


if __name__=='__main__':unittest.main()
