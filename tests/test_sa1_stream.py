import sys,struct,unittest,json,tempfile
from unittest.mock import patch
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from animation_bulk import HEADER,records
from animation_catchup import unpack_events,state
from sa1_stream import packets,indexed_packets,row_dictionary,prepare,LIMIT

class StreamPackets(unittest.TestCase):
    def test_odd_catchup_counts_preserve_chained_state_and_checkpoint_tags(self):
        chart={'stream_merge_counts':[2,3,5],'pattern_initial':[0]*256}
        source=b''.join(HEADER.pack(t,4,slot,t*4+slot)+bytes(4)+bytes([t+slot])*64
                        for t in range(1,12) for slot in range(4))
        source+=HEADER.pack(65535,255,0,0)
        with patch('sa1_stream.LIMIT',256):
            normal_index,normal=packets(source,chart)
            index,data=indexed_packets(source,chart)
        entries=list(struct.iter_unpack('<HHI',normal_index));tags=[0]*256;chained=0
        for i,(_,_,choices) in enumerate(struct.iter_unpack('<HHI',index)):
            self.assertEqual(list(struct.unpack_from('<256H',data,choices+32)),tags)
            for j,count in enumerate((1,2,3,5)):
                t,n,encoded=struct.unpack_from('<HHI',data,choices+j*8)
                if not n:continue
                self.assertEqual(encoded>>28,count)
                offset=encoded&0x0FFFFFFF;actual=[]
                while True:
                    size=n&32767
                    self.assertLessEqual(size,256)
                    actual+=unpack_events(data[offset:offset+size],chart)
                    if not n&32768:break
                    chained+=1;offset+=size
                    n=struct.unpack_from('<H',data,offset)[0];offset+=2
                expected=[]
                for _,size,offset in entries[i:i+count]:
                    expected+=unpack_events(normal[offset:offset+size],chart)
                self.assertEqual(state(actual),state(expected))
                self.assertEqual(t,entries[i+count-1][0])
            if i<len(entries):
                _,size,offset=entries[i]
                for _,kind,slot,tag,_ in unpack_events(normal[offset:offset+size],chart):
                    if kind==4:tags[slot]=tag
        self.assertGreater(chained,0)

    def test_delta_hints_preserve_pixels_after_skips_and_checkpoint_seeds(self):
        from sa1_stream import inline_delta_hints
        patterns=[bytes(64)]
        for start,end in ((5,9),(7,12),(0,64),(0,0)):
            pixels=bytearray(patterns[-1])
            for i in range(start,end):pixels[i]=(pixels[i]+1)&255
            patterns.append(bytes(pixels))
        source=b''.join(HEADER.pack(i,4,3,i)+bytes(4)+pixels
                        for i,pixels in enumerate(patterns[1:],1))
        source+=HEADER.pack(65535,255,0,0)
        hinted=inline_delta_hints(source,[0]*256,b''.join(patterns))
        events=[(v,hinted[a+7:b]) for a,b,t,k,slot,v in records(hinted) if k==4]
        for selected,tag,pixels in ((range(4),0,bytes(64)),([1,3],0,bytes(64)),
                                    ([0,2,3],0xFE03,bytes([173])*64)):
            pixels=bytearray(pixels)
            for index in selected:
                new,body=events[index];base,start,length=struct.unpack_from('<HBB',body)
                self.assertLessEqual(start+length,64)
                if tag!=base:start,length=0,64
                pixels[start:start+length]=body[4+start:4+start+length]
                tag=new
                self.assertEqual(bytes(pixels),patterns[new])
        self.assertEqual(struct.unpack_from('<HBB',events[0][1]),(0,5,4))
        self.assertEqual(struct.unpack_from('<HBB',events[-1][1])[2],0)

    def test_coordinate_batches_preserve_every_value_and_frame(self):
        from sa1_stream import batch_coordinates
        source=b''.join(HEADER.pack(t,k,i,(i*97+t)&(255 if k==1 else 65535))
                        for t in (2,3) for k in (1,2,3) for i in range(200))
        source+=HEADER.pack(65535,255,0,0)
        result=batch_coordinates(source,alpha=True)
        self.assertEqual(unpack_events(result,{}),unpack_events(source,{}))
        self.assertTrue(any(k in (17,18) for _,_,_,k,_,_ in records(result)))
        self.assertTrue(any(k==19 for _,_,_,k,_,_ in records(result)))

    def test_direct_sprite_image_routing_preserves_packet_and_image(self):
        from sa1_stream import direct_spill_packet
        for cells,glyphs in ((1,1),(16,16),(80,80)):
            image=bytes((i*37+11)&255 for i in range(glyphs*32))
            body=struct.pack('<HH',glyphs,9)+bytes(30+cells*6)+image+bytes(40+cells*4)
            original=HEADER.pack(5,2,0,123)+HEADER.pack(5,22,cells,len(body))+body+HEADER.pack(65535,255,0,0)
            packet=direct_spill_packet(original,{'stream_direct_spill_trial':True})
            t,k,begin,size=HEADER.unpack_from(packet)
            self.assertEqual((t,k,size),(5,32,len(image)))
            self.assertEqual(packet[begin:begin+size],image)
            self.assertEqual(packet[7:],original)
            for chunk_size in (128,1024,8192):
                staging=bytearray(len(packet));final=bytearray(size)
                for at in range(0,len(packet),chunk_size):
                    end=min(len(packet),at+chunk_size)
                    for i in range(at,end):
                        if begin<=i<begin+size:final[i-begin]=packet[i]
                        else:staging[i]=packet[i]
                self.assertEqual(final,image)
                self.assertEqual(staging[:begin],packet[:begin])
                self.assertEqual(staging[begin+size:],packet[begin+size:])
            self.assertEqual(unpack_events(packet,{}),unpack_events(original,{}))

    def test_direct_sprite_positions_match_payload_and_leave_camera_guard(self):
        from sa1_stream import direct_spill_packet
        for cells in (1,16,80):
            image=bytes([29])*cells*32
            positions=bytes((i*17+3)&255 for i in range(cells*4))
            fast=struct.pack('<hhHH',-87,51,cells,2)+bytes(32)+struct.pack('<H',0)
            body=struct.pack('<HH',cells,7)+bytes(30+cells*6)+image+fast+positions
            original=HEADER.pack(5,22,cells,len(body))+body+HEADER.pack(65535,255,0,0)
            packet=direct_spill_packet(original,{'stream_direct_spill_trial':True,'stream_direct_patterns_trial':True})
            _,kind,count,size=HEADER.unpack_from(packet)
            self.assertEqual((kind,count),(33,2))
            routes=list(struct.iter_unpack('<HHH',packet[7:7+size]))
            self.assertEqual([(n,d) for a,n,d in routes],[(len(image),0x9000),(len(positions),0xec00)])
            self.assertEqual(packet[routes[1][0]:routes[1][0]+len(positions)],positions)
            # Raster origin and line budgets remain in the packet, so a
            # mismatched camera still takes the independent coordinate path.
            self.assertEqual(packet[routes[0][0]+len(image):routes[1][0]],fast)
            self.assertEqual(unpack_events(packet,{}),unpack_events(original,{}))

    def test_direct_texture_table_covers_chunk_boundaries_and_catchup(self):
        from sa1_stream import direct_spill_packet,indexed_packets
        chart={'stream_direct_spill_trial':True,'stream_direct_patterns_trial':True,
               'pattern_initial':[0]*256,'stream_merge_counts':[2,3,5]}
        sources=[]
        for t in range(6):
            source=b''.join(HEADER.pack(t,4,i,100+t*128+i)+bytes(4)+bytes([(i+t)&255])*64 for i in range(128))
            sources.append(source)
            original=source+HEADER.pack(65535,255,0,0)
            packet=direct_spill_packet(original,chart)
            _,kind,count,size=HEADER.unpack_from(packet)
            self.assertEqual((kind,count,size),(33,128,768))
            routes=list(struct.iter_unpack('<HHH',packet[7:7+size]))
            for chunk_size in (128,1024,8192):
                stage=bytearray(len(packet));vram_source=bytearray(16384)
                for begin in range(0,len(packet),chunk_size):
                    for pos in range(begin,min(begin+chunk_size,len(packet))):
                        route=next(((a,n,d) for a,n,d in routes if a<=pos<a+n),None)
                        if route:
                            a,n,d=route;vram_source[d+pos-a]=packet[pos]
                        else:stage[pos]=packet[pos]
                for i in range(128):self.assertEqual(vram_source[i*64:(i+1)*64],bytes([(i+t)&255])*64)
                for a,n,d in routes:self.assertEqual(stage[a:a+n],bytes(n))
            self.assertEqual(unpack_events(packet,{}),unpack_events(original,{}))
        index,data=indexed_packets(b''.join(sources)+HEADER.pack(65535,255,0,0),chart)
        for frame,_,directory in list(struct.iter_unpack('<HHI',index))[:-1]:
            seeds=struct.unpack_from('<256H',data,directory+32)
            self.assertEqual(list(seeds[:128]),[100+(frame-1)*128+i for i in range(128)] if frame else [0]*128)
            for choice in range(4):
                _,size,offset=struct.unpack_from('<HHI',data,directory+choice*8)
                if not size:continue
                offset&=0xfffffff;packet=data[offset:offset+(size&32767)]
                _,kind,count,n=HEADER.unpack_from(packet)
                self.assertEqual(kind,33)
                for a,length,destination in struct.iter_unpack('<HHH',packet[7:7+n]):
                    self.assertEqual(length%64,0)
                    for delta in range(0,length,64):
                        slot=(destination+delta)//64
                        actual=packet[a+delta:a+delta+64]
                        event=next(e for e in unpack_events(packet,{}) if e[1]==4 and e[2]==slot)
                        self.assertEqual(actual,event[4][4:])

    def test_map_row_compaction_preserves_wraps_overwrites_and_timestamps(self):
        from sa1_stream import compact_map_rows
        chart={'cell_coordinates':[[x,3] for x in range(124,132)]}
        source=b''.join(HEADER.pack(7,9,i,1)+struct.pack('<HHB',x,3,i+1)
                        for i,(x,_) in enumerate(chart['cell_coordinates']))
        source+=HEADER.pack(7,29,2,10)+struct.pack('<HHBHHB',0,3*128+124,91,1,3*128+125,92)
        source+=HEADER.pack(8,9,2,1)+struct.pack('<HHB',126,3,93)
        source+=HEADER.pack(65535,255,0,0)
        result=compact_map_rows(source)
        self.assertLess(len(result),len(source))
        self.assertEqual(unpack_events(source,chart),unpack_events(result,chart))
        for a,b,t,k,i,v in records(result):
            if k==9:self.assertLessEqual((struct.unpack_from('<H',result,a+7)[0]&127)+v,128)

    def test_bulk_map_rows_preserve_order_and_crossing_boundaries(self):
        from sa1_stream import bulk_map_rows
        chart={'stream_bulk_rows_trial':True,'cell_coordinates':[[x,3] for x in range(124,132)]}
        source=b''.join(HEADER.pack(7,9,i,1)+struct.pack('<HHB',x,3,i+1)
                        for i,(x,_) in enumerate(chart['cell_coordinates']))
        source+=HEADER.pack(7,9,0,2)+struct.pack('<HHBB',124,3,91,92)
        source+=HEADER.pack(8,9,2,1)+struct.pack('<HHB',126,3,93)
        source+=HEADER.pack(65535,255,0,0)
        result=bulk_map_rows(source,chart)
        self.assertTrue(any(k==36 for _,_,_,k,_,_ in records(result)))
        self.assertLess(len(result),len(source))
        self.assertEqual(unpack_events(source,chart),unpack_events(result,chart))
        self.assertEqual(bulk_map_rows(source,{}),source)

    def test_rom_seek_index_uses_fixed_msu_record_stride(self):
        from sa1_stream import rom_index
        entries=[(i,99,i*544) for i in range(9000)]
        compact=rom_index(b''.join(struct.pack('<HHI',*e) for e in entries))
        self.assertEqual(len(compact),18000)
        self.assertEqual(list(struct.unpack('<9000H',compact)),list(range(9000)))
        with self.assertRaises(AssertionError):rom_index(struct.pack('<HHI',0,99,1))
        with self.assertRaises(AssertionError):
            rom_index(b''.join(struct.pack('<HHI',i,1,i*544) for i in range(32769)))

    def test_engine_rebuild_reuses_packets_after_fallback_is_bulk_packed(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)
            (p/'level66.json').write_text(json.dumps(dict(code='TEST',motion_step=1,pattern_count=2)))
            (p/'patterns66.bin').write_bytes(bytes(128))
            (p/'animation66.bin').write_bytes(HEADER.pack(1,27,1,1)+HEADER.pack(65535,255,0,0))
            prepare(p,66)
            data=(p/'stream_data66.bin').read_bytes()
            # Engine compilation subsequently transforms the fallback stream.
            (p/'animation66.bin').write_bytes(HEADER.pack(1,20,0,0))
            prepare(p,66)
            self.assertEqual((p/'stream_data66.bin').read_bytes(),data)
            (p/'stream_index66.bin').unlink()
            with self.assertRaises(AssertionError):prepare(p,66)

    def test_checkpoint_seed_ids_match_state_before_each_packet(self):
        chart={'pattern_initial':list(range(256)),'sa1_row_dictionary':1}
        source=HEADER.pack(5,4,182,6205)+bytes(68)
        source+=HEADER.pack(6,4,12,7000)+bytes(68)
        source+=HEADER.pack(65535,255,0,0)
        index,data=indexed_packets(source,chart)
        expected=list(range(256))
        for time,size,choices in struct.iter_unpack('<HHI',index):
            self.assertEqual(list(struct.unpack_from('<256H',data,choices+32)),expected)
            if time==65535:
                self.assertEqual(size,0)
                self.assertEqual(expected[182],6205)
                self.assertEqual(expected[12],7000)
                continue
            _,n,offset=struct.unpack_from('<HHI',data,choices)
            for _,kind,slot,tag,_ in unpack_events(data[offset:offset+n],chart):
                if kind==27:expected[slot]=tag

    def test_chained_overdue_packets_preserve_final_state(self):
        # Force multiple bounded chunks, including repeated writes whose
        # retained final state is still too large for one transport packet.
        source=b''.join(HEADER.pack(1,2,i%40,i) for i in range(200))
        source+=HEADER.pack(65535,255,0,0)
        with patch('sa1_stream.LIMIT',96):
            normal_index,normal=packets(source,{})
            index,data=indexed_packets(source,{})
        entries=list(struct.iter_unpack('<HHI',normal_index));chained=0
        for i,(_,_,choices) in enumerate(struct.iter_unpack('<HHI',index)):
            for j,count in enumerate((1,2,4,8)):
                _,n,offset=struct.unpack_from('<HHI',data,choices+j*8)
                if not n:continue
                chained+=bool(n&32768);actual=[]
                while True:
                    size=n&32767
                    self.assertLessEqual(size,96)
                    actual+=unpack_events(data[offset:offset+size],{})
                    if not n&32768:break
                    offset+=size;n=struct.unpack_from('<H',data,offset)[0];offset+=2
                expected=[]
                for _,size,offset in entries[i:i+count]:
                    expected+=unpack_events(normal[offset:offset+size],{})
                self.assertEqual(state(actual),state(expected))
        self.assertGreater(chained,0)

    def test_split_frame_preserves_events_and_order(self):
        chart={'cell_coordinates':[[129,130]]}
        events=HEADER.pack(5,0,0,17)
        events+=b''.join(HEADER.pack(5,4,i%256,i)+bytes(4)+bytes([i%256])*64 for i in range(240))
        events+=HEADER.pack(6,2,0,123)
        end=HEADER.pack(65535,255,0,0)
        index,data=packets(events+end,chart)
        merged=bytearray();times=[]
        for at in range(0,len(index),8):
            t,size,offset=struct.unpack_from('<HHI',index,at)
            self.assertLessEqual(size,LIMIT)
            chunk=data[offset:offset+size]
            self.assertEqual(list(records(chunk))[-1][3],255)
            merged+=chunk[:-7];times.append(t)
        self.assertGreater(times.count(5),1)
        self.assertEqual(times,sorted(times))
        self.assertEqual(unpack_events(events+end,chart),unpack_events(bytes(merged)+end,chart))

    def test_rejects_unsupported_records(self):
        with self.assertRaises(AssertionError):
            packets(HEADER.pack(1,16,0,0)+HEADER.pack(65535,255,0,0),{})

    def test_dictionary_is_pixel_exact_across_index_banks(self):
        patterns=bytes(range(64))*5000
        data,base=row_dictionary(patterns)
        result=bytearray()
        for at in range(0,len(patterns)//4,2):
            row=struct.unpack_from('<H',data,at)[0]
            result+=data[base+row:base+row+8]
        self.assertEqual(bytes(result),patterns)
        self.assertLess(len(data),len(patterns)//2)

    def test_overdue_choices_preserve_final_state(self):
        chart={'cell_coordinates':[[0,0],[1,0]]}
        frames=[HEADER.pack(t,0,t%2,t)+HEADER.pack(t,2,0,t*9)+
                HEADER.pack(t,4,1,t)+bytes(4)+bytes([t])*64 for t in range(12)]
        data=b''.join(frames)+HEADER.pack(65535,255,0,0)
        index,payload=indexed_packets(data,chart)
        for i in range(len(frames)):
            for j,count in enumerate((1,2,4,8)):
                _,_,choices=struct.unpack_from('<HHI',index,i*8)
                t,n,offset=struct.unpack_from('<HHI',payload,choices+j*8)
                if not n:continue
                actual=[]
                while True:
                    size=n&32767;self.assertLessEqual(size,LIMIT)
                    actual+=unpack_events(payload[offset:offset+size],chart)
                    if not n&32768:break
                    offset+=size;n=struct.unpack_from('<H',payload,offset)[0];offset+=2
                expected=unpack_events(b''.join(frames[i:i+count]),chart)
                self.assertEqual(state(actual),state(expected))
                self.assertEqual(t,i+count-1)
