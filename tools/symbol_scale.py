"""Camera-scaled event artwork, derived from the editable OBJ source."""
import struct
import numpy as np
from make_assets import tile_bytes

TILES=(32,34,36,38)


def frames(data):
    assert len(data)==8192
    sheet=np.zeros((128,128),dtype=np.uint8)
    for t in range(256):
        b=data[t*32:(t+1)*32]
        for y in range(8):
            for x in range(8):
                sheet[t//16*8+y,t%16*8+x]=sum(((b[(p//2)*16+y*2+p%2]>>(7-x))&1)<<p for p in range(4))
    icons=[sheet[t//16*8:t//16*8+16,t%16*8:t%16*8+16] for t in TILES]
    result=bytearray(32*4)
    for size in range(1,33):
        box=8 if size<=8 else 16 if size<=16 else 32
        pixels=np.zeros((box,box*4),dtype=np.uint8)
        indices=((2*np.arange(size)+1)*16)//(2*size)
        offset=(box-size)//2
        for i,icon in enumerate(icons):
            pixels[offset:offset+size,i*box+offset:i*box+offset+size]=icon[np.ix_(indices,indices)]
        blob=b''.join(tile_bytes(pixels[y:y+8,x:x+8]) for y in range(0,box,8) for x in range(0,box*4,8))
        # Size, length and pointer are bounded independently of chart count.
        struct.pack_into('<HH',result,(size-1)*4,len(result),len(blob))
        result+=blob
    assert len(result)<65536
    return bytes(result)
