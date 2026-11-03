"""Expansion regressions against cartridge output and real pad input."""
import json,sys,unittest,ctypes as C
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from emulate import Emulator
from campaign_assets import connected_track,compile_chart,OUT
from official_catalog import WORLDS,PACKS,load_game_json

class Campaign(unittest.TestCase):
    def test_catalog_coverage(self):
        self.assertEqual(len(WORLDS),39)
        self.assertEqual(sorted(n for p in PACKS.values() for n in p['levels']),list(range(1,40)))
        self.assertEqual(load_game_json('{"text":"comma, } inside a string",}'),{'text':'comma, } inside a string'})
    def test_pause_and_automatic_midspin_timing(self):
        import math
        floors=[dict(seqID=i,entryangle=math.pi*1.5,exitangle=math.pi*.5,speed=1.,isCCW=0,extraBeats=0.,midSpin=0,holdLength=-1,numPlanets=2) for i in range(4)]
        floors[1]['extraBeats']=3
        data=dict(id='test',title='TEST',bpm=120,offset=0,countdown=4,separate_countdown=True,floors=floors)
        c,_=compile_chart(data)
        self.assertEqual([n['time'] for n in c['notes']],[0,2,4,4.5])
        self.assertEqual(c['notes'][1]['pause_frames'],90)
        floors[1]['extraBeats']=0;floors[1]['midSpin']=1;floors[1]['exitangle']=floors[1]['entryangle']
        c,_=compile_chart(data)
        self.assertEqual([n['time'] for n in c['notes']],[0,2,2,2.5])
        self.assertEqual(c['hits'],2)
    def test_complete_charts_and_events(self):
        counts=[167,145,160,172,165,359,196,318,319,283,433,326]
        ends=[75.230,60.938,58.058,115.765,59.924,125.129,82.875,87.900,97.286,83.333,121.865,90.808]
        for level,(count,end) in enumerate(zip(counts,ends),1):
            c=json.loads((OUT/f'level{level}.json').read_text());notes=c['notes']
            self.assertEqual(c['steps'],count);self.assertAlmostEqual(notes[-1]['time'],end,places=3)
            self.assertTrue(all(a['frame']<b['frame'] for a,b in zip(notes,notes[1:])))
            self.assertTrue(all((n['rate']<0)==n['ccw'] for n in notes))
            self.assertLessEqual(c['track_tiles'],1024)
        c=json.loads((OUT/'level7.json').read_text())
        self.assertGreater(sum(bool(n['flags']&4) for n in c['notes']),10)
        flags=[n['flags'] for level in range(1,10) for n in json.loads((OUT/f'level{level}.json').read_text())['notes']]
        self.assertTrue(any(f&1 for f in flags));self.assertTrue(any(f&2 for f in flags))
    def test_shared_track_borders(self):
        # Three centers form a straight strip: one seam halfway between each,
        # no extra node boxes or outlines cutting through either rectangle.
        c={'id':'test','notes':[{'x':128+i*24,'y':144} for i in range(3)]}
        connected_track(c)
        from PIL import Image
        a=np.array(Image.open(OUT/'leveltest-track.png'))
        self.assertEqual(np.where(a[144,116:189]==2)[0].tolist(),[24,48])
        self.assertEqual(np.where(a[144,116:189]==3)[0].tolist(),[0,72])
        self.assertTrue(np.all(a[138,117:188]>0))
        self.assertTrue(np.all(a[136,116:189]==0))
        (OUT/'leveltest-track.png').unlink()

class PadFixture(unittest.TestCase):
    def setUp(self):
        self.em=Emulator(rom=OUT/'adofai.sfc')
        for _ in range(120):self.em.run()
    def tearDown(self):self.em.close()
    def press(self,b):self.em.run([b]);self.em.run()
    def timing(self,b):
        self.press(0)
        while self.em.read('settings_row')!=2:self.press(5)
        self.press(b);self.press(3)
    def wait(self,p,limit=1500):
        for _ in range(limit):
            if p():return
            self.em.run()
        self.fail(str(self.em.snapshot()))

