import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from decoration_tracks import DecorationTracks, Tween, actor_camera_events
from make_assets import FPS


class DecorationTrackTests(unittest.TestCase):
    def test_dark_instruction_is_readable_on_port_playfield(self):
        chart=dict(notes=[dict(x=16,y=16,time=0,speed=1)],decoration_text_contrast=True)
        data=dict(source='unused.adofai',bpm=120,featured_actions=[],featured_decorations=[
            dict(floor=0,eventType='AddText',decText='A',color='000000ff')])
        py,px=np.mgrid[:32,:32]
        palette=np.zeros(256,dtype=np.uint16)
        result=DecorationTracks(data,chart).draw(np.zeros((34,32),dtype=np.uint8),0,px,py,0,palette)
        self.assertGreater(np.count_nonzero(palette[result]),3)

    def test_instructional_color_spans_do_not_draw_markup(self):
        from decoration_tracks import text_image
        plain=text_image('AB')
        colored=text_image('<color=#ff0000>A</color>B')
        self.assertEqual(plain.shape,colored.shape)
        self.assertTrue(np.array_equal(plain[:,:,3],colored[:,:,3]))
        first=colored[:,:64];second=colored[:,64:]
        self.assertTrue(np.all(first[first[:,:,3]>0]==[255,0,0,255]))
        self.assertTrue(np.all(second[second[:,:,3]>0]==255))

    def test_set_text_becomes_instant_tagged_image_change(self):
        from decoration_tracks import expanded_moves
        data=dict(bpm=120,featured_actions=[dict(eventType='SetText',floor=1,
                  tag='instruction',decText='TURN',angleOffset=90)])
        chart=dict(notes=[dict(time=0,speed=1),dict(time=2,speed=1)])
        rows=expanded_moves(data,chart)
        self.assertEqual(len(rows),1)
        start,_,duration,event=rows[0]
        self.assertAlmostEqual(start,2.25*FPS)
        self.assertEqual(duration,0)
        self.assertEqual(event['decorationImage'],'@text:TURN')
        self.assertEqual(event['tag'],'instruction')

    def test_optional_scenery_preserves_exact_floor_pixels_and_colors(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)
            Image.new('RGBA',(400,400),(255,0,0,255)).save(path/'red.png')
            chart=dict(notes=[dict(x=16,y=16,time=0,speed=1)],decoration_depth_order=True,
                       decoration_background_only=True,decoration_background_resolution=2,
                       decoration_background_brightness=.35)
            floor=dict(floor=0,eventType='AddObject',objectType='Floor',trackAngle=90,depth=1)
            scenery=dict(floor=0,eventType='AddDecoration',decorationImage='red.png',depth=-10)
            py,px=np.mgrid[:32,:32];results=[]
            for decorations in ([floor],[floor,scenery]):
                palette=np.zeros(256,dtype=np.uint16);palette[32]=31<<10
                image=np.zeros((34,32),dtype=np.uint8);image[17,16]=32
                data=dict(source=str(path/'main.adofai'),bpm=120,featured_actions=[],featured_decorations=decorations)
                result=DecorationTracks(data,chart).draw(image,0,px,py,0,palette)
                results.append(palette[result].copy())
            protected=results[0]!=0
            self.assertGreater(int(protected.sum()),10)
            np.testing.assert_array_equal(results[0][protected],results[1][protected])

    def test_background_filter_keeps_native_and_png_track_objects(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)
            Image.new('RGBA',(100,100),(255,255,255,255)).save(path/'tile.png')
            chart=dict(notes=[dict(x=16,y=16,time=0,speed=1)],decoration_background_tags=['scenery'])
            data=dict(source=str(path/'main.adofai'),bpm=120,featured_actions=[],
                featured_decorations=[dict(floor=0,eventType='AddDecoration',
                    decorationImage='tile.png',tag=tag) for tag in ('scenery','track')]+
                    [dict(floor=0,eventType='AddObject',objectType='Floor',tag='scenery')])
            renderer=DecorationTracks(data,chart)
            self.assertEqual(len(renderer.objects),2)

    def test_difference_overlay_preserves_underlying_track_contrast(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)
            Image.new('RGBA',(100,100),(255,255,255,255)).save(path/'invert.png')
            chart=dict(notes=[dict(x=16,y=16,time=0,speed=1)],decoration_depth_order=True)
            data=dict(source=str(path/'main.adofai'),bpm=120,featured_actions=[],
                featured_decorations=[dict(floor=0,eventType='AddDecoration',
                    decorationImage='invert.png',relativeTo='Tile',depth=-10,blendMode='Difference')])
            py,px=np.mgrid[:32,:32]
            palette=np.zeros(256,dtype=np.uint16);palette[32]=32767
            image=np.zeros((34,32),dtype=np.uint8);image[17,16]=32
            result=DecorationTracks(data,chart).draw(image,0,px,py,0,palette)
            self.assertEqual(int(palette[result[17,16]]),0)
            self.assertEqual(int(palette[result[17,15]]),32767)

    def test_background_cannot_cover_playable_floor_but_foreground_can(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)
            Image.new('RGBA',(100,100),(255,0,0,255)).save(path/'red.png')
            chart=dict(notes=[dict(x=16,y=16,time=0,speed=1)],decoration_depth_order=True)
            py,px=np.mgrid[:32,:32]
            for depth,expected in ((1,31<<10),(-1,31)):
                data=dict(source=str(path/'main.adofai'),bpm=120,featured_actions=[],
                    featured_decorations=[dict(floor=0,eventType='AddDecoration',
                        decorationImage='red.png',relativeTo='Tile',depth=depth)])
                palette=np.zeros(256,dtype=np.uint16);palette[32]=31<<10
                image=np.zeros((34,32),dtype=np.uint8);image[17,16]=32
                result=DecorationTracks(data,chart).draw(image,0,px,py,0,palette)
                self.assertEqual(int(palette[result[17,16]]),expected)

    def test_native_floor_objects_have_distinct_turn_geometry(self):
        from decoration_tracks import floor_image
        straight=floor_image(dict(trackAngle=180))
        turn=floor_image(dict(trackAngle=90))
        midspin=floor_image(dict(trackAngle=360,trackType='Midspin'))
        self.assertEqual(straight.shape,(300,300,4))
        self.assertTrue(np.any(straight[:,:,3]))
        self.assertFalse(np.array_equal(straight,turn))
        self.assertFalse(np.array_equal(turn,midspin))

    def test_set_object_color_uses_authored_tween(self):
        from decoration_tracks import expanded_moves
        data=dict(bpm=120,featured_actions=[dict(floor=0,eventType='SetObject',tag='t',duration=2,
                                                trackColor='ffb9b9ff',ease='InSine')])
        rows=expanded_moves(data,dict(notes=[dict(time=1,speed=1)]))
        self.assertEqual(rows[0][3]['color'],'ffb9b9ff')
        self.assertAlmostEqual(rows[0][2],FPS)

    def test_live_projection_matches_both_displaced_planets(self):
        proxies=[dict(relativeTo=p,position=[2,-3],parallax=[50,50],tag=p)
                 for p in ('RedPlanet','BluePlanet')]
        data=dict(bpm=120,featured_decorations=proxies,featured_actions=[])
        chart=dict(notes=[dict(time=0,speed=1)],camera_follow_versions=[[0,100,200]],
                   camera_projection_versions=[[0,256,0]],camera_zoom_versions=[[0,256,256]])
        events,versions=actor_camera_events(data,chart,4)
        self.assertEqual(versions,[[0,52,128,128,0,512,128]])
        self.assertEqual([e[1] for e in events],[10,15,6])
        proxies[1]['position']=[0,0]
        with self.assertRaises(ValueError):actor_camera_events(data,chart,4)

    def test_screen_decoration_visibility_and_color_alpha(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)
            Image.new('RGBA',(100,100),(255,255,255,255)).save(path/'tile.png')
            data=dict(source=str(path/'main.adofai'),bpm=120,
                featured_decorations=[dict(floor=0,eventType='AddDecoration',
                    decorationImage='tile.png',relativeTo='CameraAspect',tag='screen',
                    position=[0,0],visible=False,color='ffffff80',lockRotation=True,lockScale=True)],
                featured_actions=[dict(floor=0,eventType='MoveDecorations',tag='screen',
                    duration=0,visible=True),dict(floor=0,eventType='MoveDecorations',tag='screen',
                    angleOffset=180,duration=0,visible=False)])
            chart=dict(notes=[dict(x=0,y=0,time=0,speed=1)],
                       camera_sampling_versions=[[0,256,0]])
            renderer=DecorationTracks(data,chart)
            py,px=np.mgrid[:32,:64];px=px+500;py=py+700
            for frame,visible in ((0,True),(FPS,False)):
                palette=np.zeros(256,dtype=np.uint16)
                result=renderer.draw(np.zeros((34,64),dtype=np.uint8),frame,px,py,0,palette,(532,716))
                if visible:self.assertEqual(int(palette[result[17,32]]),16|(16<<5)|(16<<10))
                else:self.assertFalse(result.any())

    def test_replacement_completes_previous_target(self):
        tween = Tween(0, [(0, 100, 10, 'Linear'), (50, 100, 20, 'Linear')])
        self.assertEqual(tween.at(25), 2.5)
        self.assertEqual(tween.at(50), 10)
        self.assertEqual(tween.at(100), 15)

    def test_authored_png_moves_in_tile_units(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            Image.new('RGBA', (100, 100), (255, 255, 255, 255)).save(path/'tile.png')
            data = dict(source=str(path/'main.adofai'), bpm=120,
                featured_decorations=[dict(floor=0, eventType='AddDecoration',
                    decorationImage='tile.png', relativeTo='Tile', tag='moving')],
                featured_actions=[dict(floor=0, eventType='MoveDecorations', tag='moving',
                    duration=1, positionOffset=[1, 0])])
            chart = dict(notes=[dict(x=16, y=16, time=0, speed=1)])
            renderer = DecorationTracks(data, chart)
            py, px = np.mgrid[:32, :64]
            for frame, x in [(0, 16), (FPS/2, 40)]:
                palette = np.zeros(256, dtype=np.uint16)
                result = renderer.draw(np.zeros((34, 64), dtype=np.uint8), frame, px, py, 0, palette)
                self.assertEqual(palette[result[17, x]], 32767)
                self.assertEqual(result[17, 40 if x == 16 else 16], 0)


if __name__ == '__main__':
    unittest.main()
