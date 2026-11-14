import json
import hashlib
import tempfile
import struct
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from import_featured import FEATURED,read_chart
from campaign_assets import compile_chart
from menu_sets import groups


class FeaturedImportTests(unittest.TestCase):
    def test_firestix_selection_has_variants_without_night_wander(self):
        from import_firestix import FIRESTIX
        ids={m['workshop'] for m in FIRESTIX}
        self.assertEqual(len(ids),15)
        self.assertTrue({'2117970100','2118312031'}<=ids)
        self.assertNotIn('2719493511',ids)
        levels=[1,34,35,36,37,38]+[m['id'] for m in FIRESTIX]
        self.assertEqual(sorted(i for _,members in groups(levels) for i in members),list(range(len(levels))))

    def test_hidden_speed_symbols_leave_chart_timing_unchanged(self):
        from import_official import normalize_json
        raw=dict(settings=dict(bpm=120,offset=0),angleData=[0,0,0,0],actions=[
            dict(floor=1,eventType='SetSpeed',speedType='Bpm',beatsPerMinute=240),
            dict(floor=2,eventType='SetSpeed',speedType='Bpm',beatsPerMinute=60)])
        data=normalize_json(raw,dict(id=1,code='TEST',title='TEST',text='test'))
        visible,original=compile_chart(data)
        data['hidden_icons']=[False,True,True,False,False]
        hidden,packed=compile_chart(data);count=len(hidden['notes'])
        self.assertEqual(original[:7*count],packed[:7*count])
        self.assertEqual(original[8*count:],packed[8*count:])
        self.assertEqual(hidden['notes'][1]['flags'],visible['notes'][1]['flags']|128)
        self.assertEqual(hidden['notes'][2]['flags'],visible['notes'][2]['flags']|128)
        self.assertEqual([n['speed'] for n in hidden['notes']],[n['speed'] for n in visible['notes']])

    def test_projection_keeps_pattern_ids_above_65535(self):
        from projected_tracks import Source
        with tempfile.TemporaryDirectory() as folder:
            out=Path(folder)
            (out/'patterns77.bin').write_bytes(bytes(65536*64)+bytes([32])*64)
            (out/'timeline77.bin').write_bytes(b'')
            chart=dict(map_width=1,map_height=1,pattern_initial=[65536],
                       cell_coordinates=[],visibility_offsets=[],pattern_versions=[],
                       track_palette_versions=[[0,0,31]],camera_follow_versions=[[0,0,-32]],
                       camera_sampling_versions=[[0,256,0],[1,0,0],[2,256,0]])
            (out/'level77.json').write_text(json.dumps(chart))
            source=Source(out,77);pixels=source.screen(0)
            self.assertEqual(int(source.palette[pixels[33,0]]),31)
            self.assertEqual(int(pixels[41,0]),0)
            self.assertFalse(source.screen(1).any())
            self.assertTrue((source.screen(2)==pixels).all())

    def test_selected_revisions_and_wave(self):
        self.assertEqual({m['workshop'] for m in FEATURED if m['wave']==1},
                         {'2731815380','2731825935','2731817282'})
        self.assertEqual(FEATURED[0]['workshop'],'2970486324')
        menu=groups([1,62,63,64,65,66,75,76,77,78])
        self.assertEqual(sorted(i for _,indices in menu for i in indices),list(range(10)))

    def test_endless_moving_platform_entry_and_native_grid(self):
        path=ROOT/'assets/private/level75.json'
        if not path.exists():self.skipTest('Owner Workshop import required')
        data=json.loads(path.read_text());chart,_=compile_chart(data)
        region,=chart['freeroam_regions']
        self.assertEqual(region['entry'],[48,-48])
        self.assertIn(tuple(region['entry']),region['cells'])
        self.assertNotIn((0,0),region['cells'])
        self.assertEqual(region['twirls'],[[192,-96],[192,-120]])
        self.assertLess(region['return_start'],region['end'])
        self.assertEqual(data['source_sha256'],hashlib.sha256(Path(data['source']).read_bytes()).hexdigest())

    def test_download_is_never_rewritten_by_separator_repair(self):
        path=ROOT/'assets/private/level75.json'
        if not path.exists():self.skipTest('Owner Workshop import required')
        source=Path(json.loads(path.read_text())['source'])
        before=source.read_bytes();raw,repairs=read_chart(source)
        self.assertEqual(before,source.read_bytes())
        self.assertEqual(len(raw['angleData']),540)

    def test_missing_member_separator_repair_is_explicit(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'main.adofai'
            path.write_text('{"actions":[]\n\t"decorations":[]}')
            before=path.read_bytes();raw,repairs=read_chart(path)
            self.assertEqual(raw,dict(actions=[],decorations=[]))
            self.assertEqual(repairs,['Inserted missing separator before decorations member'])
            self.assertEqual(path.read_bytes(),before)

    def test_rom_tables_preserve_maze_entry_exit_and_radius_transition(self):
        path=ROOT/'assets/private/level75.json'
        if not path.exists():self.skipTest('Owner Workshop import required')
        from track_motion import motion_schedule
        from neo_runtime_assets import binary_tables
        data=json.loads(path.read_text());chart,_=compile_chart(data)
        chart.update(mode7=True,motion_step=1);motion_schedule(data,chart)
        with tempfile.TemporaryDirectory() as folder:
            out=Path(folder);(out/'level75.json').write_text(json.dumps(chart))
            blob,labels=binary_tables(out,[75])
        self.assertEqual(struct.unpack_from('<hh',blob,labels['neo_free_entries']),(48,-48))
        self.assertEqual(struct.unpack_from('<hh',blob,labels['neo_free_records']+20),(336,-96))
        count=struct.unpack_from('<H',blob,labels['neo_ease_counts'])[0]
        records=list(struct.iter_unpack('<4H',blob[labels['neo_ease_records']:labels['neo_ease_records']+count*8]))
        for step,start,duration,index in records:
            if step!=385:continue
            sizes=struct.unpack_from('<'+str(duration+1)+'H',blob,labels['neo_ease_radii']+index*2)
            self.assertEqual((sizes[0],sizes[-1]),(256,512))
            self.assertTrue(any(256<s<512 for s in sizes))
            break
        else:self.fail('Missing radius transition before floor 386')
        self.assertEqual(struct.unpack_from('<H',blob,labels['neo_note_margins']+386*2)[0],50)


if __name__=='__main__':unittest.main()
