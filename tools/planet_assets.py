"""Pre-scaled planet sprites, packed into unused Mode 7 OBJ tiles."""
import json
from pathlib import Path
import numpy as np
from PIL import Image
from make_assets import tile_bytes
SLOTS={5:[0],6:[2],8:[4],10:[10,14,40,42],12:[44,46,70,78],14:[96,98,100,102]}
def scaled_objects(data):
 pix=np.zeros((128,128),dtype=np.uint8)
 for t in range(256):
  b=data[t*32:(t+1)*32]
  for y in range(8):
   for x in range(8):pix[t//16*8+y,t%16*8+x]=sum(((b[(bit//2)*16+y*2+bit%2]>>(7-x))&1)<<bit for bit in range(4))
 source=Image.fromarray(pix[1:15,49:63].copy())
 for radius,slots in SLOTS.items():
  size=16 if radius<=8 else 32
  canvas=Image.new('L',(size,size));canvas.paste(source.resize((2*radius,2*radius),Image.Resampling.NEAREST),((size-2*radius)//2,)*2)
  for q,tile in enumerate(slots):
   part=np.array(canvas.crop(((q%2)*16,(q//2)*16,(q%2)*16+16,(q//2)*16+16))) if size==32 else np.array(canvas)
   x=tile%16*8;y=tile//16*8;pix[y:y+16,x:x+16]=part
 return b''.join(tile_bytes(pix[y*8:y*8+8,x*8:x*8+8]) for y in range(16) for x in range(16))
def patch_pack(out):
 from graphics_sources import patch_sa1_pack
 patch_sa1_pack(out)
