"""Hardware-emulated regression checks; requires a Snes9x libretro core."""
import json
import ctypes as C
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from emulate import Emulator

class Cartridge(unittest.TestCase):
    def test_header_and_checksum(self):
        rom=(ROOT/'build/campaign/adofai.sfc').read_bytes()
        self.assertEqual(len(rom),8388608)
        self.assertEqual(rom[0x40FFD5],0x35)
        self.assertEqual(int.from_bytes(rom[0x40FFFC:0x40FFFE],'little'),0x8000)
        complement=int.from_bytes(rom[0x40FFDC:0x40FFDE],'little')
        checksum=int.from_bytes(rom[0x40FFDE:0x40FFE0],'little')
        self.assertEqual(complement^checksum,65535)
        self.assertEqual(sum(rom)&65535,checksum)
    def test_chart_milestones(self):
        d=json.loads((ROOT/'build/campaign/level1.json').read_text());n=d['notes']
        self.assertEqual(len(n),168)
        self.assertAlmostEqual(n[1]['time'],1.63)
        self.assertAlmostEqual(n[-1]['time'],75.23,places=4)
        self.assertEqual([v['step'] for v in n if v['flags']&2],[161])
        self.assertAlmostEqual(n[-1]['time']-n[-2]['time'],1.6,places=4)

class Playing(unittest.TestCase):
    def setUp(self):
        self.em=Emulator(rom=ROOT/'build/campaign/adofai.sfc')
        self.notes=json.loads((ROOT/'build/campaign/level1.json').read_text())['notes']
        for _ in range(90):self.em.run()
        self.assertGreater(self.em.read('tick'),80)
    def tearDown(self):self.em.close()
    def press(self,button):
        self.em.run([button]);self.em.run()
    def start(self,button=3):
        self.press(button)
        if button!=3:self.press(3)
        self.wait(lambda:self.em.read('music_active')==1,180)
    def wait(self,predicate,limit=5200):
        for _ in range(limit):
            if predicate():return
            self.em.run()
        self.fail('Emulated state did not arrive: '+str(self.em.snapshot()))
    def play_to(self,step=167,offset=0):
        for _ in range(5100):
            s=self.em.snapshot()
            if s['step']>=step:return
            self.assertEqual(s['state'],1,s)
            target=self.notes[s['step']+1]['frame']+s['calibration']+offset
            self.em.run([8] if target<=s['elapsed']+1<=target+2 else [])
        self.fail('Replay did not finish')
    def test_full_controller_replay(self):
        self.start();self.play_to()
        self.assertEqual(self.em.read('state'),3)
        self.assertEqual(self.em.read('combo'),167)
        counts=[C.c_uint16.from_address(self.em.ram+self.em.labels['judgment_counts']+i*2).value for i in range(11)]
        self.assertEqual(sum(counts),167)
        self.assertEqual(self.em.read('perfects'),sum(counts[3:6]))
        self.assertEqual(self.em.read('score_lo')+65536*self.em.read('score_hi'),sum(c*w for c,w in zip(counts,[20,40,75,100,100,100,75,40,20,0,0])))
        self.assertEqual(self.em.read('misses'),0)
    def test_no_input_fails(self):
        self.start();self.wait(lambda:self.em.read('state')==2)
        self.assertEqual(self.em.read('step'),0)
        self.assertIn(self.em.read('timing_error'),range(7,10))
    def test_extra_early_input_is_recoverable(self):
        self.start();target=self.notes[1]['frame']-7
        self.wait(lambda:self.em.read('elapsed')>=target-1)
        self.press(8)
        self.assertEqual(self.em.read('state'),1)
        self.assertGreater(self.em.read('overload'),0)
        self.play_to(4)
        self.assertEqual(self.em.read('state'),1)
        self.assertEqual(self.em.read('misses'),0)
        self.assertEqual(self.em.read('overload'),0)
    def test_holding_button_does_not_repeat(self):
        self.start();self.wait(lambda:self.em.read('elapsed')>=self.notes[1]['frame']-1)
        for _ in range(120):self.em.run([8])
        self.assertEqual(self.em.read('state'),2)
        self.assertEqual(self.em.read('step'),1)
    def test_pause_preserves_song_and_run(self):
        self.start();self.play_to(12);self.press(3)
        self.assertEqual(self.em.read('state'),4)
        before=self.em.read('elapsed')
        for _ in range(120):self.em.run()
        self.assertEqual(self.em.read('elapsed'),before)
        self.press(3);self.play_to()
        self.assertEqual(self.em.read('combo'),167)
        self.assertEqual(self.em.read('misses'),0)
    def test_practice_continues_through_all_misses(self):
        self.start(9);self.wait(lambda:self.em.read('state')==3)
        self.assertEqual(self.em.read('step'),167)
        self.assertEqual(self.em.read('misses'),167)
        self.assertEqual(self.em.read('combo'),0)
    def test_autoplay_completes(self):
        self.start(1);self.wait(lambda:self.em.read('state')==3)
        self.assertEqual(self.em.read('combo'),167)
        self.assertEqual(self.em.read('perfects'),167)
    def test_retry_resets_attempt_and_retains_best(self):
        self.start();self.play_to(20);self.press(2)
        self.wait(lambda:self.em.read('step')==0 and self.em.read('elapsed')<10)
        self.assertEqual(self.em.read('combo'),0)
        self.assertGreaterEqual(self.em.read('best'),20)
        self.wait(lambda:self.em.read('state')==2)
        self.press(3)
        self.wait(lambda:self.em.read('state')==1 and self.em.read('music_active')==1)
        self.assertEqual(self.em.read('misses'),0)
    def test_offset_setting_and_clamps(self):
        for _ in range(15):self.press(7)
        self.assertEqual(self.em.read('calibration',True),8)
        for _ in range(20):self.press(6)
        self.assertEqual(self.em.read('calibration',True),-8)
        for _ in range(11):self.press(7)
        self.assertEqual(self.em.read('calibration',True),3)
        self.start();self.play_to(20)
        self.assertEqual(self.em.read('combo'),20)
    def test_pause_exit_and_normal_restart(self):
        self.start(9);self.press(3);self.press(2)
        self.assertEqual(self.em.read('state'),0)
        self.start(8)
        self.assertEqual(self.em.read('practice'),0)
        self.assertEqual(self.em.read('autoplay'),0)

if __name__=='__main__':unittest.main(verbosity=2)
