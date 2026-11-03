"""Authored color scope, timing, palette reuse and opaque neon interiors."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from make_assets import FPS
from track_colors import sequences,evaluate,palette_schedule,palette_words

class TrackColors(unittest.TestCase):
    def fixture(self,count=6):
        d=dict(bpm=60,track_settings=dict(trackColor='ff0000'),track_actions=[])
        c=dict(code='TEST',notes=[dict(time=float(i),frame=round(i*FPS),speed=1) for i in range(count)])
        return d,c
    def test_color_track_carries_and_just_this_tile_restores_stripes(self):
        d,c=self.fixture();d['track_actions']=[dict(floor=1,eventType='ColorTrack',trackColorType='Stripes',trackColor='00ff00',secondaryTrackColor='0000ff'),
                                             dict(floor=2,eventType='ColorTrack',trackColor='ffffff',trackColorType='Single',justThisTile=True)]
        seq=sequences(d,c)
        self.assertEqual([evaluate(s,0)[0] for s in seq],[(1,0,0),(0,1,0),(1,1,1),(0,1,0),(0,0,1),(0,1,0)])
    def test_recolor_range_gap_offset_and_duration(self):
        d,c=self.fixture();d['track_actions']=[dict(floor=1,eventType='RecolorTrack',startTile=[0,'Start'],endTile=[4,'Start'],gapLength=1,
                                             angleOffset=180,duration=2,trackColor='0000ff')]
        seq=sequences(d,c)
        at=round(2*FPS)
        self.assertEqual(evaluate(seq[0],at)[0],(1,0,0))
        middle=evaluate(seq[2],at+round(FPS))[0]
        self.assertAlmostEqual(middle[0],.5,places=2);self.assertAlmostEqual(middle[2],.5,places=2)
        self.assertEqual(evaluate(seq[4],round(4*FPS)+1)[0],(0,0,1))
        self.assertEqual(evaluate(seq[1],round(5*FPS))[0],(1,0,0))
    def test_partial_recolor_retains_glow_secondary_color_and_phase(self):
        d,c=self.fixture();d['track_settings'].update(trackColorType='Glow',secondaryTrackColor='0000ff',trackColorAnimDuration=2,
                                                   trackColorPulse='Forward',trackPulseLength=4)
        d['track_actions']=[dict(floor=1,eventType='RecolorTrack',startTile=[0,'Start'],endTile=[0,'End'],trackStyle='Neon')]
        seq=sequences(d,c)
        a,style=evaluate(seq[1],round(1.5*FPS));b,_=evaluate((seq[1][0],),round(1.5*FPS))
        self.assertEqual(a,b);self.assertEqual(style,'Neon')
    def test_tagged_repeat_respects_relative_floor_and_disabled_events(self):
        d,c=self.fixture();d['track_actions']=[dict(floor=0,eventType='RecolorTrack',startTile=[0,'ThisTile'],endTile=[0,'ThisTile'],trackColor='0000ff',eventTag='x'),
                                             dict(floor=0,eventType='RepeatEvents',tag='x',repeatType='Floor',floorCount=2,gapLength=2,executeOnCurrentFloor=True),
                                             dict(floor=1,eventType='RecolorTrack',trackColor='ffffff',active=False)]
        seq=sequences(d,c)
        self.assertEqual([evaluate(s,round(6*FPS))[0] for s in seq],[(0,0,1),(1,0,0),(0,0,1),(1,0,0),(0,0,1),(1,0,0)])
    def test_palette_fade_uses_stable_geometry_and_reuses_hidden_slots(self):
        d,c=self.fixture(20);d['track_actions']=[dict(floor=i,eventType='ColorTrack',trackColor=f'{i*10:02x}8080') for i in range(20)]
        initial=[1]+[0]*19;changes={round(i*FPS):{i:3,i-1:0} for i in range(1,20)}
        slots,updates=palette_schedule(d,c,initial,changes)
        self.assertEqual(slots,[0]*20);self.assertFalse(updates)
        self.assertEqual(c['track_color_peak'],1)
        self.assertTrue(all(0<=i<96 and 0<=v<=32767 for _,i,v in c['track_palette_versions']))
        self.assertGreater(len(c['track_palette_versions']),96)
    def test_neon_keeps_opaque_black_fill_and_three_depth_edges(self):
        words=palette_words((1,.3,.8),'Neon')
        self.assertEqual(len(words),6);self.assertLess(words[0]&31,2)
        self.assertGreater(words[1]&31,words[3]&31)
        self.assertGreater(words[3]&31,words[5]&31)

    def test_landing_brightens_exclusive_material_without_pattern_changes(self):
        d,c=self.fixture(2);c['authored_visibility']=True
        d['track_settings']['trackGlowIntensity']=35
        d['track_actions']=[dict(floor=1,eventType='ColorTrack',trackColor='0080ff')]
        slots,updates=palette_schedule(d,c,[3,3],{})
        self.assertFalse(updates,'Landing should update the existing palette, not rerasterize the floor')
        index=slots[1]*2;at=c['notes'][1]['frame']
        values=[(f,v) for f,i,v in c['track_palette_versions'] if i==index]
        before=next(v for f,v in reversed(values) if f<at)
        after=next(v for f,v in reversed(values) if f<=at)
        self.assertGreater(sum((after>>s)&31 for s in (0,5,10)),sum((before>>s)&31 for s in (0,5,10)))

    def test_zero_glow_preserves_unlit_surface(self):
        d,c=self.fixture(2);c['authored_visibility']=True
        d['track_settings']['trackGlowIntensity']=0
        slots,updates=palette_schedule(d,c,[3,3],{})
        at=c['notes'][1]['frame'];index=slots[1]*2
        values=[(f,v) for f,i,v in c['track_palette_versions'] if i==index]
        before=next(v for f,v in reversed(values) if f<at)
        self.assertEqual(before,palette_words((1,0,0),'Standard')[0])

    def test_distinct_color_timelines_keep_stable_separate_materials(self):
        d,c=self.fixture(2);c['authored_visibility']=True
        d['track_settings']['trackGlowIntensity']=0
        d['track_actions']=[dict(floor=1,eventType='RecolorTrack',
            startTile=[0,'Start'],endTile=[0,'Start'],trackColor='0000ff')]
        slots,updates=palette_schedule(d,c,[3,3],{})
        self.assertNotEqual(slots[0],slots[1])
        for frame,changes in sorted(updates.items()):
            for i,slot in changes.items():slots[i]=slot
        self.assertNotEqual(slots[0],slots[1])
        palette={i:v for _,i,v in c['track_palette_versions']}
        self.assertEqual(palette[slots[0]*2],palette_words((0,0,1),'Standard')[0])
        self.assertEqual(palette[slots[1]*2],palette_words((1,0,0),'Standard')[0])

if __name__=='__main__':unittest.main()
