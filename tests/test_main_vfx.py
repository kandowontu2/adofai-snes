import sys,struct,unittest
from pathlib import Path
import numpy as np
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from main_vfx_assets import encode_background


class MainScenery(unittest.TestCase):
    def decode(self,chr,map):
        result=np.zeros((256,256),dtype=np.uint8)
        for index,(word,) in enumerate(struct.iter_unpack('<H',map)):
            tile=(word&1023)-80
            self.assertGreaterEqual(tile,0)
            self.assertLess(tile,len(chr)//32)
            data=chr[tile*32:tile*32+32]
            pixels=np.array([[sum(((data[y*2+(p&1)+(16 if p>=2 else 0)]>>(7-x))&1)<<p for p in range(4)) for x in range(8)] for y in range(8)],dtype=np.uint8)
            if word&0x4000:pixels=pixels[:,::-1]
            if word&0x8000:pixels=pixels[::-1,:]
            y,x=divmod(index,32);result[y*8:y*8+8,x*8:x*8+8]=pixels
        return result

    def test_flip_map_and_four_bit_pixels_round_trip(self):
        rng=np.random.default_rng(5)
        patch=rng.integers(0,4,(8,8),dtype=np.uint8)*70
        image=np.tile(np.block([[patch,patch[:,::-1]],[patch[::-1,:],patch[::-1,::-1]]]),(16,16))
        chr,map,pal,cell,pixels=encode_background(Image.fromarray(image).convert('RGB'))
        self.assertEqual(cell,1)
        self.assertEqual(len(map),2048)
        np.testing.assert_array_equal(self.decode(chr,map),pixels)
        self.assertTrue(np.all(pixels>0),'CGRAM zero must remain the gameplay backdrop')

    def test_complex_scenery_never_exceeds_reserved_vram(self):
        rng=np.random.default_rng(6)
        image=Image.fromarray(rng.integers(0,256,(256,256,3),dtype=np.uint8))
        chr,map,pal,cell,pixels=encode_background(image)
        self.assertLessEqual(len(chr),0xE00)
        self.assertEqual(cell,2)
        np.testing.assert_array_equal(self.decode(chr,map),pixels)
        self.assertEqual(pal.shape,(15,3))
