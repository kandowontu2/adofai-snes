import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from hit_sound_assets import selections

class HitSounds(unittest.TestCase):
    def test_midspin_trigger_and_silent_normal_sound(self):
        chart=dict(notes=[dict(flags=f) for f in (0,0,24,0,0,0)])
        source=dict(hitsound="Kick",hitsoundVolume=100,events=[
            dict(floor=0,gameSound="Hitsound",hitsound="Hammer",hitsoundVolume=100),
            dict(floor=2,gameSound="Midspin",hitsound="Hat",hitsoundVolume=50),
            dict(floor=4,gameSound="Hitsound",hitsound="None",hitsoundVolume=100),
            dict(floor=5,gameSound="Hitsound",hitsound="Sizzle",hitsoundVolume=80)])
        self.assertEqual(selections(chart,source),[("Kick",76),("Kick",76),("Hat",38),("Hat",38),("None",76),("Sizzle",61)])

if __name__=="__main__":unittest.main()
