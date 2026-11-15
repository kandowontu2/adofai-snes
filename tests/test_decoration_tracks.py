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
