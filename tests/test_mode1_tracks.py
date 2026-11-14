import sys,struct,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from mode1_tracks import encode_tile,decode_tile,schedule,symbol_candidates,icon_descriptors
from sa1_stream import indexed_packets,mode1_seeds
from animation_bulk import HEADER,records

class Mode1Tracks(unittest.TestCase):
    def test_row_dictionary_reconstructs_all_four_planes(self):
        from sa1_stream import mode1_row_dictionary
        import random
        rng=random.Random(66)
        glyphs=[bytes(rng.randrange(256) for _ in range(32)) for _ in range(128)]
        glyphs+=glyphs[:8]
        packed=mode1_row_dictionary(b''.join(glyphs));base=len(glyphs)*12
        for i,expected in enumerate(glyphs):
            actual=bytearray(32)
            for y in range(8):
                pair=int.from_bytes(packed[i*12+(y//2)*3:i*12+(y//2)*3+3],'little')
                row=((pair>>(12*(y%2)))&4095)*4
                actual[y*2:y*2+2]=packed[base+row:base+row+2]
                actual[16+y*2:18+y*2]=packed[base+row+2:base+row+4]
            self.assertEqual(actual,expected)

    def test_due_frames_preserve_cached_future_glyphs_and_overlapping_map_writes(self):
        from sa1_stream import mode1_merge_frames
        import random
        rng=random.Random(71);source=bytearray()
        for time in range(8):
            palette=bytes(rng.randrange(32,96) for _ in range(96)) if time%3==0 else b''
            uploads=[(rng.randrange(32),rng.randrange(1000)) for _ in range(20)]
            # Slot 900 is a future prefetch, deliberately absent from the map.
            uploads.append((900,time+100))
            body=struct.pack('<H',2 if palette else 0)+palette+b''.join(struct.pack('<HH',*u) for u in uploads)
            source+=HEADER.pack(time,30,len(uploads),len(body))+body
            spans=[]
            for _ in range(4):
                start=rng.randrange(24)*2;values=bytes(rng.randrange(256) for _ in range(12))
                spans.append(struct.pack('<HH',start,len(values))+values)
            body=b''.join(spans);source+=HEADER.pack(time,31,len(spans),len(body))+body
            source+=HEADER.pack(time,2,time%3,100+time)
        def replay(data):
            cache=list(range(1024));colors=bytes(96);tilemap=bytearray(4096);positions={}
            for a,b,t,k,i,v in records(data):
                p=data[a+7:b]
                if k==30:
                    flags=struct.unpack_from('<H',p)[0];offset=2
                    if flags&2:colors=p[2:98];offset=98
                    for slot,glyph in struct.iter_unpack('<HH',p[offset:]):cache[slot]=glyph
                elif k==31:
                    offset=0
                    for _ in range(i):
                        addr,size=struct.unpack_from('<HH',p,offset);offset+=4
                        tilemap[addr:addr+size]=p[offset:offset+size];offset+=size
                elif k==2:positions[i]=v
            return cache,colors,tilemap,positions
        merged=mode1_merge_frames(bytes(source),{},7)
        self.assertEqual(replay(bytes(source)+HEADER.pack(65535,255,0,0)),replay(merged))
        self.assertEqual(replay(merged)[0][900],107)
        self.assertLess(len(merged),len(source))

    def test_checkpoint_seed_restores_state_before_its_first_packet(self):
        palette=bytes([0,32,33]+[0]*93)
        payload=struct.pack('<H',2)+palette+struct.pack('<HH',17,543)
        mapdata=struct.pack('<HHHH',64,4,0x0811,0x0812)
        source=HEADER.pack(0,30,1,len(payload))+payload
        source+=HEADER.pack(63,31,1,len(mapdata))+mapdata
        source+=HEADER.pack(64,30,1,6)+struct.pack('<HHH',0,17,777)
        source+=HEADER.pack(65535,255,0,0)
        index,data=indexed_packets(source,{'mode1_tracks':1})
        seeds=mode1_seeds(index,data)
        start=struct.unpack_from('<I',seeds,4)[0]
        self.assertEqual(struct.unpack_from('<H',seeds,start)[0],2)
        self.assertEqual(seeds[start+2:start+98],palette)
        self.assertEqual(seeds[start+98+64:start+98+68],mapdata[4:])
        self.assertEqual(struct.unpack_from('<H',seeds,start+98+4096+17*2)[0],543)

    def test_symbol_candidates_keep_margin_and_follow_moving_notes(self):
        chart={'notes':[{'x':0,'y':48},{'x':270,'y':48},{'x':600,'y':48}],
               'render_viewports':{'0':[0,4,33,19],'2':[40,4,33,19]}}
        source=HEADER.pack(0,28,3,6)+struct.pack('<3H',0,1,2)
        source+=HEADER.pack(1,2,2,128)+HEADER.pack(65535,255,0,0)
        data=symbol_candidates(chart,source)+HEADER.pack(65535,255,0,0)
        events=[(t,list(struct.unpack('<'+'H'*(v//2),data[a+7:b]))) for a,b,t,k,i,v in records(data) if k==28]
        self.assertEqual(events,[(0,[0,1]),(1,[0,1,2]),(2,[])])

    def test_authored_hold_release_and_planet_icons(self):
        notes=[dict(flags=32,hold_length=h,planets=p,ccw=False) for h,p in [(0,2),(-1,2),(2,2),(-1,2),(-1,2),(-1,3),(-1,2)]]
        data=icon_descriptors({'notes':notes})
        icons=[struct.unpack_from('<Hbb',data,i*16+8) for i in range(len(notes))]
        self.assertEqual(icons,[(0x3268,0,0),(0x326c,0,0),(0x346a,1,0),(0x346c,0,0),(0,0,0),(0x366e,0,0),(0x3648,0,0)])

    def test_exact_four_plane_pixels(self):
        palette=list(range(32,47))
        pixels=bytes(([0]+palette)[(x*3+y*5)%16] for y in range(8) for x in range(8))
        self.assertEqual(decode_tile(encode_tile(pixels,palette),palette),pixels)

    def test_prefetch_replay_keeps_every_frame_exact_across_evictions(self):
        glyphs=[bytes(32)]+[i.to_bytes(2,'little')*16 for i in range(1,1101)]
        frames=[({0:(0,0),**{j+1:(t*10+j+1,j%2) for j in range(20)}},((32,33),(34,35))) for t in range(109)]
        jobs,stats=schedule(frames,glyphs,budget=1100,lookahead=8)
        bytime={t:(count,payload) for t,count,payload in jobs};cache=[bytes(32)]*1024;bindings=[0]*256;selectors=bytes(96)
        for t,(refs,palettes) in enumerate(frames):
            if t in bytime:
                count,payload=bytime[t];flags=struct.unpack_from('<H',payload)[0];at=2
                if flags&1:bindings=struct.unpack_from('<256H',payload,at);at+=512
                if flags&2:selectors=payload[at:at+96];at+=96
                self.assertEqual(len(payload)-at,count*34)
                for i in range(count):
                    slot=struct.unpack_from('<H',payload,at)[0];cache[slot]=payload[at+2:at+34];at+=34
            for logical,(glyph,bank) in refs.items():
                entry=bindings[logical]
                self.assertEqual(cache[entry&1023],glyphs[glyph],(t,logical))
                if glyph:self.assertEqual(entry>>10,bank+2)
            for bank,palette in enumerate(palettes):self.assertEqual(selectors[bank*16+1:bank*16+1+len(palette)],bytes(palette))
        self.assertTrue(all(s['dma_cost']<=1100 for s in stats[1:]))

if __name__=='__main__':unittest.main()
