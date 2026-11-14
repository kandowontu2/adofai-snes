import sys,unittest,collections
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from track_patterns import palette_alias_table

class StablePaletteAliases(unittest.TestCase):
    def test_a_fading_entry_does_not_rewrite_the_static_surfaces(self):
        ranks={32:8,33:0,34:0,35:0}
        for moving in (31,20,10,0,10,20,31):
            colors={32:moving,33:32767,34:31,35:32767}
            table=palette_alias_table(colors,ranks)
            self.assertEqual(table[34],34)
            for source in colors:self.assertEqual(colors[table[source]],colors[source])
        self.assertEqual(palette_alias_table({32:31,34:31},ranks)[32],34)
