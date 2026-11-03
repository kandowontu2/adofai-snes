"""Check the published menu pixels, cursor, and text through both pages."""
import ctypes as C,json,sys,unittest
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
from emulate import Emulator
from input_helpers import press
from official_catalog import PACKS

class Menus(unittest.TestCase):
    def test_cursor_and_text_on_every_cartridge(self):
        for pack,meta in PACKS.items():
            base=ROOT/'build/campaign' if pack=='main' else ROOT/f'build/packs/{pack}'
            em=Emulator(rom=base/'adofai.sfc')
            try:
                for _ in range(120):em.run()
                def words(row):
                    return np.frombuffer(C.string_at(em.ram+0x800+row*64,64),dtype='<u2')
                def text(row):return ''.join(chr(int(x)&255) if x&255 else ' ' for x in words(row))
                for selected in range(len(meta['levels'])):
                    self.assertEqual(em.read('selected_level'),selected,pack)
                    self.assertEqual(text(3).strip(),meta['title'],pack)
                    self.assertEqual(text(21).strip(),'X PRACTICE    Y WATCH',pack)
                    self.assertEqual(text(24).strip(),'L / R SPEED: 1.0X',pack)
                    cursors=[row for row in range(6,15) if text(row)[0]=='>']
                    self.assertEqual(cursors,[6+selected%9],pack)
                    self.assertNotEqual(int(words(cursors[0])[0])&0x1c00,0,pack)
                    # The PPU's committed text map must match the complete HUD.
                    for _ in range(3):em.run()
                    vram=em.core.retro_get_memory_data(3)
                    self.assertEqual(C.string_at(vram+0xf000,2048),C.string_at(em.ram+0x800,2048),pack)
                    em.capture(base/f'verification/menu-{selected+1}.png')
                    if selected+1<len(meta['levels']):press(em,5)
                # Decorative orbs stay above the level list and controls.
                oam=np.frombuffer(C.string_at(em.ram+0x200,512),dtype=np.uint8).reshape(128,4)
                self.assertTrue(np.all(oam[oam[:,1]<224,1]==24),pack)
                press(em,0)
                for row in range(6):
                    self.assertEqual(em.read('state'),7)
                    self.assertEqual([y for y in range(6,17,2) if text(y)[1]=='>'],[6+row*2],pack)
                    press(em,5)
                press(em,3)
                self.assertEqual(em.read('state'),0)
                self.assertEqual(text(21).strip(),'X PRACTICE    Y WATCH')
                # Check actual bright font pixels, not only tile indices.
                em.capture(base/'verification/menu-fixed.png')
                from PIL import Image
                pixels=np.array(Image.open(base/'verification/menu-fixed.png'))
                self.assertGreater(np.count_nonzero(np.all(pixels[48:120]>180,axis=2)),100,pack)
            finally:em.close()

if __name__=='__main__':unittest.main()
