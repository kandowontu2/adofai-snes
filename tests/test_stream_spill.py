import collections,random,struct,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from animation_bulk import HEADER
from animation_catchup import unpack_events
from stream_spill import compile_spills
from mode1_tracks import decode_tile

class StreamSpill(unittest.TestCase):
    def test_palette_fade_keeps_glyph_indices_and_exact_colors(self):
        tiles=[bytes(64),bytes([32])*64,bytes([32,33])*32]
        chart=dict(pattern_initial=[0,1]+[0]*254,cell_coordinates=[(0,5)],
                   track_palette_versions=[[0,0,100],[0,1,200],[2,0,300],[2,1,50]],
                   render_viewports={'0':[0,5,1,1]},
                   render_transforms={'0':[256,0,128,104]},
                   stream_spill_threshold=1,stream_spill_stable_trial=True)
        source=(HEADER.pack(0,14,0,2)+bytes([0,1])+
                HEADER.pack(1,4,1,2)+bytes(4)+tiles[2]+
                HEADER.pack(2,7,0,300)+HEADER.pack(2,7,1,50)+
                HEADER.pack(65535,255,0,0))
        output=compile_spills(chart,source,b''.join(tiles),{(0,5):1})
        glyphs=[]
        for t,k,count,_,p in unpack_events(output,chart):
            if k!=22:continue
            palette=struct.unpack_from('<15H',p,4)
            glyph=p[34+count*6:34+count*6+32];glyphs.append(glyph)
            pixels=decode_tile(glyph,list(range(1,16)))
            expected=[100,200]*32 if t==1 else [300,50]*32
            self.assertEqual([palette[v-1] for v in pixels],expected)
        self.assertEqual(len(glyphs),2)
        self.assertEqual(glyphs[0],glyphs[1])

    def test_checkpoint_does_not_skip_sprite_to_background_repair(self):
        tiles=[bytes(64),bytes([32])*64,bytes([33])*64]
        chart=dict(pattern_initial=[0,1]+[0]*254,cell_coordinates=[(0,5)],
                   track_palette_versions=[[0,0,100],[0,1,200]],
                   render_viewports={'0':[0,5,1,1]},
                   render_transforms={'0':[256,0,128,104],'100':[256,1,128,104]},
                   stream_spill_threshold=1,checkpoints=[dict(origin_frame=90)])
        source=(HEADER.pack(0,14,0,2)+bytes([0,1])+
                HEADER.pack(80,4,1,2)+bytes(4)+tiles[2]+
                HEADER.pack(100,11,256,1)+HEADER.pack(65535,255,0,0))
        output=compile_spills(chart,source,b''.join(tiles),{(0,5):1},max_objects=1)
        repairs=[t for t,k,i,v,p in unpack_events(output,chart) if k==4 and i==1 and v==2]
        # The canonical checkpoint can replace the speculative stream image.
        # Reappearance must still receive an upload after that checkpoint.
        self.assertIn(100,repairs)

    def test_early_uploads_preserve_every_visible_frame(self):
        rng=random.Random(381);coords=[(x,5) for x in range(12)]
        tiles=[bytes(64)]+[bytes(rng.choice((32,33,34)) for _ in range(64)) for _ in range(80)]
        initial={xy:i+1 for i,xy in enumerate(coords)}
        chart=dict(pattern_initial=[0]+list(range(1,13))+[0]*243,
                   cell_coordinates=coords,track_palette_versions=[[0,i,100+i] for i in range(3)],
                   render_viewports={'0':[0,5,12,1]},
                   render_transforms={'0':[256,0,128,104],'59':[256,1,128,104]})
        source=HEADER.pack(0,14,0,13)+bytes(range(13));updates={}
        for t in range(3,59):
            slot=rng.randrange(1,13);tag=13+t
            updates[t]=(slot,tag)
            source+=HEADER.pack(t,4,slot,tag)+bytes(4)+tiles[tag]
        source+=HEADER.pack(59,11,256,1)+HEADER.pack(65535,255,0,0)
        data=compile_spills(chart,source,b''.join(tiles),initial,max_objects=4,lookahead=8)
        groups=collections.defaultdict(list)
        for event in unpack_events(data,chart):groups[event[0]].append(event)
        wanted=list(chart['pattern_initial']);loaded=list(wanted);world=dict(initial);objects={};palette=[];glyphs=b''
        for t in range(60):
            if t in updates:slot,tag=updates[t];wanted[slot]=tag
            for _,kind,slot,value,payload in groups[t]:
                if kind==4:loaded[slot]=value
                elif kind==9:
                    x,y,v=struct.unpack('<HHB',payload);world[x,y]=v
                elif kind==22:
                    count=struct.unpack_from('<H',payload)[0]
                    palette=struct.unpack_from('<15H',payload,4)
                    objects={(x//8,y//8):g for x,y,g in struct.iter_unpack('<hhH',payload[34:34+6*slot])}
                    glyphs=payload[34+6*slot:34+6*slot+count*32]
            for xy,logical in initial.items():
                bg=tiles[loaded[world[xy]]] if world[xy] else bytes(64)
                over=decode_tile(glyphs[objects[xy]*32:objects[xy]*32+32],list(range(1,16))) if xy in objects else bytes(64)
                actual=[palette[o-1] if o else 100+b-32 if b else 0 for b,o in zip(bg,over)]
                self.assertEqual(actual,[100+p-32 for p in tiles[wanted[logical]]],(t,xy))
        self.assertGreater(chart['stream_spill_stats']['early_repairs'],0)

    def test_sprite_delta_base_and_span_reconstruct_full_images(self):
        coords=[(x,y) for y in range(4,8) for x in range(10)]
        tiles=[bytes(64)]+[bytes([32])*64 for _ in coords]
        for i in range(40):
            tile=bytearray([32]*64);tile[i]=33;tiles.append(bytes(tile))
        initial={xy:i+1 for i,xy in enumerate(coords)}
        chart=dict(pattern_initial=[0]+list(range(1,41))+[0]*215,
                   cell_coordinates=coords,track_palette_versions=[[0,0,100],[0,1,200]],
                   render_viewports={'0':[0,4,10,4]},render_transforms={'0':[256,0,128,104]},
                   stream_spill_delta_trial=True)
        source=HEADER.pack(0,14,0,41)+bytes(range(41))
        for i in range(1,41):source+=HEADER.pack(1,4,i,40+i)+bytes(4)+tiles[40+i]
        for t in range(2,7):source+=HEADER.pack(t,4,1,40+t)+bytes(4)+tiles[40+t]
        source+=HEADER.pack(65535,255,0,0)
        data=compile_spills(chart,source,b''.join(tiles),initial)
        images={0:b''};hint=None;checked=0
        for _,kind,index,value,payload in unpack_events(data,chart):
            if kind==35:hint=(index,struct.unpack('<H',payload)[0],value)
            elif kind==22:
                count,identity=struct.unpack_from('<HH',payload)
                full=payload[34+index*6:34+index*6+count*32]
                if hint and full:
                    base,start,size=hint
                    self.assertIn(base,images)
                    actual=bytearray(images[base]);actual.extend(bytes(max(0,len(full)-len(actual))))
                    actual[start:start+size]=full[start:start+size]
                    self.assertEqual(actual[:len(full)],full)
                    self.assertEqual(start%32,0);self.assertEqual(size%32,0)
                    checked+=1
                images[identity]=full
        self.assertGreater(checked,2)

    def test_exact_pixels_palette_changes_and_checkpoint_entry(self):
        coords=[(x,y) for y in range(4,8) for x in range(10)]
        tiles=[bytes(64)]+[bytes([32])*64 for _ in coords]
        for i in range(40):
            tile=bytearray([32]*64);tile[i]=33;tiles.append(bytes(tile))
        chart=dict(pattern_initial=[0]+list(range(1,41))+[0]*215,
                   cell_coordinates=coords,track_palette_versions=[[0,0,100],[0,1,200],[2,1,300]],
                   render_viewports={'0':[0,4,10,4]},
                   render_transforms={'0':[256,0,128,104],'4':[256,1,128,104]})
        initial={p:i+1 for i,p in enumerate(coords)}
        source=HEADER.pack(0,14,0,41)+bytes(range(41))
        for i in range(1,41):source+=HEADER.pack(1,4,i,40+i)+bytes(4)+tiles[40+i]
        source+=HEADER.pack(2,7,1,300)+HEADER.pack(3,2,0,12)
        source+=HEADER.pack(4,11,256,1)+HEADER.pack(5,2,0,13)+HEADER.pack(65535,255,0,0)
        data=compile_spills(chart,source,b''.join(tiles),initial)
        groups=collections.defaultdict(list)
        for event in unpack_events(data,chart):groups[event[0]].append(event)
        self.assertEqual({t for t,events in groups.items() if any(e[1]==22 and e[2] for e in events)},{1,2,3})
        self.assertFalse(any(e[1]==27 for e in groups[1]),
                         'Masked glyphs must not publish stale BG cache tags')
        snapshots=[e for rows in groups.values() for e in rows if e[1]==22]
        image_ids={}
        for _,_,count,_,payload in snapshots:
            image_id=struct.unpack_from('<H',payload,2)[0]
            glyph_count=struct.unpack_from('<H',payload)[0]
            glyph_image=payload[34+6*count:34+6*count+glyph_count*32]
            if image_id in image_ids:self.assertEqual(image_ids[image_id],glyph_image)
            image_ids[image_id]=glyph_image
            fast=payload[34+6*count+glyph_count*32:]
            ox,oy,visible,negative_bytes=struct.unpack_from('<hhHH',fast)
            budgets=fast[8:40]
            negative=list(struct.unpack('<'+'H'*(negative_bytes//2),fast[40:40+negative_bytes]))
            packed=fast[40+negative_bytes:]
            self.assertLessEqual(len(fast),512)
            self.assertLessEqual(negative_bytes,64)
            self.assertEqual(len(packed),visible*4)
            cells=list(struct.iter_unpack('<hhH',payload[34:34+6*count]))
            expected=[];lines=[0]*32;neg=[]
            for wx,wy,tile in cells:
                x,y=wx-ox,wy-oy
                if not (-7<=x<256 and 25<=y<177):continue
                if x<0:neg.append(len(expected)*4)
                expected.append((x&255,y,tile,0x21))
                for line in range(y//8,(y+7)//8+1):lines[line]+=1
            self.assertEqual(list(struct.iter_unpack('<BBBB',packed)),expected)
            self.assertEqual(list(budgets),lines)
            self.assertEqual(negative,neg)
        for start in (0,1,2,3,4):
            world=dict(initial);pixels={i:tiles[i if start<=1 else 40+i] for i in range(1,41)}
            colors=[0]*96;colors[0]=100;colors[1]=200 if start<=2 else 300
            obj={};obj_palette=[];glyphs=b''
            seed_mask_pending=True
            for frame in range(start,6):
                for _,kind,i,v,payload in groups[frame]:
                    if kind==4:pixels[i]=payload[4:]
                    elif kind==7:colors[i]=v
                    elif kind==9:
                        x,y,slot=struct.unpack('<HHB',payload);world[x,y]=slot
                    elif kind==22:
                        count=struct.unpack_from('<H',payload)[0]
                        obj_palette=struct.unpack_from('<15H',payload,4)
                        obj={(x//8,y//8):slot for x,y,slot in struct.iter_unpack('<hhH',payload[34:34+6*i])}
                        if chart.get('stream_spill_incremental_trial') and seed_mask_pending:
                            for xy in obj:world[xy]=0
                            seed_mask_pending=False
                        glyphs=payload[34+6*i:34+6*i+count*32]
                        self.assertEqual(len(glyphs),count*32)
                        self.assertLessEqual(i,80)
                for xy,slot in initial.items():
                    expected=tiles[slot if frame==0 else 40+slot]
                    bg=pixels[world[xy]] if world[xy] else bytes(64)
                    decoded=decode_tile(glyphs[obj[xy]*32:(obj[xy]+1)*32],list(range(1,16))) if xy in obj else bytes(64)
                    for at,(raw,over) in enumerate(zip(bg,decoded)):
                        actual=obj_palette[over-1] if over else colors[raw-32] if raw else 0
                        want=colors[expected[at]-32] if expected[at] else 0
                        self.assertEqual(actual,want,(start,frame,xy,at))
                if frame>=4:self.assertFalse(obj,'Rotating camera must use the native Mode 7 track')
        self.assertEqual(chart['stream_spill_stats']['max_colors'],2)
        self.assertEqual(chart['stream_spill_stats']['max_objects'],40)


class StableStreamSpill(StreamSpill):
    def setUp(self):
        from unittest.mock import patch
        original=compile_spills
        def stable(chart,*args,**kwargs):
            chart['stream_spill_stable_trial']=True
            return original(chart,*args,**kwargs)
        replacement=patch(__name__+'.compile_spills',side_effect=stable)
        replacement.start();self.addCleanup(replacement.stop)

class IncrementalStreamSpill(StreamSpill):
    def setUp(self):
        from unittest.mock import patch
        original=compile_spills
        def incremental(chart,*args,**kwargs):
            chart['stream_spill_stable_trial']=True
            chart['stream_spill_incremental_trial']=True
            return original(chart,*args,**kwargs)
        replacement=patch(__name__+'.compile_spills',side_effect=incremental)
        replacement.start();self.addCleanup(replacement.stop)
