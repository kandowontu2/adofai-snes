import sys,unittest
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from decoration_tracks import DecorationTracks
from overclocked_readability import title_actions,shortcut_image


class OverclockedReadabilityTests(unittest.TestCase):
    def test_previous_title_does_not_return_during_section_six(self):
        data=dict(id=284,bpm=120,source='unused.adofai',featured_decorations=[
            dict(eventType='AddText',decText='5. SPEEDY LANES',tag='game')],
            featured_actions=[dict(floor=231,eventType='MoveDecorations',tag='game',
                                   positionOffset=[-2,6],duration=1)])
        chart=dict(notes=[dict(time=i,speed=1,x=0,y=0) for i in range(232)])
        renderer=DecorationTracks(data,chart)
        self.assertEqual(renderer.objects[0]['tracks'][5].at(224*60.0988118623),100)
        self.assertEqual(renderer.objects[0]['tracks'][5].at(232*60.0988118623),0)

    def test_section_six_title_is_centered_without_append_marker(self):
        actions=[dict(floor=231,eventType='SetText',tag='game2',decText='+ 6. Flip-Flop Tiles'),
                 dict(floor=231,eventType='MoveDecorations',tag='game2',positionOffset=[2,6])]
        result=title_actions(actions)
        self.assertEqual(result[0]['decText'],'6. Flip-Flop Tiles')
        self.assertEqual(result[1]['positionOffset'],[0,6])
        self.assertEqual(actions[1]['positionOffset'],[2,6])

    def test_shortcut_symbols_remain_distinct_at_native_tile_size(self):
        from PIL import Image
        images=[np.asarray(Image.fromarray(shortcut_image(name)).resize((24,14),Image.Resampling.NEAREST))
                for name in ('triangle.png','square.png')]
        self.assertFalse(np.array_equal(images[0][3:11,8:16],images[1][3:11,8:16]))
        for image in images:
            center=image[3:11,8:16,:3]
            self.assertGreater(np.count_nonzero(np.all(center==0,axis=2)),15)
            self.assertGreater(np.count_nonzero(np.all(center==255,axis=2)),5)

    def test_shortcut_symbol_is_visible_over_native_floor(self):
        chart=dict(notes=[dict(time=i,speed=1,x=16,y=16) for i in range(226)],
                   decoration_depth_order=True)
        data=dict(id=284,bpm=120,source='unused.adofai',featured_actions=[],
                  featured_decorations=[dict(floor=0,eventType='AddDecoration',
                      decorationImage='square.png',depth=1,scale=[44,45.5])])
        palette=np.zeros(256,dtype=np.uint16);palette[32]=31<<10
        image=np.zeros((34,32),dtype=np.uint8);image[10:24,4:28]=32
        py,px=np.mgrid[:32,:32]
        result=DecorationTracks(data,chart).draw(image,0,px,py,0,palette)
        self.assertEqual(int(palette[result[17,16]]),32767)

if __name__=='__main__':unittest.main()
