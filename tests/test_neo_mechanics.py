import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from neo_mechanics import duration_beats, packed_pause, release_required, HOLD, FREE_ROAM
from neo_audio import hold_events, suppress_regular_hit
from neo_runtime_assets import phase


class NeoMechanicsTests(unittest.TestCase):
    def test_hold_turns_preserve_underlying_arc_and_pause(self):
        self.assertEqual(duration_beats(dict(holdLength=5, extraBeats=0.5), 1), 11.5)
        self.assertEqual(duration_beats(dict(holdLength=0), 0.5), 0.5)
        self.assertEqual(duration_beats(dict(holdLength=-1), 2), 2)

    def test_zero_length_hold_still_requires_release(self):
        self.assertTrue(release_required(dict(holdLength=0), dict(holdLength=-1)))
        self.assertFalse(release_required(dict(holdLength=0), dict(holdLength=0)))
        self.assertFalse(release_required(dict(holdLength=-1), dict(holdLength=-1)))

    def test_special_flags_preserve_pause(self):
        self.assertEqual(packed_pause(dict(pause_frames=12)), 12)
        self.assertEqual(packed_pause(dict(pause_frames=0, hold_length=0)), HOLD)
        self.assertEqual(packed_pause(dict(pause_frames=123, freeroam=True)), FREE_ROAM | 123)
        with self.assertRaises(ValueError):
            packed_pause(dict(pause_frames=16384))

    def test_hold_audio_replaces_tap_and_obeys_mid_sample_lead(self):
        notes=[dict(time=t,hold_length=h,flags=0) for t,h in [(0,-1),(1,0),(2,-1),(3,-1)]]
        data=dict(native_holdsound=dict(holdStartSound=0,holdLoopSound=0,holdEndSound=0,
                  holdMidSound=1,holdMidSoundType=0,holdMidSoundTiming=1,holdMidSoundDelay=.5))
        events=hold_events(data,notes)
        self.assertEqual([(e['sound'],round(e['time'],3)) for e in events],
                         [('HeldbeatStartFuse',1),('HeldbeatLoopFuse',1),('HeldbeatMidSingSing',1.288),('HeldbeatEndFuse',2)])
        self.assertTrue(suppress_regular_hit(notes,1))
        self.assertTrue(suppress_regular_hit(notes,2))
        self.assertFalse(suppress_regular_hit(notes,3))

    def test_planet_easing_and_mirrored_parts(self):
        self.assertAlmostEqual(phase(2,.5),1-2**-.5)
        self.assertAlmostEqual(phase(2,.75,2,True),1-(1-2**-.5)/2)
        self.assertEqual(phase(2,1,2,True),1)
        self.assertEqual(phase(2,0),0)


if __name__ == '__main__':
    unittest.main()
