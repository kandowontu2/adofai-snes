import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from audit_song_alignment import RATE, alignment


class SongAlignmentTest(unittest.TestCase):
    def test_detects_signed_delay_with_countdown_and_added_hits(self):
        source = np.random.default_rng(75).normal(size=RATE*8)
        for delay in (-120, 0, 192):
            encoded = np.pad(source, (RATE+delay, RATE))
            encoded[RATE*3:RATE*3+200] += 3
            rows = alignment(source, encoded, 1, [2])
            self.assertEqual(rows[0]['delay_ms'], delay*1000/RATE)
            self.assertGreater(rows[0]['correlation'], .95)


if __name__ == '__main__':
    unittest.main()
