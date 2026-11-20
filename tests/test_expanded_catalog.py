import json
import sys
import unittest
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from import_official import normalize_json
from menu_sets import groups, groups_for_pack
from import_yangsy import YANGSY


class ExpandedCatalogTests(unittest.TestCase):
    def test_main_ex_has_its_own_ordered_set_and_retired_bonus_is_excluded(self):
        from official_catalog import PACKS,RETIRED_LEVEL_IDS
        from import_main_ex import MAIN_EX
        self.assertEqual([m['code'] for m in MAIN_EX],[f'{i}-EX' for i in range(1,13)])
        self.assertNotIn(39,PACKS['jokes']['levels'])
        self.assertIn(39,RETIRED_LEVEL_IDS)
        levels=[94]+[m['id'] for m in reversed(MAIN_EX)]
        sets=dict(groups(levels))
        self.assertEqual([levels[i] for i in sets['MAIN EX LEVELS']],list(range(239,251)))
        self.assertEqual([levels[i] for i in sets['JOKE WORLDS']],[94])

    def test_partial_scale_keeps_other_axis_tween_running(self):
        from track_motion import scale_schedule
        from make_assets import FPS
        data=dict(bpm=120,track_actions=[
            dict(floor=0,eventType='MoveTrack',duration=2,scale=[200,None]),
            dict(floor=1,eventType='MoveTrack',duration=2,scale=[None,300],
                 startTile=[0,'Start'],endTile=[0,'Start'])])
        chart=dict(motion_step=1,notes=[dict(time=0,speed=1),dict(time=.25,speed=1)])
        changes=scale_schedule(data,chart)
        at=round(.5*FPS)
        x,y=changes[at][0]
        self.assertAlmostEqual(x,1+at/FPS,places=4)
        self.assertAlmostEqual(y,1+2*(at/FPS-.25),places=4)

    def test_negative_authored_zoom_keeps_signed_projection(self):
        from track_camera import mode7_zoom_schedule
        chart = dict(code='TEST', projected_zoom_range=True,
                     camera_zoom_versions=[[0, 256, 256], [1, -512, -128], [2, 0, 0], [3, 4608, 14]])
        mode7_zoom_schedule(chart)
        self.assertEqual(chart['camera_sampling_versions'], [[0, 256, 0], [1, -512, 0], [2, 0, 0], [3, 4608, 0]])
        self.assertEqual(chart['camera_projection_versions'], [[0, 256, 0], [1, -128, 0], [2, 0, 0], [3, 14, 0]])

    def test_replay_uses_the_menu_in_the_built_rom(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder)
            (p/'pack.json').write_text(json.dumps({'levels': [1, 75, 95]}))
            (p/'tables.inc').write_text(
                'menu_set_starts: .word 0,2\n'
                'menu_set_counts: .word 1,2\n'
                'menu_level_indices: .word 2,1,0\n'
                'menu_set_name0: .byte "OLD JOKES",0\n'
                'menu_set_name1: .byte "OLD FEATURED",0\n')
            self.assertEqual(groups_for_pack(p), [('OLD JOKES', [2]), ('OLD FEATURED', [1, 0])])

    def test_yangsy_is_separate_and_unique(self):
        self.assertEqual(len(YANGSY), len({m['workshop'] for m in YANGSY}))
        self.assertTrue(all(m['author'] == 'Yangsy56302' for m in YANGSY))
        levels = [1, 62, 75, 95] + [m['id'] for m in YANGSY]
        menu = dict(groups(levels))
        self.assertEqual([levels[i] for i in menu['YANGSY CURSED LEVELS']],
                         [m['id'] for m in YANGSY])
        self.assertEqual([levels[i] for i in menu['COMMUNITY']], [62])
        self.assertEqual(sorted(i for indices in menu.values() for i in indices), list(range(len(levels))))

    def test_mid_floor_tempo_carries_final_speed(self):
        raw = dict(settings=dict(bpm=120, offset=0), angleData=[0, 0, 0], actions=[
            dict(floor=1, eventType='SetSpeed', speedType='Bpm', beatsPerMinute=240, angleOffset=90)])
        data = normalize_json(raw, dict(id=1, code='TEST', title='TEST', text='test'))
        # Half a beat at 120 BPM followed by half a beat at 240 BPM = .375s.
        self.assertAlmostEqual(data['floors'][1]['speed'], 4 / 3)
        self.assertEqual(data['floors'][2]['speed'], 2)

    def test_disabled_strings_do_not_enable_gameplay_events(self):
        raw = dict(settings=dict(bpm=120, offset=0), angleData=[0] * 5, actions=[
            dict(floor=0, eventType='Twirl', active='Disabled'),
            dict(floor=0, eventType='AutoPlayTiles', enabled='Enabled'),
            dict(floor=2, eventType='AutoPlayTiles', enabled='Disabled')])
        data = normalize_json(raw, dict(id=1, code='TEST', title='TEST', text='test'))
        self.assertFalse(any(f['isCCW'] for f in data['floors']))
        self.assertEqual([f['auto'] for f in data['floors']], [1, 1, 0, 0, 0, 0])

    def test_auto_section_starts_on_its_event_floor(self):
        raw = dict(settings=dict(bpm=165, offset=0), angleData=[0]*8, actions=[
            dict(floor=2, eventType='AutoPlayTiles', enabled=True),
            dict(floor=4, eventType='AutoPlayTiles', enabled=False),
            dict(floor=6, eventType='AutoPlayTiles', enabled=True),
            dict(floor=7, eventType='AutoPlayTiles', enabled=False)])
        data=normalize_json(raw,dict(id=295,code='WT-X',title='TEST',text='test'))
        self.assertEqual([f['auto'] for f in data['floors']],[0,0,1,1,0,0,1,0,0])


if __name__ == '__main__':
    unittest.main()