class Calibration(PadFixture):
    def test_all_taps_are_acknowledged(self):
        self.press(2)
        for i,b in enumerate([8,0,9,1,10,11,4,5,6,7,8,0,9,1,10,11]):
            self.press(b);self.assertEqual(self.em.read('cal_count'),i+1)
        self.assertEqual(self.em.read('state'),6)
        self.assertEqual(self.em.read('skipped_commits'),0)
    def test_menu_second_page_and_wrap(self):
        for n in range(1,12):
            self.press(5);self.assertEqual(self.em.read('selected_level'),n)
            self.assertEqual(self.em.read('state'),0)
            self.assertEqual(self.em.read('menu_first'),0 if n<9 else 9)
        self.press(5);self.assertEqual(self.em.read('selected_level'),0)
        self.press(4);self.assertEqual(self.em.read('selected_level'),11)
    def test_measured_offset_apply_retry_cancel(self):
        self.press(2);last=-1
        for _ in range(900):
            ticks=self.em.read('audio_ticks');beat=(ticks-20)//125;phase=(ticks-20)%125
            tap=ticks>=125 and phase<5 and beat!=last
            if tap:last=beat
            self.em.run([8] if tap else [])
            if self.em.read('state')==6:break
        self.assertEqual(self.em.read('cal_count'),16)
        self.assertIn(self.em.read('cal_recommend',True),range(5,8))
        self.press(9);self.assertEqual(self.em.read('state'),5);self.assertEqual(self.em.read('cal_count'),0)
        self.press(2);self.assertEqual(self.em.read('state'),0);self.assertEqual(self.em.read('calibration'),0)
        for _ in range(3):self.press(7)
        self.press(3);self.wait(lambda:self.em.read('music_active')==1)
        self.wait(lambda:self.em.read('elapsed')>20)
        self.assertEqual(self.em.read('elapsed')-self.em.read('chart_time'),3)
        # Both orbit and judgment reach the first tile at the corrected clock.
        chart=json.loads((OUT/'level1.json').read_text())
        for _ in range(600):
            s=self.em.snapshot()
            if s['step']>=12:break
            target=chart['notes'][s['step']+1]['frame']+3
            self.em.run([8] if target<=s['elapsed']+1<=target+2 else [])
        self.assertEqual(self.em.read('step'),12);self.assertEqual(self.em.read('misses'),0)

