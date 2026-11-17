import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from msu_assets import checkpoint_track_base,validate_track_numbers

class TrackNumberTests(unittest.TestCase):
    def test_released_track_numbers_are_preserved(self):
        self.assertEqual(checkpoint_track_base(1),1032)
        self.assertEqual(checkpoint_track_base(284),10088)

    def test_new_charts_do_not_overlap_overclocked(self):
        validate_track_numbers([dict(id=284,checkpoints=[0]*34),
                                dict(id=285,checkpoints=[0]*2),
                                dict(id=286,checkpoints=[0]*5)])

    def test_overlapping_ranges_fail_before_writing_audio(self):
        with self.assertRaisesRegex(AssertionError,'Overlapping MSU tracks'):
            validate_track_numbers([dict(id=1,checkpoints=[0]*33),dict(id=2,checkpoints=[0])])

if __name__=='__main__':unittest.main()
