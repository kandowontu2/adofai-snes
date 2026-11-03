"""Binary snapshot contract shared by the asset compiler and SNES retry code."""
import struct,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from animation_assets import generate,coordinate_index
from campaign_assets import compress_map

class Animation(unittest.TestCase):
    def test_compiled_reference_sets_follow_cell_lifetimes(self):
        with tempfile.TemporaryDirectory() as folder:
            out=Path(folder)
            chart=dict(id=77,mode7=True,notes=[],visibility_cells=2,
                       visibility_offsets=[0,14],cell_coordinates=[[0,0],[1,0]],
                       spatial_cell_order=1,checkpoints=[],global_pattern_references=True,
                       compiled_reference_sets=True)
            timeline=struct.pack('<7H',3,0,1,10,2,20,0)+struct.pack('<5H',2,0,1,20,0)
            generate(out,chart,timeline,b'')
            data=(out/'animation77.bin').read_bytes();cursor=0;sets=[]
            while cursor<len(data):
                frame,kind,index,value=struct.unpack_from('<HBHH',data,cursor);cursor+=7
                if kind==14:
                    sets.append((frame,list(data[cursor:cursor+value])));cursor+=value
            self.assertEqual(sets,[(0,[0,1]),(10,[0,1,2]),(20,[0])])

    def test_spatial_runs_reorder_cells_and_delay_reuse_until_old_cells_leave(self):
        with tempfile.TemporaryDirectory() as folder:
            out=Path(folder);tiles=[0]*256
            for x,old in ((126,2),(127,0),(128,1)):tiles[x]=0x2000+old
            (out/'track_map77.bin').write_bytes(compress_map(tiles,256,1))
            rows=[[(0,1),(10,0),(20,2)],[(0,1),(10,0),(20,2)],[(0,1),(10,0),(20,2)]]
            timeline=bytearray();offsets=[]
            for row in rows:
                offsets.append(len(timeline));timeline+=struct.pack('<H',len(row))
                timeline+=b''.join(struct.pack('<HH',*v) for v in row)
            chart=dict(id=77,code='TEST',mode7=True,notes=[],visibility_cells=3,visibility_offsets=offsets,
                       cell_coordinates=[],map_height=1,map_offset_shift=2,checkpoints=[],
                       pattern_versions=[[(0,0)],[(0,1),(15,2)],[(0,0)]])
            # Palette scheduling normally has notes; these events need none.
            generate(out,chart,timeline,bytes(64)+bytes([3])*64+bytes([5])*64)
            self.assertEqual(chart['cell_coordinates'],[[126,0],[127,0],[128,0]])
            self.assertEqual(chart['visibility_offsets'],[offsets[2],offsets[0],offsets[1]])
            data=(out/'animation77.bin').read_bytes();cursor=0;seen=[]
            while cursor<len(data):
                frame,kind,index,value=struct.unpack_from('<HBHH',data,cursor);cursor+=7
                if kind==4:
                    deadline,release=struct.unpack_from('<HH',data,cursor)
                    if frame==15: self.assertEqual((index,deadline,release),(1,65534,10))
                    cursor+=68
                elif kind==9:
                    x,y=struct.unpack_from('<HH',data,cursor);cursor+=4
                    seen.append((frame,index,value,x,y,list(data[cursor:cursor+value])));cursor+=value
            self.assertIn((20,0,3,126,0,[2,2,2]),seen)
            self.assertEqual(chart['animation_format'],10)
    def test_decorative_motion_keeps_nonsticky_planet_coordinates_in_snapshot(self):
        with tempfile.TemporaryDirectory() as folder:
            out=Path(folder);(out/'track_map77.bin').write_bytes(b'')
            rows=[[(0,3)],[(0,3)],[(0,100),(10,200)],[(0,124),(10,224)],[(0,144),(10,244)],[(0,144),(10,244)]]
            timeline=bytearray();offsets=[]
            for versions in rows:
                offsets.append(len(timeline));timeline+=struct.pack('<H',len(versions))
                timeline+=b''.join(struct.pack('<HH',*v) for v in versions)
            chart=dict(id=77,mode7=True,notes=[dict(x=100,y=144,stick_to_floor=False),dict(x=124,y=144,stick_to_floor=True)],
                       moving_tiles=True,visibility_cells=0,visibility_offsets=offsets,cell_coordinates=[],map_height=0,
                       checkpoints=[dict(origin_frame=64)])
            generate(out,chart,timeline,b'')
            stream=(out/'animation77.bin').read_bytes()
            events=[struct.unpack_from('<HBHH',stream,i) for i in range(0,len(stream),7)]
            self.assertFalse(any(kind in (2,3) and index==0 for _,kind,index,_ in events))
            self.assertTrue(any(kind==2 and index==1 and value==224 for _,kind,index,value in events))
            snapshot=(out/'animation77-checkpoint-0.bin').read_bytes()
            self.assertEqual(struct.unpack_from('<4H',snapshot,210),(100,224,144,244))

    def test_palette_batch_preserves_sparse_indices_and_snapshot_cursor(self):
        with tempfile.TemporaryDirectory() as folder:
            out=Path(folder)
            chart=dict(id=77,code='TEST',mode7=True,notes=[],visibility_cells=0,cell_coordinates=[],map_height=0,
                       visibility_offsets=[],checkpoints=[dict(origin_frame=32)],track_palette_versions=[(0,0,31),(0,17,992),(0,95,31744),(5,0,0)])
            (out/'track_map77.bin').write_bytes(b'')
            generate(out,chart,b'',b'')
            stream=(out/'animation77.bin').read_bytes()
            self.assertEqual(struct.unpack_from('<HBHH',stream),(0,8,0,3))
            self.assertEqual(stream[7:16],struct.pack('<BHBHBH',0,31,17,992,95,31744))
            snapshot=(out/'animation77-checkpoint-0.bin').read_bytes()
            self.assertEqual(struct.unpack_from('<I',snapshot,4)[0],16)
            self.assertEqual(struct.unpack_from('<H',snapshot,18+17*2)[0],992)
    def test_world_coordinates_and_byte_states_survive_checkpoint_snapshot(self):
        with tempfile.TemporaryDirectory() as folder:
            out=Path(folder);tiles=[0]*(256*130)
            for i in range(3):tiles[129*256+149+i]=0x2000+i
            (out/'track_map77.bin').write_bytes(compress_map(tiles,256,130))
            timeline=b''.join(struct.pack('<HHHHH',2,0,0,10,i+1) for i in range(3))
            chart=dict(id=77,code='TEST',mode7=True,notes=[dict(x=150,y=200),dict(x=174,y=200)],
                       visibility_cells=3,visibility_offsets=[0,10,20],cell_coordinates=[0,1,2],map_height=130,map_offset_shift=2,
                       pattern_versions=[[(0,0)] for _ in range(256)],checkpoints=[dict(origin_frame=64)],
                       camera_zoom_versions=[(0,256,256),(20,-512,-128)],track_palette_versions=[(0,0,31),(20,95,1024),(40,0,992)])
            generate(out,chart,timeline,bytes(64))
            self.assertEqual(chart['cell_coordinates'],[[149,129],[150,129],[151,129]])
            self.assertEqual(struct.unpack('<HHHHHH',coordinate_index(chart)),(149,150,151,129,129,129))
            snapshot=(out/'animation77-checkpoint-0.bin').read_bytes()
            self.assertEqual(snapshot[:4],b'ADS5')
            self.assertEqual(struct.unpack_from('<HHHhh',snapshot,8),(3,2,16384,256,256))
            self.assertEqual(struct.unpack_from('<H',snapshot,18)[0],31)
            self.assertEqual(struct.unpack_from('<H',snapshot,18+95*2)[0],1024)
            self.assertEqual(snapshot[210:213],bytes([1,2,3]))
            self.assertEqual(struct.unpack_from('<HHHH',snapshot,213),(150,174,200,200))
            self.assertEqual(snapshot[221:223],bytes([3,3]))

class RotationSnapshot(unittest.TestCase):
    def test_retry_restores_matrix_and_trail_phase_before_palette(self):
        with tempfile.TemporaryDirectory() as folder:
            out=Path(folder)
            (out/'track_map77.bin').write_bytes(b'')
            c=dict(id=77,mode7=True,notes=[],visibility_cells=0,visibility_offsets=[],cell_coordinates=[],map_height=0,
                   checkpoints=[dict(origin_frame=64)],camera_follow_versions=[[0,100,200]],
                   camera_rotation_versions=[[0,256,0],[20,0,-256]],camera_rotation_phase_versions=[[0,0],[20,192]],
                   track_palette_versions=[[0,0,31]])
            generate(out,c,b'',b'')
            snap=(out/'animation77-checkpoint-0.bin').read_bytes()
            self.assertEqual(snap[:4],b'ADS6')
            self.assertEqual(struct.unpack_from('<HHhhHH',snap,14),(100,200,0,-256,192,31))
            self.assertEqual(len(snap),216)
            self.assertEqual(c['animation_format'],11)

if __name__=='__main__':unittest.main()
