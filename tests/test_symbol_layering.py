"""The actual OAM order must put gameplay cues over cached track cells."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from verify_mesen_ppu import sprite_tiles

class SymbolLayering(unittest.TestCase):
    def oam(self,icon_first):
        o=bytearray(544)
        for i in range(128):o[4*i+1]=240
        icon=(100,80,36,0x36);track=(100,80,0,0x21)
        for i,obj in enumerate((icon,track) if icon_first else (track,icon)):
            o[4*i:4*i+4]=bytes(obj)
        o[512]=2 if icon_first else 8
        return o
    def test_old_order_masks_icon_despite_higher_priority_bits(self):
        with self.assertRaisesRegex(AssertionError,'Gameplay icon behind'):
            sprite_tiles(self.oam(False),bytes(65536))
    def test_symbols_before_track_cells(self):
        self.assertIn((100,80),sprite_tiles(self.oam(True),bytes(65536)))

if __name__=='__main__':unittest.main()
