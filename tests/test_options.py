"""Real-pad checks for presentation, statistics, and run options."""
import ctypes as C,json,sys,unittest
from pathlib import Path
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
from emulate import Emulator
from input_helpers import press,wait,configure

class Options(unittest.TestCase):
    def setUp(self):
        self.em=Emulator(rom=ROOT/'build/campaign/adofai.sfc')
        for _ in range(120):self.em.run()
    def tearDown(self):self.em.close()
    def counts(self):
        return [C.c_uint16.from_address(self.em.ram+self.em.labels['judgment_counts']+2*i).value for i in range(11)]
    def image(self,name):
        for _ in range(5):self.em.run()
        p=ROOT/'build'/name;self.em.capture(p);return np.array(Image.open(p))
    def test_speed_steps_bounds_and_time_attack_toggle(self):
        press(self.em,0);self.assertEqual(self.em.read('state'),7)
        press(self.em,7);self.assertEqual(self.em.read('time_attack'),1)
        press(self.em,6);self.assertEqual(self.em.read('time_attack'),0)
        press(self.em,5);press(self.em,7)
        self.assertEqual(self.em.read('speed_tenths'),11)
        press(self.em,6);self.assertEqual(self.em.read('speed_tenths'),10)
        for _ in range(7):press(self.em,6)
        self.assertEqual(self.em.read('speed_tenths'),5)
        self.assertEqual(self.em.read('speed_pitch'),768)
        for _ in range(17):press(self.em,7)
        self.assertEqual(self.em.read('speed_tenths'),20)
        self.assertEqual(self.em.read('speed_pitch'),3072)
    def test_orb_colors_are_independent_and_visible(self):
        press(self.em,0)
        a=self.image('options-default.png')
        for _ in range(3):press(self.em,5)
        press(self.em,7);b=self.image('options-fire-color.png')
        self.assertEqual(self.em.read('fire_color'),1)
        self.assertEqual(self.em.read('ice_color'),1)
        self.assertFalse(np.array_equal(a[140:156,96:112],b[140:156,96:112]))
        self.assertTrue(np.array_equal(a[140:156,144:160],b[140:156,144:160]))
        press(self.em,5);press(self.em,7);c=self.image('options-both-colors.png')
        self.assertTrue(np.array_equal(b[140:156,96:112],c[140:156,96:112]))
        self.assertFalse(np.array_equal(b[140:156,144:160],c[140:156,144:160]))
        self.assertEqual(self.em.read('palette_dirty'),0)
    def test_time_attack_disables_checkpoints_and_pause_stops_timer(self):
        configure(self.em,11,True)
        press(self.em,5);press(self.em,5);press(self.em,1);press(self.em,3)
        wait(self.em,lambda:self.em.read('step')>=100,3500)
        self.assertEqual(self.em.read('checkpoint_floor'),0)
        self.assertGreater(self.em.read('run_centis'),1000)
        press(self.em,3);self.assertEqual(self.em.read('state'),4)
        before=self.em.read('run_centis')
        for _ in range(60):self.em.run()
        self.assertEqual(self.em.read('run_centis'),before)
        press(self.em,3);wait(self.em,lambda:self.em.read('run_centis')>before)
    def test_results_count_and_weight_each_judgment(self):
        press(self.em,1);press(self.em,3);wait(self.em,lambda:self.em.read('state')==3,5200)
        self.assertEqual(self.counts(),[0,0,0,0,167,0,0,0,0,0,0])
        self.assertEqual(self.em.read('score_lo'),16700)
        self.assertEqual(self.em.read('score_hi'),0)
        self.image('new-results.png')
        # Verify visible numeric map cells, including their text palette.
        p=self.em.ram+0x800+(6+4)*64+16*2
        words=[C.c_uint16.from_address(p+i*2).value for i in range(4)]
        self.assertEqual(''.join(chr(w&255) for w in words),'0167')
        self.assertTrue(all(w&0x1c00 for w in words))
    def test_calibration_keeps_fractional_precision_at_half_speed(self):
        configure(self.em,5)
        press(self.em,7) # One real-frame offset is half a chart frame.
        press(self.em,1)
        press(self.em,3)
        wait(self.em,lambda:self.em.read('elapsed')>10 and self.em.read('frame_ready')==1)
        raw=self.em.read('clock_song_frames')+self.em.read('clock_song_frac')/65536
        fraction=self.em.read('chart_frac')
        corrected=self.em.read('chart_time')-(fraction>=32768)+fraction/65536
        self.assertAlmostEqual(raw-corrected,.5,places=4)
    def test_gameplay_buttons_cannot_start_or_restart_a_song(self):
        for b in [8,9,1]:press(self.em,b)
        self.assertEqual(self.em.read('state'),0)
        press(self.em,1) # Return Watch to Normal before starting.
        press(self.em,3);wait(self.em,lambda:self.em.read('state')==2,600)
        self.assertEqual(self.counts()[9],1)
        for b in [8,0,9,1,10,11,4,5,6,7]:
            press(self.em,b);self.assertEqual(self.em.read('state'),2)
        press(self.em,3);wait(self.em,lambda:self.em.read('state')==1 and self.em.read('music_active'))
        self.assertEqual(sum(self.counts()),0)
    def test_level_select_speed_waits_for_start(self):
        press(self.em,11);self.assertEqual(self.em.read('speed_tenths'),11)
        press(self.em,10);self.assertEqual(self.em.read('speed_tenths'),10)
        press(self.em,1);self.assertEqual(self.em.read('autoplay'),1)
        for _ in range(120):self.em.run()
        self.assertEqual(self.em.read('state'),0)
        press(self.em,3);wait(self.em,lambda:self.em.read('state')==3,5200)
        for b in [8,0,9,1,10,11]:
            press(self.em,b);self.assertEqual(self.em.read('state'),3)

if __name__=='__main__':unittest.main(verbosity=2)
