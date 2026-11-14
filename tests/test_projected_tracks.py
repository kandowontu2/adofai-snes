import sys,unittest,struct,random
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from projected_tracks import encode_screen,exact_palettes
from projected_tracks import raw_seeds,share_flipped_glyphs,inline_pixels,pack_inline_pixels
from animation_bulk import HEADER
from sa1_stream import indexed_packets
from mode1_tracks import decode_tile,schedule


class ProjectedTrackTests(unittest.TestCase):
    def test_exact_palette_packing_preserves_all_six_banks(self):
        wanted={frozenset(range(32+b*15,47+b*15)) for b in range(6)}
        banks=exact_palettes(wanted)
        self.assertTrue(all(len(p)<=15 for p in banks))
        self.assertTrue(all(any(s<=set(p) for p in banks) for s in wanted))
        with self.assertRaises(ValueError):exact_palettes({frozenset(range(32,48))})

    def test_zero_plane_transport_restores_all_thirty_two_bytes(self):
        glyphs=[bytes(range(16))+bytes(16),bytes(16)+bytes(range(16)),bytes(range(32))]
        raw=b''.join(struct.pack('<H',slot)+g for slot,g in enumerate(glyphs,300))
        packed=pack_inline_pixels(raw,3)
        self.assertEqual(len(packed),18+18+34)
        self.assertEqual(list(inline_pixels(packed,3)),list(enumerate(glyphs,300)))

    def test_priority_list_starts_with_every_live_physical_slot(self):
        glyphs=[bytes(32)]+[bytes([n])*32 for n in range(1,20)]
        frames=[({i:(i+t+1,0) for i in range(4)},((32,),)) for t in range(10)]
        bindings=[];priorities=[]
        schedule(frames,glyphs,bindings_out=bindings,priorities_out=priorities,initial_prefetch=True)
        for words,(count,slots) in zip(bindings,priorities):
            self.assertEqual(set(slots[:count]),{w&1023 for w in words if w&1023})
            self.assertEqual(len(slots),len(set(slots)))

    def test_hardware_flips_share_glyphs_without_changing_pixels(self):
        from mode1_tracks import encode_tile
        pixels=bytes((x+2*y)%3+32 for y in range(8) for x in range(8))
        image=np.frombuffer(pixels,dtype=np.uint8).reshape(8,8)
        variants=[image,image[:,::-1],image[::-1],image[::-1,::-1]]
        palette=(32,33,34)
        glyphs=[bytes(32)]+[encode_tile(v.tobytes(),palette) for v in variants]
        frames=[({i:(i+1,0) for i in range(4)},(palette,))]
        shared,frames=share_flipped_glyphs(glyphs,frames)
        self.assertEqual(len(shared),2)
        for i,(glyph,bank) in frames[0][0].items():
            actual=np.frombuffer(decode_tile(shared[glyph],palette),dtype=np.uint8).reshape(8,8)
            if bank&16:actual=actual[:,::-1]
            if bank&32:actual=actual[::-1]
            np.testing.assert_array_equal(actual,variants[i])

    def test_inline_checkpoint_restores_atlas_palette_map_and_symbols(self):
        palette=bytes([32,33,34,35])*24
        events=HEADER.pack(0,30,0,98)+struct.pack('<H',2)+palette
        events+=HEADER.pack(0,37,2,68)+struct.pack('<H',2)+bytes([11])*32+struct.pack('<H',3)+bytes([22])*32
        events+=HEADER.pack(0,31,1,8)+struct.pack('<HHHH',256,4,0x0802,0x0803)
        events+=HEADER.pack(0,28,1,2)+struct.pack('<H',17)
        events+=HEADER.pack(70,37,1,34)+struct.pack('<H',2)+bytes([44])*32+HEADER.pack(65535,255,0,0)
        index,data=indexed_packets(events,dict(mode1_tracks=2,mode1_projected=True))
        seeds=raw_seeds(index,data)
        first,second=struct.unpack_from('<II',seeds,4)
        for offset,value in ((first,11),(second,44)):
            self.assertEqual(seeds[offset+2:offset+98],palette)
            self.assertEqual(seeds[offset+98+256:offset+98+260],struct.pack('<HH',0x0802,0x0803))
            atlas=offset+98+4096
            self.assertEqual(seeds[atlas+64:atlas+96],bytes([value])*32)
            self.assertEqual(seeds[atlas+96:atlas+128],bytes([22])*32)
            self.assertEqual(seeds[atlas+32768:atlas+32772],struct.pack('<HH',2,17))

    def test_prefetch_never_evicts_a_glyph_used_by_the_published_frame(self):
        rng=random.Random(240)
        glyphs=[bytes(32)]+[struct.pack('<H',i)+bytes([i%251])*30 for i in range(1,2500)]
        frames=[({i:(g,i%6) for i,g in enumerate(rng.sample(range(1,2500),80))},tuple((32,33) for _ in range(6))) for _ in range(60)]
        bindings=[];jobs,_=schedule(frames,glyphs,bindings_size=608,bindings_out=bindings,
                                    initial_prefetch=True,ramp_prefetch=False,eviction_horizon=1)
        by_time={t:(n,p) for t,n,p in jobs};cache=[bytes(32)]*1024
        for t,((refs,pal),words) in enumerate(zip(frames,bindings)):
            if t in by_time:
                count,payload=by_time[t];flags=struct.unpack_from('<H',payload)[0]
                at=2+1216*bool(flags&1)+96*bool(flags&2)
                for _ in range(count):
                    slot=struct.unpack_from('<H',payload,at)[0];cache[slot]=payload[at+2:at+34];at+=34
                self.assertEqual(at,len(payload))
            for logical,(glyph,bank) in refs.items():
                self.assertEqual(cache[words[logical]&1023],glyphs[glyph])
                self.assertEqual(words[logical]>>10,bank+2)

    def test_projected_background_preserves_every_visible_color(self):
        image=np.zeros((184,256),dtype=np.uint8)
        y,x=np.indices((144,256));image[33:177]=np.where((x-y)%19<5,32+(x//11+y//13)%12,0)
        glyphs=[bytes(32)];lookup={glyphs[0]:0};palettes=[]
        refs,pal=encode_screen(image,palettes,glyphs,lookup,{})
        result=np.zeros_like(image)
        for cell,(glyph,bank) in refs.items():
            row,col=divmod(cell,32)
            result[32+row*8:40+row*8,col*8:col*8+8]=np.frombuffer(decode_tile(glyphs[glyph],pal[bank]),dtype=np.uint8).reshape(8,8)
        np.testing.assert_array_equal(result,image)

    def test_screen_bindings_can_address_the_entire_viewport(self):
        glyphs=[bytes(32),bytes([1])*32,bytes([2])*32]
        frames=[({607:(1,0)},((32,),)),({607:(2,0)},((32,),))]
        bindings=[];jobs,stats=schedule(frames,glyphs,bindings_size=608,bindings_out=bindings)
        self.assertEqual(len(bindings),2)
        self.assertEqual(len(bindings[0]),608)
        self.assertGreater(bindings[0][607]&1023,0)
        self.assertNotEqual(bindings[0][607],bindings[1][607])
