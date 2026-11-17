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
            featured_actions=[dict(floor=227,eventType='SetText',tag='game2',decText='6. Flip'),
                              dict(floor=231,eventType='MoveDecorations',tag='game',
                                   positionOffset=[-2,6],duration=1,opacity=100)])
        chart=dict(notes=[dict(time=i,speed=1,x=0,y=0) for i in range(232)])
        renderer=DecorationTracks(data,chart)
        self.assertEqual(renderer.objects[0]['tracks'][5].at(224*60.0988118623),100)
        self.assertEqual(renderer.objects[0]['images'][-1][1],'@text:')

    def test_section_six_title_is_centered_without_append_marker(self):
        actions=[dict(floor=231,eventType='SetText',tag='game2',decText='+ 6. Flip-Flop Tiles'),
                 dict(floor=231,eventType='MoveDecorations',tag='game2',positionOffset=[2,6])]
        result=title_actions(actions)
        self.assertEqual(result[0]['decText'],'6. Flip-Flop Tiles')
        move=next(a for a in result if a['eventType']=='MoveDecorations')
        self.assertEqual(move['positionOffset'],[0,6])
        self.assertEqual(actions[1]['positionOffset'],[2,6])

    def test_all_main_header_tags_retire_other_headings(self):
        for tag in ('game','game2','game3'):
            events=title_actions([dict(floor=1,eventType='SetText',tag=tag,decText='21. Lag Tiles')])
            self.assertEqual({a['tag'] for a in events if a.get('decText')==''},
                             {'game','game2','game3'}-{tag})

    def test_inactive_new_heading_does_not_clear_current_heading(self):
        chart=dict(notes=[dict(time=0,speed=1,x=0,y=0)])
        data=dict(id=284,bpm=120,source='unused.adofai',
                  featured_decorations=[dict(eventType='AddText',decText='OLD',tag='game')],
                  featured_actions=[dict(floor=0,eventType='SetText',tag='game2',decText='NEW',active=False)])
        renderer=DecorationTracks(data,chart)
        self.assertEqual(renderer.objects[0]['images'][-1][1],'@text:OLD')

    def test_long_heading_fits_inside_viewport(self):
        chart=dict(notes=[dict(time=0,speed=1,x=0,y=0)])
        data=dict(id=284,bpm=120,source='unused.adofai',featured_actions=[],
                  featured_decorations=[dict(eventType='AddText',tag='game',
                      relativeTo='Camera',decText='9. RED TILES ARE DISTRACTIONS!',scale=[100,100])])
        py,px=np.mgrid[:32,:256];palette=np.zeros(256,dtype=np.uint16)
        result=DecorationTracks(data,chart).draw(np.zeros((34,256),dtype=np.uint8),
                                                0,px,py,0,palette,(128,16))
        columns=np.nonzero(result)[1]
        self.assertGreater(len(columns),20)
        self.assertGreaterEqual(int(columns.min()),7)
        self.assertLessEqual(int(columns.max()),248)

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