class CheckpointsAndTiming(PadFixture):
    def test_simultaneous_buttons_are_independent_timestamped_taps(self):
        chart=json.loads((OUT/'level1.json').read_text());self.press(3)
        self.wait(lambda:self.em.read('music_active')==1)
        # Two real notes in the same controller poll, as in dense tech rolls.
        C.c_uint16.from_address(self.em.ram+0x4004).value=chart['first_frame']
        self.wait(lambda:self.em.read('elapsed')>=chart['first_frame']-1)
        self.em.run([8,0])
        self.wait(lambda:self.em.read('step')>=2,20)
        self.assertEqual(self.em.read('combo'),2)
        self.assertEqual(self.em.read('misses'),0)
        self.assertEqual(self.em.read('tap_head'),self.em.read('tap_tail'))
        for _ in range(5):self.em.run([8,0])
        self.assertEqual(self.em.read('combo'),2) # Holding is not another tap.
    def test_accepted_late_landings_never_charge_overload_and_retry_resets(self):
        chart=json.loads((OUT/'level1.json').read_text());self.press(3)
        for _ in range(1100):
            s=self.em.snapshot()
            if s['step']>=15:break
            target=chart['notes'][s['step']+1]['frame']+5
            self.em.run([8 if s['step']%2==0 else 0] if target<=s['elapsed']+1<=target+2 else [])
        self.assertEqual(self.em.read('state'),1)
        self.assertEqual(self.em.read('step'),15)
        self.assertEqual(self.em.read('overload'),0)
        self.wait(lambda:self.em.read('state')==2)
        self.press(3);self.wait(lambda:self.em.read('music_active')==1)
        self.assertEqual(self.em.read('overload'),0)
        self.assertEqual(self.em.read('fail_reason'),0)
    def test_difficulty_cycles_and_changes_judgment(self):
        self.assertEqual(self.em.read('difficulty'),1)
        self.assertEqual(self.em.read('hit_window'),5)
        self.timing(10)
        self.assertEqual(self.em.read('difficulty'),0)
        self.assertEqual(self.em.read('hit_window'),3)
        self.timing(10)
        self.assertEqual(self.em.read('difficulty'),2)
        self.assertEqual(self.em.read('hit_window'),7)
        self.timing(11);self.assertEqual(self.em.read('difficulty'),0)
        self.timing(11);self.assertEqual(self.em.read('difficulty'),1)
        self.press(3)
        chart=json.loads((OUT/'level1.json').read_text())
        target=chart['notes'][1]['frame']+5
        self.wait(lambda:self.em.read('elapsed')>=target-1)
        self.press(8)
        self.wait(lambda:self.em.read('state')==1)
        self.assertEqual(self.em.read('state'),1)
        self.assertEqual(self.em.read('step'),1)
        self.assertEqual(self.em.read('overload'),0)
        self.assertEqual(self.em.read('feedback'),8)
    def test_clustered_extra_taps_overload(self):
        chart=json.loads((OUT/'level1.json').read_text());self.press(3)
        self.wait(lambda:self.em.read('elapsed')>=chart['first_frame']-8)
        for b in (8,0,9,1):self.em.run([b])
        self.assertEqual(self.em.read('state'),2)
        self.assertEqual(self.em.read('fail_reason'),2)
    def test_strict_and_looser_use_distinct_deadlines(self):
        chart=json.loads((OUT/'level1.json').read_text())
        self.timing(10);self.press(3) # Strict's outer allowance is four frames.
        self.wait(lambda:self.em.read('elapsed')>=chart['first_frame']+5)
        self.assertEqual(self.em.read('state'),2)
        self.press(2);self.wait(lambda:self.em.read('state')==0)
        self.timing(11);self.timing(11);self.press(3)
        self.wait(lambda:self.em.read('elapsed')>=chart['first_frame']+6)
        self.press(8)
        self.assertEqual(self.em.read('state'),1)
        self.assertEqual(self.em.read('step'),1)
        self.assertEqual(self.em.read('feedback'),8)
    def test_original_flags_retry_and_full_restart(self):
        chart=json.loads((OUT/'level3.json').read_text())
        self.assertEqual([(c['trigger'],c['floor']) for c in chart['checkpoints']],[(96,96)])
        self.assertTrue(chart['notes'][96]['flags']&64)
        self.press(5);self.press(5);self.press(3)
        for _ in range(3000):
            s=self.em.snapshot()
            if s['step']>=96:break
            target=chart['notes'][s['step']+1]['frame']
            self.em.run([8 if s['step']%2==0 else 0] if target<=s['elapsed']+1<=target+2 else [])
        self.assertEqual(self.em.read('checkpoint_floor'),96)
        self.wait(lambda:self.em.read('state')==2)
        self.em.run();self.em.run()
        frozen=tuple(self.em.read(k) for k in ('cam_x','cam_y','angle','chart_time'))
        for _ in range(30):self.em.run()
        self.assertEqual(frozen,tuple(self.em.read(k) for k in ('cam_x','cam_y','angle','chart_time')))
        self.assertEqual(self.em.read('display_state'),2)
        self.press(3)
        self.wait(lambda:self.em.read('state')==1)
        self.assertEqual(self.em.read('state'),1)
        self.assertEqual(self.em.read('step'),96)
        self.assertEqual(self.em.read('checkpoint_preroll'),1)
        self.assertEqual(self.em.read('music_origin'),chart['checkpoints'][0]['origin_frame'])
        self.wait(lambda:self.em.read('state')==2)
        self.press(2);self.wait(lambda:self.em.read('state')==0)
        self.press(3) # Returning to the menu then START is a full restart.
        self.wait(lambda:self.em.read('state')==1 and self.em.read('music_active')==1)
        self.assertEqual(self.em.read('step'),0)
        self.assertEqual(self.em.read('checkpoint_floor'),0)
        self.assertEqual(self.em.read('music_origin'),0)
    def test_looser_early_boundary_after_count_in(self):
        chart=json.loads((OUT/'level1.json').read_text())
        self.timing(10);self.timing(10);self.press(3)
        self.wait(lambda:self.em.read('elapsed')>=chart['first_frame']-10)
        self.em.run([8]);self.em.run([0]);self.em.run()
        self.assertEqual(self.em.read('state'),1)
        self.assertEqual(self.em.read('step'),1)
        self.assertIn(self.em.read('last_error',True),(-8,-7))
        self.assertEqual(self.em.read('overload'),0)
    def test_imported_offsets_and_duplicate_checkpoint_events(self):
        from import_official import normalize_json
        source=load_game_json((ROOT/'build/catalog/text-3064.json').read_text())
        c=normalize_json(source,next(m for m in WORLDS if m['id']==26))
        compiled,_=compile_chart(c)
        self.assertIn((806,814),[(c['trigger'],c['floor']) for c in compiled['checkpoints']])
        self.assertIn((946,945),[(c['trigger'],c['floor']) for c in compiled['checkpoints']])
        source=load_game_json((ROOT/'build/catalog/text-2975.json').read_text())
        c=normalize_json(source,next(m for m in WORLDS if m['id']==23))
        self.assertEqual(len(c['checkpoints']),4)

if __name__=='__main__':unittest.main(verbosity=2)
