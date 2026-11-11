"""Exercise song sets, four-times speed, signed calibration and the live HUD."""
import argparse,ctypes as C,json
from pathlib import Path
from emulate import Emulator
from input_helpers import press,select_level,configure,wait
from menu_sets import groups
from verification_data import identity


def verify(rom):
    em=Emulator(rom=rom)
    levels=json.loads((rom.parent/'pack.json').read_text())['levels']
    try:
        for _ in range(120):em.run()
        assert em.read('speed_tenths')==10
        em.capture(rom.parent/'verification/ui-menu.png')
        sets=groups(levels)
        for n in levels:
            select_level(em,n)
            assert em.read('selected_level')==levels.index(n)
            for _ in range(3):em.run()
            row=6+em.read('menu_selection')-em.read('menu_first')
            assert C.c_ubyte.from_address(em.hud+row*64).value==ord('>')
        checked=0
        for speed in range(5,41):
            for offset in (-30,-8,-1,0,1,30):
                configure(em,speed,calibration=offset)
                fixed=(abs(offset+8)*em.read('speed_pitch')*65536+768)//1536
                if offset+8<0:fixed=-fixed
                actual=em.read('speed_offset',True)*65536+em.read('speed_offset_frac')
                assert actual==fixed,(speed,offset,actual,fixed)
                checked+=1
        configure(em,40,calibration=0)
        press(em,0)
        while em.read('settings_row')!=1:press(em,4)
        for _ in range(100):em.run([7])
        em.run();assert em.read('speed_tenths')==40
        for _ in range(300):em.run([6])
        em.run();assert em.read('speed_tenths')==5
        press(em,3);configure(em,40,calibration=0)
        select_level(em,levels[0]);press(em,1);press(em,3)
        wait(em,lambda:em.read('combo')>=5,2500)
        assert em.read('meter_count')>0 and em.read('meter_average')==64
        assert em.read('m7_vbottom')==175
        em.capture(rom.parent/'verification/ui-playfield.png')
        wait(em,lambda:em.read('state')==3,12000)
        for _ in range(8):em.run()
        row=C.string_at(em.hud+22*64,64)
        text=''.join(chr(row[i]) if row[i] else ' ' for i in range(0,64,2))
        assert 'TIME' not in text and 'SPEED' in text,text
        assert em.read('misses')==0
        em.capture(rom.parent/'verification/ui-results.png')
        result=dict(passed=True,menu_songs=len(levels),sets=len(sets),calibration_speed_cases=checked,
                    max_speed=4.0,viewport_height=144,autoplay_hits=em.read('perfects'),**identity(rom))
        (rom.parent/'verification/ui-update.json').write_text(json.dumps(result,indent=2))
        print(result)
    finally:em.close()

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--rom',type=Path,required=True);a=ap.parse_args()
    (a.rom.parent/'verification').mkdir(exist_ok=True)
    verify(a.rom.resolve())
