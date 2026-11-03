"""Master catalog and actual multi-page menu publication."""
import ctypes as C,json,os,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
from emulate import Emulator
from input_helpers import press,configure
BASE=Path(os.environ.get('ADOFAI_TEST_MASTER',ROOT/'build/packs/master'))

class Master(unittest.TestCase):
    def test_calibration_orbit_moves_without_taps_and_does_not_jump_on_input(self):
        em=Emulator(rom=BASE/'adofai.sfc')
        try:
            for _ in range(120):em.run()
            press(em,2)
            angles=[]
            for frame in range(240):
                em.run([8] if frame==110 else [])
                angles.append(em.read('angle'))
            # The original half-second orbit crosses the target seven times
            # in four seconds. A tap must not set its position or restart it.
            self.assertEqual(em.read('cal_count'),1)
            self.assertGreaterEqual(sum(b<a-200 for a,b in zip(angles,angles[1:])),7)
            self.assertTrue(all(1<=(b-a)%256<=11 for a,b in zip(angles,angles[1:])))
        finally:em.close()

    def test_all_signed_offsets_are_published_in_options_menu_and_results(self):
        em=Emulator(rom=BASE/'adofai.sfc')
        def check(row,col,value):
            hud=C.string_at(em.ram+0x800,2048)
            start=row*64+col*2
            self.assertEqual(''.join(chr(hud[start+i*2]) for i in range(3)),f'{value:+03d}')
            self.assertEqual(C.string_at(em.core.retro_get_memory_data(3)+0xf000,2048),hud)
        try:
            for _ in range(120):em.run()
            press(em,0)
            for _ in range(5):press(em,5)
            for _ in range(30):press(em,6)
            for value in range(-30,31):
                self.assertEqual(em.read('calibration',True),value)
                check(16,23,value)
                press(em,3);check(26,12,value)
                press(em,0)
                if value<30:press(em,7)
            press(em,8)
            for button in [8,0,9,1,10,11,4,5,6,7,8,0,9,1,10,11]:press(em,button)
            self.assertEqual(em.read('state'),6)
            while em.read('cal_recommend',True)>-30:press(em,6)
            for value in range(-30,31):
                check(10,11,value)
                if value<30:press(em,7)
        finally:em.close()

    def test_calibration_zero_is_the_previous_plus_eight(self):
        em=Emulator(rom=BASE/'adofai.sfc')
        try:
            for _ in range(120):em.run()
            self.assertEqual(em.read('calibration',True),0)
            self.assertEqual(em.read('speed_tenths'),10)
            self.assertEqual(em.read('speed_offset',True),8)
            press(em,0)
            for _ in range(5):press(em,5)
            for _ in range(8):press(em,6)
            self.assertEqual(em.read('calibration',True),-8)
            self.assertEqual(em.read('speed_offset',True),0)
            for _ in range(16):press(em,7)
            self.assertEqual(em.read('calibration',True),8)
            self.assertEqual(em.read('speed_offset',True),16)
            press(em,3)
            configure(em,5)
            self.assertEqual(em.read('speed_offset',True),8)
        finally:em.close()

    def test_hold_repeat_waits_then_scrolls_and_never_generates_gameplay_taps(self):
        em=Emulator(rom=BASE/'adofai.sfc')
        try:
            for _ in range(120):em.run()
            for _ in range(20):em.run([5])
            self.assertEqual(em.read('selected_level'),1)
            for _ in range(30):em.run([5])
            self.assertGreater(em.read('selected_level'),3)
            em.run();press(em,0)
            for _ in range(5):press(em,5)
            for _ in range(20):em.run([6])
            self.assertEqual(em.read('calibration',True),-1)
            for _ in range(170):em.run([6])
            self.assertEqual(em.read('calibration',True),-30)
            em.run();press(em,3)
            press(em,3)
            for _ in range(40):em.run([5])
            self.assertEqual(em.read('tap_head'),em.read('tap_tail'))
            self.assertEqual(em.read('tap_overruns'),0)
        finally:em.close()

    def test_all_61_menu_selections_have_visible_cursor_and_text(self):
        base=BASE
        self.assertEqual(json.loads((base/'pack.json').read_text())['levels'],list(range(1,62)))
        em=Emulator(rom=base/'adofai.sfc')
        try:
            for _ in range(120):em.run()
            for selected in range(61):
                self.assertEqual(em.read('selected_level'),selected)
                hud=C.string_at(em.ram+0x800,2048)
                def row(n):return ''.join(chr(hud[n*64+i]) if hud[n*64+i] else ' ' for i in range(0,64,2))
                self.assertEqual(row(3).strip(),'MSU-1 ALL WORLDS + TECH')
                self.assertEqual([n for n in range(6,15) if row(n)[0]=='>'],[6+selected%9])
                self.assertEqual(row(19).strip(),'START TO PLAY')
                self.assertEqual(row(24).strip(),'L / R SPEED: 1.0X')
                video=em.core.retro_get_memory_data(3)
                self.assertEqual(C.string_at(video+0xf000,2048),hud)
                if selected<60:press(em,5)
            press(em,11);self.assertEqual(em.read('speed_tenths'),11)
            self.assertEqual(em.read('state'),0)
        finally:em.close()

if __name__=='__main__':unittest.main()
