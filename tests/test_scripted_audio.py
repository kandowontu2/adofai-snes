import sys,unittest,json,tempfile
from unittest.mock import patch
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from neo_audio import play_sound_events,planet_cues


class ScriptedAudio(unittest.TestCase):
    def test_mixed_waveform_keeps_automatic_hit_and_pitch_without_looping(self):
        import numpy as np
        from scipy.io import wavfile
        import embedded_hit_audio as audio
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);private=root/'assets/private';samples=private/'hitsounds'
            samples.mkdir(parents=True);(root/'assets/audio').mkdir()
            (private/'hitsound-levels.json').write_text(json.dumps({'1':dict(hitsound='Kick',hitsoundVolume=100,
                events=[dict(floor=1,hitsound='Shaker',hitsoundVolume=100),dict(floor=2,hitsound='None',hitsoundVolume=100)])}))
            (root/'assets/audio/hit-timing.json').write_text('{}')
            (root/'assets/audio/hit-sound-offsets.json').write_text('{"Shaker":0.015}')
            wavfile.write(samples/'sndKick.wav',1000,np.full(10,1000,dtype=np.int16))
            wavfile.write(samples/'sndShaker.wav',1000,np.full(10,2000,dtype=np.int16))
            wave=np.round(1000*np.sin(2*np.pi*100*np.arange(200)/1000)).astype(np.int16)
            wavfile.write(samples/'sndIceTile.wav',1000,wave)
            notes=[dict(step=i,time=t,flags=flag) for i,(t,flag) in enumerate([(0,0),(.1,8),(.2,16),(.3,0)])]
            cue=dict(note=3,sound='IceTile',time=.5,end=.8,pitch=200.,volume=1.,loop=False)
            chart=dict(id=1,notes=notes,neo_sound_events=[cue,cue])
            pcm=np.zeros(1000)
            with patch.object(audio,'ROOT',root):report=audio.mix_hits(pcm,chart,1000)
            self.assertEqual([(e['sound'],e['start_sample']) for e in report['inserted']],
                             [('Shaker',85),('IceTile',500),('IceTile',500)])
            np.testing.assert_allclose(pcm[85:95],2000*38/112)
            self.assertFalse(pcm[95:500].any())
            self.assertFalse(pcm[600:].any(),'a one-shot must not loop to its scheduled stop')
            frequencies=np.fft.rfftfreq(100,.001)
            self.assertEqual(frequencies[np.argmax(abs(np.fft.rfft(pcm[500:600])))],200)

    def test_play_sound_uses_native_offset_lead_and_preserves_duplicates(self):
        e=dict(floor=1,eventType='PlaySound',hitsound='Shaker',hitsoundVolume=50,
               angleOffset=90,offset=125,playDuration=200,pitch=150)
        data=dict(bpm=120,featured_actions=[e,e,dict(e,active=False)])
        notes=[dict(time=0,speed=1),dict(time=4,speed=2)]
        events=play_sound_events(data,notes)
        self.assertEqual(len(events),2)
        self.assertAlmostEqual(events[0]['time'],3.985)
        self.assertAlmostEqual(events[0]['end'],4.2)
        self.assertEqual((events[0]['pitch'],events[0]['volume'],events[0]['loop']),(150,.5,False))

    def test_planet_change_uses_current_volume_and_skips_held_landings(self):
        notes=[dict(time=i,planets=n,flags=0,hold_length=-1) for i,n in enumerate((2,3,2,3,2))]
        notes[3]['hold_length']=0
        data=dict(native_hit_volume=1,featured_actions=[dict(floor=2,eventType='SetHitsound',hitsoundVolume=50)])
        events=planet_cues(data,notes)
        self.assertEqual([(e['note'],e['sound'],e['volume']) for e in events],
                         [(1,'VehiclePositive',.6),(2,'VehicleNegative',.3)])


if __name__=='__main__':unittest.main()
