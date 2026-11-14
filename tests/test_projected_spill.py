import sys,unittest
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from projected_spill import split,append_packets,stable_glyphs
from viewport_cells import sampled_pixels
from mode1_tracks import decode_tile
from animation_bulk import HEADER,records


class ProjectedSpillTests(unittest.TestCase):
    def test_rotated_overflow_preserves_screen_pixels_and_clears(self):
        tiles=[bytes(64)]
        for i in range(270):
            tile=bytearray([32]*64)
            for j in range(9):tile[j]=33 if i>>j&1 else 34
            tiles.append(bytes(tile))
        history={(i%30,i//30+5):[(0,i+1),(2,0)] for i in range(270)}
        chart=dict(code='fixture',notes=[dict(frame=4)],camera_follow_versions=[[0,0,0]],
                   camera_sampling_versions=[[0,240,90]],track_palette_versions=[[0,0,1],[0,1,31],[0,2,992]],
                   viewport_center_y=104,viewport_top=32,viewport_bottom=176)
        result=split(chart,tiles,history);event=chart['projected_spill_frames'][0]
        px,py=sampled_pixels(0,0,240,90,104,176,32)
        colors=[0]*256;colors[32:35]=[1,31,992]
        def screen(hist):
            out=np.zeros(px.shape,dtype=np.uint16)
            for cell,rows in hist.items():
                p=next((p for f,p in reversed(rows) if f<=0),0)
                if not p:continue
                ys,xs=np.where((px//8==cell[0])&(py//8==cell[1]))
                for y,x in zip(ys,xs):out[y,x]=colors[tiles[p][int(px[y,x]&7)+8*int(py[y,x]&7)]]
            return out
        original=screen(history);combined=np.zeros((256,256),dtype=np.uint16)
        combined[33:177]=screen(result);glyphs=bytes.fromhex(event['glyphs'])
        for x,y,g in event['objects']:
            pixels=decode_tile(glyphs[g*32:g*32+32],list(range(1,len(event['palette'])+1)))
            for j,p in enumerate(pixels):
                if p:combined[y+j//8,x+j%8]=event['palette'][p-1]
        np.testing.assert_array_equal(original,combined[33:177])
        self.assertLessEqual(len({rows[0][1] for rows in result.values() if rows[0][0]==0}-{0}),255)
        self.assertEqual(chart['projected_spill_frames'][-1]['objects'],[])
        blob=append_packets(chart,HEADER.pack(65535,255,0,0))
        parsed=list(records(blob));self.assertEqual([(r[2],r[3]) for r in parsed[:-1]],[(0,35),(0,22),(2,22)])
        self.assertTrue(parsed[1][4]&0x8000)

    def test_compact_masks_leave_direct_pixel_and_oam_routes_exact(self):
        import struct
        from sa1_stream import direct_spill_packet
        cells=[(i*8,40) for i in range(110)]
        glyphs=bytes([7])*32+bytes([8])*32
        objects=[[16,40,0],[24,40,1]]
        chart=dict(projected_spill_compact=True,projected_spill_frames=[dict(frame=0,origin=[0,0],
            cells=cells,palette=[31],glyphs=glyphs.hex(),objects=objects)])
        data=append_packets(chart,HEADER.pack(65535,255,0,0))
        routed=direct_spill_packet(data,dict(stream_direct_spill_trial=True,stream_direct_patterns_trial=True))
        first=list(records(routed))[0]
        self.assertEqual(first[3],33)
        routes=list(struct.iter_unpack('<HHH',routed[first[0]+7:first[1]]))
        image=next((a,n) for a,n,dest in routes if dest==0x9000)
        self.assertEqual(routed[image[0]:image[0]+image[1]],glyphs)
        objects_route=next((a,n) for a,n,dest in routes if dest==0xEC00)
        self.assertEqual(routed[objects_route[0]:objects_route[0]+objects_route[1]],bytes([16,40,0,0x21,24,40,1,0x21]))

    def test_stable_atlas_preserves_objects_when_glyph_order_changes(self):
        a,b,c=(bytes([i])*32 for i in (1,2,3))
        frames=[dict(glyphs=(a+b).hex(),objects=[[10,20,0],[30,40,1]]),
                dict(glyphs=(b+c+a).hex(),objects=[[10,20,0],[30,40,1],[50,60,2]])]
        out=stable_glyphs(frames)
        for original,packed in zip(frames,out):
            old=bytes.fromhex(original['glyphs']);new=bytes.fromhex(packed['glyphs'])
            for (x,y,g),(xx,yy,gg) in zip(original['objects'],packed['objects']):
                self.assertEqual((x,y,old[g*32:g*32+32]),(xx,yy,new[gg*32:gg*32+32]))
        self.assertEqual(out[0]['objects'][1][2],out[1]['objects'][0][2])
        self.assertEqual(out[0]['objects'][0][2],out[1]['objects'][2][2])
