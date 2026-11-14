import base64
import json
import math
from pathlib import Path
import sys
import unittest
import zlib

import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from neo_fog import Fog,strength
from neo_math import POOLS,pool,FONT_CHARS
from neo_visuals import chapter_time
from make_assets import FPS

ROOT=Path(__file__).resolve().parents[1]


class MathFogTests(unittest.TestCase):
    def test_alternative_corner_pixels_are_the_playable_geometry_reflected(self):
        from PIL import Image
        from neo_warps import compile_math,fork_surfaces
        from track_geometry import surface
        notes=[dict(x=i*24,y=100,time=i,frame=i,entry_angle=math.pi,exit_angle=0,
                    spin_kind='normal',hold_length=-1) for i in range(1100)]
        for root in (248,260,555,567):
            x=root*24
            for j,(dx,dy,entry,exit) in enumerate(((0,0,math.pi,math.pi/2),(0,24,-math.pi/2,0),
                                                  (24,24,math.pi,0),(48,24,math.pi,0))):
                notes[root+j].update(x=x+dx,y=100+dy,entry_angle=entry,exit_angle=exit)
            notes[root+3]['gem_platform']=True
        chart=dict(code='T3-X',notes=notes)
        # Deliberately incompatible prefab artwork must not affect corners.
        data=dict(code='T3-X',native_tile_size=1.5,native_positions=[[n['x']/16,-n['y']/16] for n in notes],
                  native_math=[dict(kind='floor',section=1,matrix=[[1,0,0],[0,1,0],[0,0,1]],size=[1,1],alpha=[255])])
        compile_math(data,chart)
        for owner in (248,555):
            v=chart['notes'][owner]['scene_visual'];paint=Image.frombytes('L',tuple(v['size']),bytes.fromhex(v['surface']))
            json.dumps(v)  # The generated source chart must serialize as well.
            ox=notes[owner]['x']+v['offset'][0];oy=notes[owner]['y']+v['offset'][1]
            for root in (owner,owner+12):
                corner=notes[root+1];x,y,real=surface(notes,root+1)
                expected=real.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
                fy=2*notes[root]['y']-y-real.height+1
                # Includes the entire rounded outer corner and its border;
                # excludes the adjacent shared junction and straight piece.
                cx=corner['x'];cy=2*notes[root]['y']-corner['y']
                actual=paint.crop((cx-10-ox,cy-10-oy,cx+11-ox,cy+11-oy))
                target=expected.crop((cx-10-x,cy-10-fy,cx+11-x,cy+11-fy))
                self.assertEqual(actual.tobytes(),target.tobytes(),root)
                gem_index=root+3
                clean=[dict(n) for n in notes]
                for n in clean:n.pop('scene_visual',None)
                gx,gy,gem=surface(clean,gem_index)
                _,fx,fy,fake=next(p for p in fork_surfaces(clean,root) if p[0]==gem_index)
                self.assertEqual(fake.tobytes(),gem.tobytes(),'Gem facets or borders reveal an answer')
                self.assertEqual(fake.size,gem.size)
                self.assertEqual(int(fx),int(gx))
                self.assertEqual(int(fy),2*clean[root]['y']-int(gy)-gem.height+1)
                assembled=paint.crop((int(fx)-ox,int(fy)-oy,int(fx)+gem.width-ox,int(fy)+gem.height-oy))
                self.assertEqual(assembled.tobytes(),gem.tobytes(),'Compositing changed a gem platform')
                from track_colors import sequences
                palettes=sequences(data,chart)
                self.assertEqual(palettes[owner],palettes[gem_index],'Gem platforms use different colors')

    def test_both_math_paths_have_identical_reveal_and_fade(self):
        from neo_visuals import configure
        from track_visibility import visibility_schedule
        for code,roots in (('T3-X',(248,555)),('T3EX-X',(319,727))):
            positions=[[i*1.5,0] for i in range(1100)]
            data=dict(code=code,bpm=170,native_tile_size=1.5,native_positions=positions,
                      native_track_effects=[],native_math=[dict(section=section,kind='floor',size=[2,2],alpha=[255]*4,
                        matrix=[[1,0,positions[root][0]],[0,1,0],[0,0,1]]) for section,root in enumerate(roots,1)])
            chart=dict(code=code,notes=[dict(x=i*24,y=0,time=i,frame=i,speed=1,spin_kind='normal',hold_length=-1) for i in range(1100)])
            configure(data,chart)
            initial,changes=visibility_schedule(data,chart)
            for root in roots:
                branches=[root]+[r+j for r in (root,root+12) for j in (1,2,3)]
                alpha=list(initial)
                for i,v in changes.get(0,{}).items():alpha[i]=v
                self.assertEqual({alpha[i] for i in branches},{0})
                for updates in changes.values():
                    for i,v in updates.items():alpha[i]=v
                    self.assertEqual(len({alpha[i] for i in branches}),1,(code,root,updates))

    def test_native_question_variants_keep_answers_paired(self):
        for name,variants in POOLS.items():
            self.assertEqual(len(variants),4,name)
            self.assertEqual(len({q for q,a,b in variants}),4,name)
            for question,correct,wrong in variants:
                value=eval(question.replace('^','**'),{'__builtins__':{},'SQRT':math.sqrt})
                self.assertAlmostEqual(value,correct,msg=question)
                self.assertNotEqual(correct,wrong)
                self.assertLess(len(question+'='),16)

    def test_native_pitch_and_ex_difficulty_pools(self):
        self.assertEqual([pool('T3-X',g,10) for g in range(4)],['base0','2','3','3c'])
        self.assertEqual([pool('T3-X',g,13) for g in range(4)],['base0','2','2b','3'])
        self.assertEqual([pool('T3-X',g,16) for g in range(4)],['base0','1b','2','2b'])
        self.assertEqual([pool('T3-X',g,20) for g in range(4)],['base0','1b','1c','1d'])
        self.assertEqual([pool('T3EX-X',g,10) for g in range(4)],['3','3c','4','3b'])

    def test_every_live_label_character_has_external_chr(self):
        raw=(ROOT/'assets/graphics/mode7/math-font.chr').read_bytes()
        self.assertEqual(len(raw),704)
        chars=set(''.join(q+'='+str(a)+str(b) for variants in POOLS.values() for q,a,b in variants))
        for char in chars:
            self.assertIn(char,FONT_CHARS)
            index=FONT_CHARS.index(char)
            glyph=raw[index*32:(index+1)*32]
            self.assertTrue(any(glyph),char)
            # Font pixels are zero or seven in every palette: both choices
            # have the identical ink index, without correctness coloring.
            for y in range(8):
                self.assertEqual(glyph[y*2],glyph[y*2+1])
                self.assertEqual(glyph[y*2],glyph[16+y*2])
                self.assertEqual(glyph[17+y*2],0)

    def test_native_fog_envelope_and_ex_difference(self):
        for ex in (False,True):
            self.assertEqual(strength(585,ex),0)
            self.assertAlmostEqual(strength(589,ex),.8 if ex else .6)
            self.assertGreater(strength(605,ex),1)
            self.assertEqual(strength(625,ex),0)
        self.assertGreater(strength(599,True),strength(599,False))

    def test_clouds_are_spatial_coverage_and_cannot_touch_hud(self):
        sprite=dict(size=[8,8],ppunit=10,alpha=base64.b64encode(zlib.compress(bytes([255])*64)).decode())
        chart=dict(code='T3-X',notes=[dict(frame=0,time=0,x=128,y=104,angle=0,rate=256),dict(frame=99999,time=1)],
                   viewport_top=32,viewport_bottom=176,viewport_center_y=104,
                   mawaru_fog=dict(sprites=[sprite],groups=[[0]*5,[0]*5,[0]]))
        fog=Fog(chart);before=round(chapter_time(chart,584)*FPS);active=round(chapter_time(chart,610)*FPS)
        image=np.ones((184,256),dtype=np.uint8)*32;palette=np.zeros(256,dtype=np.uint16);palette[32]=1234
        self.assertIsNone(fog.mask(before,(0,0),(256,0)))
        first=fog.screen(active,image,(0,0),(256,0),palette)
        second=fog.screen(active,image,(0,0),(256,0),palette)
        self.assertTrue(np.array_equal(first,second),'No temporal dithering')
        self.assertTrue(np.array_equal(first[:33],image[:33]))
        self.assertTrue(np.array_equal(first[177:],image[177:]))
        self.assertGreater(np.count_nonzero(first!=image),100)
        self.assertEqual(int(palette[32]),1234,'Track color changed to accommodate fog')


if __name__=='__main__':unittest.main()
