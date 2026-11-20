import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from gameplay_decorations import is_gameplay,has_replacements,simple_planet_proxies


class GameplayDecorationTests(unittest.TestCase):
    def test_native_floor_replacements_are_detected_without_a_level_id(self):
        self.assertTrue(has_replacements(dict(featured_decorations=[dict(eventType='AddObject',objectType='Floor')])))

    def test_vfx_off_keeps_masks_hazards_and_authored_gameplay_blocks(self):
        for d in [dict(maskingType='Mask'),dict(hitbox='Kill'),dict(hitbox='Event'),
                  dict(eventType='AddDecoration',decorationImage='ctile-step.png')]:
            self.assertTrue(is_gameplay(d))
        self.assertTrue(is_gameplay(dict(decorationImage='special-board.png'),dict(decoration_gameplay_images=['special-board.png'])))

    def test_tiled_scenery_is_not_mistaken_for_a_playable_tile(self):
        self.assertFalse(is_gameplay(dict(eventType='AddDecoration',decorationImage='background_tile.png',failHitbox='Disabled')))
        self.assertFalse(is_gameplay(dict(eventType='AddDecoration',decorationImage='particle.png')))
        for name in ('city_tileable_2.png','fog_tileable_11.png','sine_tileable.png'):
            self.assertFalse(is_gameplay(dict(eventType='AddDecoration',decorationImage=name)))
        self.assertTrue(is_gameplay(dict(eventType='AddDecoration',decorationImage='Tileable football field.png')))
        self.assertTrue(is_gameplay(dict(eventType='AddDecoration',decorationImage='fog_tileable.png',hitbox='Kill')))

    def test_custom_input_cues_survive_without_a_tile_filename(self):
        self.assertTrue(is_gameplay(dict(eventType='AddDecoration',decorationImage='cm-q1.png',tag='q1i input')))
        self.assertTrue(is_gameplay(dict(eventType='AddDecoration',decorationImage='state.png',tag='counter2')))
        self.assertFalse(is_gameplay(dict(eventType='AddDecoration',decorationImage='background.png',tag='input-glow')))

    def test_translated_actor_proxies_require_the_existing_affine_adapter(self):
        data=dict(featured_actions=[dict(eventType='ScalePlanets',targetPlanet='All',scale=0)],
                  featured_decorations=[dict(objectType='Planet',relativeTo=p,position=[0,0]) for p in ('RedPlanet','BluePlanet')])
        self.assertTrue(simple_planet_proxies(data))
        data['featured_decorations'][0]['position']=[1,0]
        self.assertFalse(simple_planet_proxies(data))
