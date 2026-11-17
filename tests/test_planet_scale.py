import sys
import math
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from planet_scale import schedule
from make_assets import FPS

class PlanetScaleTests(unittest.TestCase):
    def test_hidden_core_does_not_hide_a_visible_replacement_actor(self):
        data=dict(live_planet_proxies=True,bpm=120,featured_actions=[
            dict(floor=0,eventType='ScalePlanets',targetPlanet='All',scale=0,duration=0)])
        chart=dict(notes=[dict(time=0,frame=60,speed=1)])
        self.assertEqual(schedule(data,chart),[])

    def test_targeted_hide_and_restore_leave_other_planets_visible(self):
        data=dict(bpm=120,featured_actions=[
            dict(floor=1,eventType='ScalePlanets',targetPlanet='IcePlanet',scale=0,duration=0),
            dict(floor=2,eventType='ScalePlanets',targetPlanet='All',scale=100,duration=0)])
        chart=dict(notes=[dict(time=t,frame=round(t*FPS),speed=1) for t in (0,1,2)])
        self.assertEqual(schedule(data,chart),[[0,256,256,256],[round(FPS),256,0,256],[round(2*FPS),256,256,256]])

    def test_replacement_actor_visibility_tracks_its_own_tags(self):
        data=dict(live_planet_proxies=True,bpm=120,featured_decorations=[
            dict(relativeTo='RedPlanet',tag='p'),dict(relativeTo='BluePlanet',tag='p')],
            featured_actions=[dict(floor=1,eventType='MoveDecorations',duration=0,tag='p',opacity=0),
                              dict(floor=2,eventType='MoveDecorations',duration=0,tag='p',opacity=100)])
        chart=dict(notes=[dict(time=t,frame=round(t*FPS),speed=1) for t in (0,1,2)])
        self.assertEqual(schedule(data,chart),[[0,256,256,256],[math.ceil(FPS),0,0,256],[math.ceil(2*FPS),256,256,256]])

    def test_eased_shrink_has_intermediate_sizes_and_reaches_zero(self):
        data=dict(bpm=120,featured_actions=[dict(floor=0,eventType='ScalePlanets',
            targetPlanet='FirePlanet',scale=0,duration=2,ease='Linear')])
        chart=dict(notes=[dict(time=0,frame=round(2*FPS),speed=1)])
        rows=schedule(data,chart)
        self.assertTrue(any(0<row[1]<256 for row in rows))
        self.assertEqual(rows[-1][1:],[0,256,256])
        self.assertLessEqual(rows[-1][0],round(FPS))

    def test_replacement_starts_from_current_size_without_snapping(self):
        data=dict(bpm=120,featured_actions=[
            dict(floor=0,eventType='ScalePlanets',targetPlanet='FirePlanet',scale=0,duration=4),
            dict(floor=1,eventType='ScalePlanets',targetPlanet='FirePlanet',scale=100,duration=2)])
        chart=dict(notes=[dict(time=t,frame=round(t*FPS),speed=1) for t in (0,1,3)])
        rows=schedule(data,chart)
        at_start=[r for r in rows if r[0]<=round(FPS)][-1]
        self.assertEqual(at_start[1],128)
        self.assertEqual(rows[-1][1],256)

if __name__=='__main__':unittest.main()
