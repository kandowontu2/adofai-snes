import unittest,re,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from presentation_assets import tables
class AdaptiveAudio(unittest.TestCase):
    def words(self,text,name):
        return [int(x) for x in re.search(name+r': .word ([^\n]+)',text)[1].split(',')]
    def test_audio_and_song_clocks_agree_at_every_speed(self):
        fps=60.0988118623;t=tables(fps,compact=True,adaptive_audio=True)
        logical=self.words(t,'speed_pitches');actual=self.words(t,'audio_speed_pitches')
        streams=self.words(t,'audio_speed_streams');scales=self.words(t,'speed_scales')
        self.assertEqual(len(logical),36)
        for i,n in enumerate(range(5,41)):
            rate=12000 if n<=10 else 8000
            playback=(32000*actual[i]/4096)/rate
            self.assertAlmostEqual(playback,logical[i]/1536)
            self.assertLessEqual(abs(playback-n/10),1/1024)
            self.assertLessEqual(abs(scales[i]-fps*.004*playback*65536),.5)
            self.assertEqual(streams[i],actual[i]*3)
    def test_normal_and_slow_speeds_are_unchanged(self):
        a=tables(60.0988118623,compact=True,adaptive_audio=True)
        b=tables(60.0988118623,compact=True)
        for name in ('speed_pitches','speed_scales'):
            self.assertEqual(self.words(a,name)[:6],self.words(b,name)[:6])
        # Runtime calibration follows the actual logical pitch. Faster
        # adaptive rates have a different pitch-quantization step.
