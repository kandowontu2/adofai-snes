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
    def test_full_native_palette_reuses_exact_art_colors(self):
        chart=dict(notes=[dict(x=16,y=16,time=0,speed=1)])
        data=dict(source='unused.adofai',bpm=120,featured_actions=[],featured_decorations=[
            dict(eventType='AddText',decText='A',scale=[50,50])])
        palette=np.zeros(256,dtype=np.uint16)
        palette[32:128]=np.arange(96,dtype=np.uint16)+100
        palette[127]=32767
        image=np.zeros((34,64),dtype=np.uint8)
        image[1:33]=np.resize(np.arange(32,128,dtype=np.uint8),(32,64))
        before=palette[image].copy();py,px=np.mgrid[:32,:64]
        result=DecorationTracks(data,chart).draw(image,0,px,py,0,palette)
        after=palette[result]
        # Only the white glyph may replace the densely colored track.
        changed=after!=before
        self.assertTrue(changed.any())
        self.assertTrue(np.all(after[changed]==32767))

    def test_literal_arrow_and_legacy_global_placement_render(self):
        from decoration_tracks import text_image
        arrow=text_image('<- Fast!')
        self.assertEqual(arrow.shape,(64,512,4))
        self.assertTrue(arrow[:,:64,3].any())
        chart=dict(notes=[dict(x=32,y=32,time=0,speed=1)])
        data=dict(source='unused.adofai',bpm=120,featured_actions=[],featured_decorations=[
            dict(eventType='AddText',decText='A',relativeTo='Global',position=[1,2],parallax=0)])
        obj=DecorationTracks(data,chart).objects[0]
        self.assertEqual([t.at(0) for t in obj['tracks'][:2]],[1.5,3.])
        self.assertEqual(obj['parallax'],[0,0])

    def test_native_pivot_offset_scales_and_rotates_with_the_sprite(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)
            Image.new('RGBA',(100,100),(255,255,255,255)).save(path/'tile.png')
            chart=dict(notes=[dict(x=32,y=32,time=0,speed=1)],local_decoration_pivots=True)
            py,px=np.mgrid[:64,:64]
            for rotation,expected in [(0,(44,32)),(90,(32,20)),(180,(20,32)),(270,(32,44))]:
                data=dict(source=str(path/'main.adofai'),bpm=120,featured_actions=[],
                          featured_decorations=[dict(floor=0,eventType='AddDecoration',
                          decorationImage='tile.png',scale=[50,50],pivotOffset=[1,0],rotation=rotation)])
                palette=np.zeros(256,dtype=np.uint16)
                image=DecorationTracks(data,chart).draw(np.zeros((66,64),dtype=np.uint8),0,px,py,0,palette)
                yy,xx=np.nonzero(palette[image[1:65]])
                self.assertGreater(len(xx),4)
                self.assertLessEqual(abs(float(xx.mean())-expected[0]),1)
                self.assertLessEqual(abs(float(yy.mean())-expected[1]),1)

    def test_legacy_uniform_decoration_scale_applies_to_both_axes(self):
        chart=dict(notes=[dict(x=0,y=0,time=i,speed=1) for i in (0,1)])
        data=dict(source='unused.adofai',bpm=120,
                  featured_decorations=[dict(eventType='AddText',decText='A',tag='legacy',scale=100)],
                  featured_actions=[dict(floor=1,eventType='MoveDecorations',tag='legacy',scale=50,duration=0)])
        obj=DecorationTracks(data,chart).objects[0]
        self.assertEqual([obj['tracks'][i].at(0) for i in (3,4)],[100,100])
        self.assertEqual([obj['tracks'][i].at(FPS+1) for i in (3,4)],[50,50])

    def test_next_beat_opacity_reset_wins_over_previous_angle_offset(self):
        # Overclocked 619's angle-offset fade and 620's new heading share
        # one beat, but separate float expressions differ by 2e-12 frames.
        chart=dict(notes=[dict(x=0,y=0,time=175.7512185987022,speed=2),
                          dict(x=0,y=0,time=175.91975792454488,speed=1)])
        data=dict(source='unused.adofai',bpm=178,
                  featured_decorations=[dict(eventType='AddText',decText='13.',tag='header')],
                  featured_actions=[
                      dict(floor=0,eventType='MoveDecorations',tag='header',angleOffset=180,duration=1,opacity=0),
                      dict(floor=1,eventType='MoveDecorations',tag='header',duration=0,opacity=100)])
        renderer=DecorationTracks(data,chart)
        self.assertEqual(renderer.objects[0]['tracks'][5].at(chart['notes'][1]['time']*FPS+1),100)

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

    def test_legacy_png_and_native_planet_replacement_are_one_live_actor(self):
        proxies=[dict(relativeTo=p,position=[0,0],parallax=[0,0],tag=p)
                 for p in ('RedPlanet','BluePlanet')]
        replacements=[dict(p,eventType='AddObject',objectType='Planet') for p in proxies]
        data=dict(bpm=120,featured_decorations=proxies+replacements,featured_actions=[])
        chart=dict(notes=[dict(time=0,speed=1)],camera_follow_versions=[[0,100,200]],
                   camera_projection_versions=[[0,256,0]],camera_zoom_versions=[[0,256,256]])
        _,versions=actor_camera_events(data,chart,4)
        self.assertEqual(versions,[[0,100,200,256,0,256,256]])
        replacements[0]['position']=[1,0]
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
