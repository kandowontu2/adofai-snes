import struct
import sys
import unittest
from pathlib import Path
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from symbol_scale import frames,TILES


def pixels(data,width):
    result=np.zeros((len(data)//32//(width//8)*8,width),dtype=np.uint8)
    for t in range(len(data)//32):
        for y in range(8):
            for x in range(8):
                for bit in range(4):
                    result[t//(width//8)*8+y,t%(width//8)*8+x]|=((data[t*32+(bit//2)*16+y*2+bit%2]>>(7-x))&1)<<bit
    return result


class SymbolScaleTests(unittest.TestCase):
    def test_every_size_preserves_source_indices_and_center(self):
        source=(Path(__file__).resolve().parents[1]/'assets/graphics/mode7/objects.chr').read_bytes()
        sheet=pixels(source,128);data=frames(source)
        previous=128
        for size in range(1,33):
            at,length=struct.unpack_from('<HH',data,(size-1)*4)
            box=8 if size<=8 else 16 if size<=16 else 32
            self.assertEqual(at,previous);previous=at+length
            self.assertEqual(length,box*box*2)
            actual=pixels(data[at:at+length],box*4)
            for i,tile in enumerate(TILES):
                original=sheet[tile//16*8:tile//16*8+16,tile%16*8:tile%16*8+16]
                # Independent pixel-center nearest-neighbor sample.
                indices=np.minimum(15,np.floor((np.arange(size)+.5)*16/size).astype(int))
                expected=np.zeros((box,box),dtype=np.uint8);offset=(box-size)//2
                expected[offset:offset+size,offset:offset+size]=original[np.ix_(indices,indices)]
                np.testing.assert_array_equal(actual[:,i*box:(i+1)*box],expected,err_msg=f'{size}px symbol {i}')
        self.assertEqual(previous,len(data))

    def test_original_sixteen_pixel_art_is_unchanged(self):
        source=(Path(__file__).resolve().parents[1]/'assets/graphics/mode7/objects.chr').read_bytes()
        data=frames(source);at,length=struct.unpack_from('<HH',data,15*4)
        actual=pixels(data[at:at+length],64);original=pixels(source,128)
        for i,tile in enumerate(TILES):
            np.testing.assert_array_equal(actual[:,i*16:(i+1)*16],original[tile//16*8:tile//16*8+16,tile%16*8:tile%16*8+16])


if __name__=='__main__':unittest.main()
