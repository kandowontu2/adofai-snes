import base64,struct,sys,unittest,zlib
from pathlib import Path
from unittest.mock import patch
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from projected_copies import CopyWorld
from projected_tracks import raw_seeds
from animation_bulk import HEADER
from sa1_stream import indexed_packets
from verify_camera_copies import sprites

class CameraCopyTests(unittest.TestCase):
    def test_unclipped_camera_and_absent_source_color_remain_exact(self):
        pack=lambda b:base64.b64encode(zlib.compress(b)).decode()
        # An off-screen cell becomes visible only to the translated camera.
        data=dict(version=1,first=0,last=1,patterns=pack(bytes(64)+bytes([33])*64),
                  cells=pack(struct.pack('<HHHHH',40,10,1,0,1)),cell_count=1,
                  palette=[0,1234]+[0]*94,palette_changes=[])
        world=CopyWorld(data);world.beat=lambda f:850
        palette=np.zeros(256,dtype=np.uint16)
        with patch('projected_copies.copy_cameras',return_value=[(-16,0,0)]):
            image=world.screen(0,(0,0),(256,0),palette,{'code':'T3-X'})
        self.assertEqual(np.count_nonzero(image),64)
        self.assertTrue(np.all(palette[image[image!=0]]==1234))
        self.assertTrue(np.all(image[:32]==0))

    def test_seed_retains_and_clears_native_copy_state(self):
        body=struct.pack('<5H',256,0,16,32,0)
        events=HEADER.pack(0,43,1,10)+body+HEADER.pack(80,43,0,0)+HEADER.pack(65535,255,0,0)
        index,data=indexed_packets(events,{'pattern_initial':[0]*256})
        seeds=raw_seeds(index,data,snapshot=True,clone_state=True)
        for seed,count in ((1,1),(2,0)):
            at=struct.unpack_from('<I',seeds,seed*4)[0]
            self.assertEqual(struct.unpack_from('<H',seeds,at+2)[0],0x8000)
            self.assertEqual(struct.unpack_from('<H',seeds,at+4)[0],count)
            if count:self.assertEqual(seeds[at+6:at+16],body)

    def test_live_planet_copies_keep_billboard_quadrants_together(self):
        source=bytearray(544)
        for i,(x,y) in enumerate(((112,88),(128,88),(112,104),(128,104))):
            source[i*4:i*4+4]=bytes((x,y,40+i*2,0x38))
        source[512]=0xAA
        arc={k:[0]*64 for k in ('x','y','tiles','flips')}
        result,count=sprites(source,16,[(0,256,0,0,16)],arc)
        self.assertEqual(count,16)
        self.assertEqual([tuple(result[i:i+2]) for i in range(0,16,4)],[(112,88),(128,88),(112,104),(128,104)])
        self.assertEqual(result[512],0xAA)

    def test_live_copy_budget_is_per_actual_scanline(self):
        source=bytearray(544)
        for i in range(40):source[i*4:i*4+4]=bytes((100,90,64,0x38))
        arc={k:[0]*64 for k in ('x','y','tiles','flips')}
        result,count=sprites(source,160,[(256,0,0,0,0)]*4,arc)
        self.assertEqual(count,32*4)

    def test_streak_cells_rotate_about_their_shared_parent(self):
        source=bytearray(544)
        for i in range(8):source[i*4+1]=224
        # Two different cells belonging to one native arc at parent (128,104).
        source[32:40]=bytes((131,108,128,0x38,134,110,129,0x38))
        arc={k:[0]*64 for k in ('x','y','tiles','flips')}
        arc['x'][0:2]=[3,6];arc['y'][0:2]=[4,6]
        arc['x'][16:18]=[-4,-6];arc['y'][16:18]=[3,6]
        arc['tiles'][16:18]=[143,142];arc['flips'][16:18]=[0x40,0x40]
        result,count=sprites(source,40,[(0,256,0,0,16)],arc)
        self.assertEqual(count,8)
        self.assertEqual(result[:8],bytes((124,107,143,0x78,122,110,142,0x78)))
