import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from campaign_assets import title_text

class MenuTitleTests(unittest.TestCase):
    def test_title_case_workshop_names_use_available_font_glyphs(self):
        self.assertEqual(title_text(dict(id=182,code='YS12-X',title='Thanks For Playing My Game')),
                         'YS12-X THANKS FOR PLAYING MY '[:28])

if __name__=='__main__':unittest.main()
