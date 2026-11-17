import math,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from neo_runtime_assets import planet_roles,twirl_curve


class PlanetRoleTests(unittest.TestCase):
    def test_new_planet_enters_without_displacing_old_pivot(self):
        roles=planet_roles([dict(planets=2),dict(planets=3)])
        pivot,active,trailing=roles[1]
        self.assertEqual(pivot,1)
        self.assertEqual(active,2)
        # The trailing identity must remain at the old pivot's (0,0)
        # when the new pivot is at (24,0) and its trailing angle is 180°.
        position={pivot:(24,0),active:(12,-12*math.sqrt(3)),trailing:(0,0)}
        self.assertEqual(position[0],(0,0))

    def test_straight_landings_cycle_all_three_and_twirl_keeps_list_order(self):
        plain=[dict(planets=p,ccw=False) for p in (2,3,3,3,3)]
        twirl=[dict(n,ccw=i>=2) for i,n in enumerate(plain)]
        a=planet_roles(plain);self.assertEqual(a,planet_roles(twirl))
        self.assertEqual([r[0] for r in a[1:]],[1,2,0,1])

    def test_midspin_chooses_previous_neighbor(self):
        notes=[dict(planets=p,flags=16 if i==2 else 0) for i,p in enumerate((2,3,3,3))]
        roles=planet_roles(notes)
        self.assertEqual(roles[2][0],roles[1][2])
        self.assertEqual(roles[3][0],roles[1][0])

    def test_twirl_preserves_both_planets_at_handoff(self):
        note=dict(frame=0,entry_angle=math.pi/3,exit_angle=-2*math.pi/3,speed=1)
        a,b,d=twirl_curve(note,dict(frame=40),120)[0]
        self.assertAlmostEqual(24*a/256,-12,delta=.1)
        self.assertAlmostEqual(24*b/256,24*math.sin(math.pi/3),delta=.1)
        # The other orb lies on the reflection axis and stays in place.
        x,y=12,24*math.sin(math.pi/3)
        self.assertAlmostEqual((a*x+b*y)/256,x,delta=.1)
        self.assertAlmostEqual((b*x+d*y)/256,y,delta=.1)

    def test_twirl_reaches_identity_after_half_interval(self):
        note=dict(frame=0,entry_angle=0,exit_angle=math.pi,speed=1)
        self.assertEqual(twirl_curve(note,dict(frame=40),120)[-1],(256,0,256))

    def test_twirl_uses_native_outsine_weight(self):
        note=dict(frame=0,entry_angle=0,exit_angle=math.pi,speed=1)
        a,b,d=twirl_curve(note,dict(frame=40),120)[10]
        self.assertEqual((a,b),(256,0))
        self.assertAlmostEqual(d/256,2*math.sin(math.pi/4)-1,delta=1/256)

if __name__=='__main__':unittest.main()
