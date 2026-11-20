import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from pickup_routes import route


class PickupRouteTests(unittest.TestCase):
    def test_waiting_orbit_collects_neighbors_so_the_route_must_leave(self):
        region=dict(step=3,start=0,return_start=500,entry=[0,0],
                    cells=[[0,0],[24,0],[48,0]],coins=[[24,0],[-24,0]],
                    coin_types=[0,0],coin_modes=[2,0,0,0],coin_targets=[1,0,0,0])
        result=route(region,dict(angle=192,rate=1024,planets=2))
        self.assertTrue(result)
        self.assertEqual(result[0][1:3],[24,0])

    def test_an_ordered_future_answer_is_a_live_guard(self):
        region=dict(step=53,start=0,return_start=500,entry=[0,0],
                    cells=[[0,0],[24,0],[48,0]],coins=[[48,0],[24,0]],
                    coin_types=[4,4],coin_modes=[2,0,0,0],coin_targets=[2,0,0,0])
        with self.assertRaises((AssertionError,ValueError)):
            route(region,dict(angle=0,rate=1024,planets=2))
