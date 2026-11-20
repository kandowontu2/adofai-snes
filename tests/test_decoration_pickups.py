import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from decoration_pickups import accepts


class PickupRuleTests(unittest.TestCase):
    def test_coins_and_combined_count_are_independent(self):
        region=dict(coin_modes=[2,0,0,2],coin_targets=[3,0,0,7])
        self.assertTrue(accepts(region,[3,4,0]))
        self.assertFalse(accepts(region,[7,0,0]))
        self.assertFalse(accepts(region,[3,3,0]))

    def test_forbidden_count_does_not_mean_a_minimum(self):
        region=dict(coin_modes=[3,2,2,0],coin_targets=[1,1,5,0])
        self.assertTrue(accepts(region,[0,1,5]))
        self.assertTrue(accepts(region,[2,1,5]))
        self.assertFalse(accepts(region,[1,1,5]))
        self.assertFalse(accepts(region,[0,2,5]))

    def test_legacy_collectibles_keep_their_minimum_requirement(self):
        region=dict(coin_modes=[1,0,0,0],coin_targets=[3,0,0,0])
        self.assertFalse(accepts(region,[2,0,0]))
        self.assertTrue(accepts(region,[3,0,0]))
        self.assertTrue(accepts(region,[4,0,0]))
