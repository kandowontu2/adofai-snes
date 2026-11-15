import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from supplemental_checkpoints import events, FLOORS


class SupplementalCheckpointTests(unittest.TestCase):
    def test_authored_events_take_precedence(self):
        original = [dict(floor=7, tileOffset=-1)]
        self.assertIs(events(dict(id=239, checkpoints=original)), original)

    def test_only_requested_empty_charts_are_extended(self):
        self.assertEqual(events(dict(id=1, checkpoints=[])), [])
        self.assertEqual(events(dict(id=245, checkpoints=[])), [])
        self.assertEqual(set(FLOORS), {62, 239, 240, 241, 242, 243, 244, 246, 247})

    def test_restart_must_not_be_on_a_midspin(self):
        floors = [dict(midSpin=False, holdLength=-1) for _ in range(282)]
        floors[135] = dict(midSpin=True, holdLength=-1)
        with self.assertRaises(AssertionError):
            events(dict(id=239, checkpoints=[], floors=floors))

    def test_updated_layout_requires_placement_review(self):
        with self.assertRaisesRegex(AssertionError, 'Chart layout changed'):
            events(dict(id=239, checkpoints=[], floors=[{}] * 283))


if __name__ == '__main__':
    unittest.main()
