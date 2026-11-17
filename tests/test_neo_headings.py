import json
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from neo_headings import COMMANDS, Headings, commands
from make_assets import FPS
from neo_visuals import chapter_time


class NativeHeadings(unittest.TestCase):
    def test_native_heading_punctuation_has_visible_editable_glyphs(self):
        from decoration_tracks import text_image
        for character in "&'":
            self.assertTrue(np.any(text_image(character,stage_punctuation=True)[:,:,3]))

    def chart(self, code='T3-X'):
        strings={key:key.upper() for _,key,_,_ in COMMANDS}
        strings['soccer2']='EX SOCCER'
        return dict(code=code,notes=[{},dict(time=2)],
                    mawaru_headings=commands(strings,code=='T3EX-X'))

    def test_both_variants_keep_the_native_schedule_and_their_own_instruction(self):
        normal,ex=self.chart(),self.chart('T3EX-X')
        self.assertEqual(len(normal['mawaru_headings']),19)
        self.assertEqual(normal['mawaru_headings'][2]['text'],'SOCCER')
        self.assertEqual(ex['mawaru_headings'][2]['text'],'EX SOCCER')
        self.assertEqual(normal['mawaru_headings'][-1]['beat'],842)
        for chart in (normal,ex):
            headings=Headings(chart)
            for command in chart['mawaru_headings']:
                start=chapter_time(chart,command['beat'])*FPS
                self.assertEqual(headings.pose(start+1)[0],command['text'])
                end=chapter_time(chart,command['beat']+command['hang']+2+command['persist'])*FPS+FPS
                if end<headings.starts[-1]:
                    # Any intervening command replaces the old heading.
                    pose=headings.pose(end)
                    self.assertTrue(pose is None or pose[0]!=command['text'])

    def test_heading_is_camera_anchored_and_does_not_recolor_track_pixels(self):
        chart=self.chart();headings=Headings(chart)
        image=np.full((184,256),32,dtype=np.uint8)
        palette=np.zeros(256,dtype=np.uint16);palette[32]=1234
        frame=chapter_time(chart,43)*FPS
        output=headings.draw(frame,image,palette)
        self.assertTrue(np.any(output!=image))
        self.assertEqual(palette[32],1234)
        ys,xs=np.nonzero(output!=image)
        self.assertGreaterEqual(ys.min(),33)
        self.assertLessEqual(xs.max(),247)
        self.assertGreaterEqual(xs.min(),8)
        self.assertTrue(np.array_equal(output[:33],image[:33]))
        self.assertIsNone(headings.pose(headings.rows[-1][3]+FPS))


if __name__=='__main__':unittest.main()
