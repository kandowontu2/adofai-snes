import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from neo_singsing import Scene
from neo_visuals import configure


class SingSingPresentationTests(unittest.TestCase):
    def test_backboard_and_ticks_keep_distinct_intensities(self):
        scene=Scene.__new__(Scene);scene.ex=True
        palette={index:value for _,index,value in scene.palette()}
        self.assertLess(palette[94],palette[95])
        self.assertGreater(palette[94],0)

    def test_x_cubicle_reveals_complete_shared_route(self):
        data=dict(code='T2-X',bpm=114)
        chart=dict(notes=[dict(time=4+i*.5) for i in range(383)])
        midspins={60,66,72,78,84,90,96,102,108,114,120,126,132,138,144}
        for i in midspins:chart['notes'][i]['spin_kind']='midspin'
        configure(data,chart)
        reveals=chart['neo_opacity_events']
        self.assertEqual({e['floor'] for e in reveals},set(range(58,148))-midspins)
        self.assertEqual({e['opacity'] for e in reveals},{1})
        self.assertEqual({e['time'] for e in reveals},{chart['notes'][1]['time']+28*60/114})

    def test_x_route_previews_one_color_and_switches_before_next_hit(self):
        chart=dict(notes=[dict(time=4+i*.5,spin_kind='normal') for i in range(383)])
        for i in (60,66,72,78,84,90,96,102,108,114,120,126,132,138,144):
            chart['notes'][i]['spin_kind']='midspin'
        configure(dict(code='T2-X',bpm=114),chart)
        from collections import defaultdict
        shown=defaultdict(set)
        for e in chart['singsing_route_events']:
            if e['opacity']:shown[e['time']].add(e['floor'])
        self.assertEqual(list(shown.values()),[{60,66},{84,90},{60,66},{84,90},{60,66},{84,90}])
        self.assertTrue(chart['singsing_backgrounds_disabled'])

    def test_ex_keeps_native_midspin_timing(self):
        chart=dict(notes=[dict(time=i,spin_kind='normal') for i in range(500)])
        chart['notes'][84]['spin_kind']='midspin'
        configure(dict(code='T2EX-X'),chart)
        self.assertEqual(chart['neo_opacity_events'],[])
        self.assertNotIn('singsing_route_events',chart)
        self.assertEqual(chart['singsing_connectors'],[84])
        self.assertTrue(chart['singsing_note_cues'])
        self.assertTrue(chart['singsing_backgrounds_disabled'])


    def test_ex_connector_visibility_follows_its_midspin(self):
        from track_visibility import visibility_schedule
        notes=[dict(time=i,speed=1,spin_kind='normal') for i in range(200)]
        notes[84]['spin_kind']='midspin'
        chart=dict(notes=notes)
        initial=[1]*200;initial[83]=0;initial[84]=0
        data=dict(code='T2EX-X',bpm=114,native_track_initial=initial)
        configure(data,chart)
        chart['neo_opacity_events']=[dict(floor=84,time=2,duration=0,opacity=1),
                                     dict(floor=84,time=3,duration=0,opacity=0)]
        initial,changes=visibility_schedule(data,chart)
        self.assertEqual(initial[83],0)
        self.assertEqual([(row[83],row[84]) for row in changes.values()],[(3,3),(0,0)])


    def test_last_ex_note_row_is_visible_below_the_track(self):
        from make_assets import FPS
        data=dict(code='T2EX-X',bpm=114,native_singsing_visuals={
            'lane0_midspin0':dict(frames=[dict(size=[5,5],alpha=(bytes([255])*25).hex())])})
        chart=dict(notes=[dict(time=0),dict(time=0)],render_transforms={0:[256,0,128,72]})
        scene=Scene(data,chart)
        layers=scene.layers(round(76.8*60/114*FPS))
        visible=[(slot,y+part.getbbox()[1],y+part.getbbox()[3])
                 for slot,front,x,y,part in layers if part.getbbox()]
        # The final group has quarter-, eighth-, and sixteenth-beat cues.
        self.assertTrue({44,45,46}.issubset({slot for slot,_,_ in visible}))
        self.assertTrue(all(top>=110 and bottom<=144 for _,top,bottom in visible))
        self.assertTrue(any(slot==47 for slot,_,_ in visible))
        bounds={}
        for slot,front,x,y,part in layers:
            if slot in (45,46) and part.getbbox():
                bounds.setdefault(slot,(x+part.getbbox()[0],x+part.getbbox()[2]))
        self.assertLess(bounds[46][1],bounds[45][0])


if __name__=='__main__':unittest.main()
