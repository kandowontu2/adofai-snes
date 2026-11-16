import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from controller_events import chords

class ControllerEventTests(unittest.TestCase):
    def test_simultaneous_taps_use_two_fresh_buttons(self):
        result=chords([(10,1,1),(20,2,2),(20,1,3),(30,2,4)])
        self.assertEqual(result,[(10,1,1),(20,6,3),(30,1,4)])
    def test_hold_release_and_new_tap_have_independent_edges(self):
        self.assertEqual(chords([(10,1,1),(30,0,2),(30,2,3),(40,0,4)]),
                         [(10,1,1),(30,2,3),(40,0,4)])
    def test_release_clears_held_buttons(self):
        self.assertEqual(chords([(10,1,1),(20,0,2),(30,2,3)]),
                         [(10,1,1),(20,0,2),(30,1,3)])
