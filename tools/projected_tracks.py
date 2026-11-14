"""Project authored track frames into exact 4-bpp screen-space tiles.

This compiler retains every source frame and uses the same fixed-point
sampler as the Mode 7 PPU verifier. Planets and input remain live objects.
"""
import argparse,bisect,collections,json,struct,pickle
from pathlib import Path
import numpy as np
from mode1_tracks import encode_tile,decode_tile,pack_palettes,schedule
from viewport_cells import sampled_pixels

def exact_palettes(wanted):
    """Prove six-bank feasibility when greedy packing fails at a crossing."""
    from scipy.optimize import milp,Bounds,LinearConstraint
    from scipy.sparse import coo_matrix
    maximal=sorted((s for s in wanted if not any(s<q for q in wanted)),key=lambda s:(-len(s),tuple(sorted(s))))
    colors=sorted(set().union(*maximal));ids={c:i for i,c in enumerate(colors)}
    width=len(colors);variables=6*(width+len(maximal));rows=[];cols=[];values=[];lo=[];hi=[]
    def constraint(coefficients,lower,upper):
        n=len(lo);lo.append(lower);hi.append(upper)
        for column,value in coefficients:rows.append(n);cols.append(column);values.append(value)
    for bank in range(6):constraint(((bank*width+i,1) for i in range(width)),0,15)
    for i,group in enumerate(maximal):
        choices=[6*width+i*6+b for b in range(6)]
        constraint(((v,1) for v in choices),1,1)
        for bank,y in enumerate(choices):
            for color in group:constraint(((y,1),(bank*width+ids[color],-1)),-np.inf,0)
    lower=np.zeros(variables);upper=np.ones(variables)
    lower[6*width]=1  # The six banks are interchangeable.
    matrix=coo_matrix((values,(rows,cols)),shape=(len(lo),variables)).tocsc()
    answer=milp(np.zeros(variables),integrality=np.ones(variables),bounds=Bounds(lower,upper),
                constraints=LinearConstraint(matrix,lo,hi),options={'time_limit':30})
    if answer.x is None:raise ValueError(('Exact six-palette packing failed',answer.message))
    banks=[[c for c in colors if answer.x[b*width+ids[c]]>.5] for b in range(6)]
    assert all(len(b)<=15 for b in banks) and all(any(s<=set(b) for b in banks) for s in wanted)
    return banks

def anchored_palettes(wanted,anchors):
    """Keep common fill/edge pairs in the same CHR bitplanes across banks."""
    import random
    maximal=[s for s in wanted if not any(s<q for q in wanted)]
    for retained in range(len(anchors),-1,-1):
        for seed in range(16):
            banks=[list(p) for p in anchors[:retained]]+[[] for _ in range(6-retained)]
            order=list(maximal);random.Random(seed).shuffle(order);order.sort(key=lambda s:-len(s))
            for colors in order:
                candidates=[(len(colors-set(p)),i) for i,p in enumerate(banks) if len(set(p)|colors)<=15]
                if not candidates:break
                bank=banks[min(candidates)[1]];bank.extend(sorted(colors-set(bank)))
            else:return banks
    # Dense EX crossings can defeat the small anchored search even when
    # an exact six-bank packing exists. Try the general unanchored packer
    # before treating that heuristic failure as a hardware capacity limit.
    try:return pack_palettes(wanted)
    except ValueError:return exact_palettes(wanted)


class Source:
    def __init__(self,folder,level,copy_world=None):
        folder=Path(folder);self.chart=json.loads((folder/f'level{level}.json').read_text());c=self.chart
        self.patterns=np.frombuffer((folder/f'patterns{level}.bin').read_bytes(),dtype=np.uint8).reshape(-1,8,8)
        self.world=np.zeros((c['map_height'],c['map_width']),dtype=np.uint16)
        self.tags=np.array(c['pattern_initial'],dtype=np.uint16);self.events=collections.defaultdict(list)
        timeline=(folder/f'timeline{level}.bin').read_bytes()
        for xy,off in zip(c['cell_coordinates'],c['visibility_offsets']):
            n=struct.unpack_from('<H',timeline,off)[0]
            for f,v in struct.iter_unpack('<HH',timeline[off+2:off+2+n*4]):self.events[f].append((xy,v))
        self.tag_events=collections.defaultdict(list)
        for i,rows in enumerate(c['pattern_versions']):
            for f,v in rows:self.tag_events[f].append((i,v))
        self.color_events=collections.defaultdict(list)
        for f,i,v in c['track_palette_versions']:self.color_events[f].append((32+i,v))
        self.palette=np.zeros(256,dtype=np.uint16)
        self.cameras={f:(x,y) for f,x,y in c['camera_follow_versions']};self.camera=self.cameras[0]
        self.rotations={f:(c,s) for f,c,s in c.get('camera_sampling_versions',c.get('camera_rotation_versions',[]))}
        self.rotation=(256,0);self.overlays={f['frame']:f for f in c.get('projected_spill_frames',[])};self.overlay=None
        self.frame=-1
        from projected_copies import CopyWorld
        copies=copy_world if copy_world is not None else c.get('mawaru_copy_world')
        self.copies=CopyWorld(copies) if copies else None
        self.native_palette=None

    def advance(self,frame):
        assert frame>=self.frame,'Projection source must advance monotonically'
        if self.native_palette is not None:
            self.palette[:]=self.native_palette;self.native_palette=None
        for f in range(self.frame+1,frame+1):
            for (x,y),v in self.events.get(f,[]):self.world[y,x]=v
            for i,v in self.tag_events.get(f,[]):self.tags[i]=v
            for i,v in self.color_events.get(f,[]):self.palette[i]=v
            self.camera=self.cameras.get(f,self.camera);self.rotation=self.rotations.get(f,self.rotation)
            self.overlay=self.overlays.get(f,self.overlay)
        self.frame=frame

    def screen(self,frame):
        self.advance(frame);c=self.chart;top=c.get('viewport_top',32);bottom=c.get('viewport_bottom',176)
        if self.copies and self.copies.first<=frame<self.copies.last:
            self.native_palette=self.palette.copy()
            return self.copies.screen(frame,self.camera,self.rotation,self.palette,c)
        px,py=sampled_pixels(*self.camera,*self.rotation,c.get('viewport_center_y',104),bottom,top)
        valid=(px>=0)&(py>=0)&(px//8<self.world.shape[1])&(py//8<self.world.shape[0])
        output=np.zeros(px.shape,dtype=np.uint8)
        x,y=px[valid],py[valid]
        output[valid]=self.patterns[self.tags[self.world[y//8,x//8]],y&7,x&7]
        image=np.zeros((184,256),dtype=np.uint8);image[top+1:bottom+1]=output
        if self.overlay and self.overlay['objects']:
            # Restore the source pixels delegated to OBJ by the old atlas.
            o=self.overlay;glyphs=bytes.fromhex(o['glyphs']);swatches=o['palette']
            indices={int(v):i for i,v in reversed(list(enumerate(self.palette))) if i>=32}
            for x,y,g in o['objects']:
                raw=decode_tile(glyphs[g*32:g*32+32],list(range(1,len(swatches)+1)))
                part=np.array([indices[swatches[v-1]] if v else 0 for v in raw],dtype=np.uint8).reshape(8,8)
                dest=image[y:y+8,x:x+8];mask=part!=0;dest[mask]=part[mask]
        # Alias equal hardware colors before palette packing. Numeric source
        # indices are not distinct colors, and retaining those aliases makes
        # a 4-bpp atlas churn as hidden source materials enter and leave.
        canonical={};translation=np.arange(256,dtype=np.uint8)
        for i in range(32,128):translation[i]=canonical.setdefault(int(self.palette[i]),i)
        normalized=translation[image]
        assert np.array_equal(self.palette[image],self.palette[normalized]),'Palette alias changed a displayed color'
        return normalized


def encode_screen(image,palettes,glyphs,lookup,encodings,anchors=()):
    """Encode every sampled color exactly; never quantize or omit a tile."""
    blocks=image[32:184].reshape(19,8,32,8).transpose(0,2,1,3).reshape(608,64)
    unique,inverse=np.unique(np.ascontiguousarray(blocks).view('V64').ravel(),return_inverse=True)
    surfaces={i:bytes(p) for i,p in enumerate(unique) if any(bytes(p))}
    wanted={frozenset(p)-{0} for p in surfaces.values()}
    for colors in sorted(wanted,key=lambda s:(-len(s),tuple(sorted(s)))):
        if any(colors<=set(p) for p in palettes):continue
        choices=[(len(colors-set(p)),i) for i,p in enumerate(palettes) if len(set(p)|colors)<=15]
        if choices:palettes[min(choices)[1]].extend(sorted(colors-set(palettes[min(choices)[1]])))
        elif len(palettes)<6:palettes.append(sorted(colors))
        else:palettes[:]=anchored_palettes(wanted,anchors) if anchors else pack_palettes(wanted);break
    refs={};encoded={}
    for i,raw in surfaces.items():
        colors=frozenset(raw)-{0}
        bank=next(i for i,p in enumerate(palettes) if colors<=set(p))
        key=raw,tuple(palettes[bank])
        if key not in encodings:
            glyph=encode_tile(raw,palettes[bank])
            assert decode_tile(glyph,palettes[bank])==raw,'Projected tile changed a source pixel'
            if glyph not in lookup:lookup[glyph]=len(glyphs);glyphs.append(glyph)
            encodings[key]=lookup[glyph]
        encoded[i]=(encodings[key],bank)
    for i,index in enumerate(inverse):
        if index in encoded:refs[i]=encoded[index]
    return refs,tuple(tuple(p) for p in palettes)


def compile_section(folder,level,start,end,copy_world=None):
    source=Source(folder,level,copy_world);palettes=[];glyphs=[bytes(32)];lookup={glyphs[0]:0};encodings={};frames=[]
    # Stable bank/color assignments avoid recreating every visible glyph
    # merely because a new source color enters the viewport.
    wanted=set();frequencies=collections.Counter()
    for frame in range(start,end+1):
        image=source.screen(frame)
        blocks=image[32:184].reshape(19,8,32,8).transpose(0,2,1,3).reshape(608,64)
        unique,counts=np.unique(np.ascontiguousarray(blocks).view('V64').ravel(),return_counts=True)
        for raw,count in zip(unique,counts):
            colors=frozenset(bytes(raw))-{0}
            if colors:wanted.add(colors)
            if len(colors)==2:frequencies[colors]+=int(count)
    anchors=[]
    for pair,count in frequencies.most_common(6):
        # The imported two-color materials use even indices for fill and
        # odd indices for contour. Equal-RGB aliases remain exact colors.
        anchors.append(tuple(sorted(pair,key=lambda i:(i%2,i))))
    try:
        if len(set().union(*wanted))>90:raise ValueError('Use frame-local banks')
        palettes=anchored_palettes(wanted,anchors)
    except ValueError:palettes=[list(p) for p in anchors]
    source=Source(folder,level,copy_world)
    for frame in range(start,end+1):
        image=source.screen(frame)
        try:frames.append(encode_screen(image,palettes,glyphs,lookup,encodings,anchors))
        except ValueError as error:raise ValueError(('Projected frame palette capacity',level,frame,len(set(image.ravel())-{0}),error.args)) from error
    return glyphs,frames


def map_cost(indices):
    spans=[]
    for addr in sorted(i*2 for i in indices):
        if spans and addr-spans[-1][1]-2<17:spans[-1][1]=addr
        else:spans.append([addr,addr])
    return sum(b-a+2+64 for a,b in spans)


def snapshot_pose(payload,count):
    """Restore a complete pose without depending on any preceding atlas."""
    palette=payload[:96];tilemap=payload[96:1312];at=1312;glyphs=[]
    assert len(palette)==96 and len(tilemap)==1216
    for _ in range(count):
        flag=payload[at];at+=1;assert flag in (0,1,2)
        size=16 if flag else 32;glyph=payload[at:at+size];at+=size
        assert len(glyph)==size
        if flag==1:glyph+=bytes(16)
        elif flag==2:glyph=bytes(16)+glyph
        glyphs.append(glyph)
    assert at==len(payload)
    return palette,tilemap,glyphs


def raw_seeds(index,data,*,snapshot=False,clone_state=False):
    from animation_bulk import HEADER,records
    entries=list(struct.iter_unpack('<HHI',index))[:-1];count=entries[-1][0]//64+2
    result=bytearray(count*4);palette=bytes(96);tilemap=bytearray(4096);atlas=bytearray(32768);symbols=b'';cursor=0;glyph_bytes=0
    clones=bytes(42)
    for seed in range(count):
        while cursor<len(entries) and entries[cursor][0]<seed*64:
            _,_,choice=entries[cursor];_,size,offset=struct.unpack_from('<HHI',data,choice)
            packet=data[offset:offset+size]
            for a,b,t,k,i,v in records(packet):
                at=a+7
                if k==30:
                    flags=struct.unpack_from('<H',packet,at)[0];assert flags==2
                    palette=packet[at+2:at+98]
                elif k==37:
                    for slot,glyph in inline_pixels(packet[at:b],i):atlas[slot*32:slot*32+32]=glyph
                elif k in (41,42,44):
                    if k==42:
                        pointer=struct.unpack_from('<I',packet,at)[0]
                        pose=data[pointer:pointer+v];pt,pk,i,pv=HEADER.unpack_from(pose)
                        assert pk in (41,44) and pv+14==v and pose[-7:]==HEADER.pack(65535,255,0,0)
                        body=pose[7:-7]
                    else:body=packet[at:b];pk=k
                    if pk==44:
                        assert len(body)==1312+i*32
                        palette,words=body[:96],body[96:1312]
                        glyphs=[body[a:a+32] for a in range(1312,len(body),32)]
                    else:palette,words,glyphs=snapshot_pose(body,i)
                    tilemap[256:1472]=words;glyph_bytes=i*32
                    atlas[32:32+glyph_bytes]=b''.join(glyphs)
                elif k==28:symbols=packet[at:b]
                elif k==43:clones=struct.pack('<H',i)+packet[at:b]+bytes(40-v)
                elif k==31:
                    for _ in range(i):
                        dest,length=struct.unpack_from('<HH',packet,at);at+=4
                        tilemap[dest:dest+length]=packet[at:at+length];at+=length
            cursor+=1
        struct.pack_into('<I',result,seed*4,len(result))
        result+=struct.pack('<H',cursor)+(struct.pack('<H',glyph_bytes|(0x8000 if clone_state else 0)) if snapshot else b'')+(clones if clone_state else b'')+palette+tilemap+atlas+struct.pack('<H',len(symbols))+symbols
    return bytes(result)


def inline_pixels(payload,count):
    """Restore omitted zero bitplanes exactly, including checkpoint seeds."""
    at=0
    for _ in range(count):
        tag=struct.unpack_from('<H',payload,at)[0];at+=2
        size=16 if tag&0xC000 else 32
        glyph=payload[at:at+size];at+=size
        if tag&0x8000:glyph+=bytes(16)
        elif tag&0x4000:glyph=bytes(16)+glyph
        assert len(glyph)==32
        yield tag&1023,glyph
    assert at==len(payload),'Inline glyph packet length differs'


def pack_inline_pixels(payload,count):
    out=bytearray()
    assert len(payload)==count*34
    for at in range(0,len(payload),34):
        slot=struct.unpack_from('<H',payload,at)[0];glyph=payload[at+2:at+34]
        if not any(glyph[16:]):out+=struct.pack('<H',slot|0x8000)+glyph[:16]
        elif not any(glyph[:16]):out+=struct.pack('<H',slot|0x4000)+glyph[16:]
        else:out+=payload[at:at+34]
    assert list(inline_pixels(out,count))==[(struct.unpack_from('<H',payload,p)[0],payload[p+2:p+34]) for p in range(0,len(payload),34)]
    return bytes(out)


def prepare(source,output,level):
    """Compile a complete canonical chart; partial prototypes cannot ship."""
    from animation_bulk import HEADER,records
    from animation_catchup import unpack_events
    from sa1_stream import indexed_packets,rom_index
    source=Path(source);output=Path(output);output.mkdir(parents=True,exist_ok=True)
    chart=json.loads((source/f'level{level}.json').read_text());last=chart['notes'][-1]['frame']-1
    glyphs,frames=compile_section(source,level,0,last)
    glyphs,frames=share_flipped_glyphs(glyphs,frames)
    return write_plan(source,output,level,glyphs,frames)


def write_plan(source,output,level,glyphs,frames):
    from animation_bulk import HEADER,records
    from animation_catchup import unpack_events
    from sa1_stream import indexed_packets,rom_index
    source=Path(source);output=Path(output);output.mkdir(parents=True,exist_ok=True)
    chart=json.loads((source/f'level{level}.json').read_text())
    previous={};bounds=[]
    for refs,palette in frames:
        bounds.append(0 if refs==previous else map_cost(refs.keys()|previous.keys()));previous=refs
    bindings=[];priorities=[];jobs,stats=schedule(frames,glyphs,lambda t:5000-bounds[t],128,bindings_size=608,bindings_out=bindings,priorities_out=priorities,
                                   initial_prefetch=True,ramp_prefetch=False,eviction_horizon=1)
    events=[(t,k,i,v,p) for t,k,i,v,p in unpack_events((source/f'animation{level}.bin').read_bytes(),chart)
            if k not in (4,9,12,14,22,25,27,29,30,31,35,36)]
    for t,count,payload in jobs:
        flags=struct.unpack_from('<H',payload)[0];head=2+1216*bool(flags&1)+96*bool(flags&2)
        if flags&2:events.append((t,30,0,98,struct.pack('<H',2)+payload[2+1216*bool(flags&1):head]))
        for at in range(0,count,128):
            n=min(128,count-at);body=pack_inline_pixels(payload[head+at*34:head+(at+n)*34],n)
            events.append((t,37,n,len(body),body))
    previous=[0]*608
    for t,values in enumerate(bindings):
        rows=collections.defaultdict(list)
        for i,(old,new) in enumerate(zip(previous,values)):
            if old!=new:rows[i//32].append(i)
        body=bytearray()
        for row,positions in sorted(rows.items()):
            first=min(positions);end=max(positions)+1
            body+=struct.pack('<HH',256+first*2,(end-first)*2)+struct.pack('<'+'H'*(end-first),*values[first:end])
        if body:events.append((t,31,len(rows),len(body),bytes(body)))
        stats[t]['map_dma_cost']=map_cost(i for i,(a,b) in enumerate(zip(previous,values)) if a!=b)
        stats[t]['total_dma_cost']=stats[t]['dma_cost']+stats[t]['map_dma_cost'];previous=values
    for t,(required,slots) in enumerate(priorities):
        body=struct.pack('<'+'H'*len(slots),*slots)
        events.append((t,39,required,len(body),body))
    events.sort(key=lambda e:e[0]);animation=b''.join(HEADER.pack(t,k,i,v)+p for t,k,i,v,p in events)+HEADER.pack(65535,255,0,0)
    chart.update(mode1_tracks=2,mode1_projected=True,mode1_glyph_count=0,sa1_stream_format=11,
                 sa1_inline_patterns=True,sa1_delta_patterns=False,sa1_row_dictionary=False,stream_row_offset=0,
                 stream_direct_patterns_trial=False,stream_direct_spill_trial=False,stream_bulk_rows_trial=False,
                 stream_merge_counts=[2,4,8],stream_obj_spill=False,catchup_disabled=True)
    for key in list(chart):
        if key.startswith('fallback_stream_'):chart.pop(key)
    chart.pop('mode1_icon_base',None)
    index,data=indexed_packets(animation,chart);rom_index(index)
    chart['stream_packets']=len(index)//8
    chart['projected_plan']=dict(source_frames=len(frames),unique_glyphs=len(glyphs),
        max_dma_cost=max(s['total_dma_cost'] for s in stats[1:]),pixel_exact=True,frame_step=1)
    for name,blob in [('stream_index',index),('stream_data',data),('resident_stream',bytes(2)),('mode1_seeds',raw_seeds(index,data))]:
        (output/f'{name}{level}.bin').write_bytes(blob)
    (output/f'level{level}.json').write_text(json.dumps(chart,indent=2))
    (output/f'projected_stats{level}.json').write_text(json.dumps(stats))
    print(chart['code'],chart['projected_plan'],len(data),'stream bytes',flush=True)


def share_flipped_glyphs(glyphs,frames):
    """Use the PPU's native H/V flips; keep every pixel and every frame."""
    reverse=bytes(int(f'{i:08b}'[::-1],2) for i in range(256))
    unique=[bytes(32)];lookup={unique[0]:0};aliases=[]
    for glyph in glyphs:
        vertical=b''.join(glyph[base+y:base+y+2] for base in (0,16) for y in range(14,-1,-2))
        variants=(glyph,glyph.translate(reverse),vertical,vertical.translate(reverse))
        best=min(range(4),key=lambda i:variants[i]);canonical=variants[best]
        if canonical not in lookup:lookup[canonical]=len(unique);unique.append(canonical)
        aliases.append((lookup[canonical],(16 if best&1 else 0)+(32 if best&2 else 0)))
    mapped=[]
    for refs,palettes in frames:
        mapped.append(({i:(aliases[g][0],bank+aliases[g][1]) for i,(g,bank) in refs.items()},palettes))
    return unique,mapped


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--source',type=Path,required=True);ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--level',type=int,required=True);ap.add_argument('--start',type=int,required=True);ap.add_argument('--end',type=int,required=True)
    a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    glyphs,frames=compile_section(a.source,a.level,a.start,a.end)
    print('Exact projected glyphs',len(glyphs),'frames',len(frames),flush=True)
    with (a.out/'frames.pkl').open('wb') as f:pickle.dump((glyphs,frames),f)
    bindings=[];jobs,stats=schedule(frames,glyphs,budget=2500,lookahead=128,bindings_size=608,bindings_out=bindings,
                                  initial_prefetch=True,ramp_prefetch=False,eviction_horizon=1)
    previous=[0]*608
    for values,row in zip(bindings,stats):
        changed=[i*2 for i,(a,b) in enumerate(zip(previous,values)) if a!=b]
        spans=[]
        for addr in changed:
            if spans and addr-(spans[-1][1]+2)<17:spans[-1][1]=addr
            else:spans.append([addr,addr])
        row['map_dma_cost']=sum(b-a+2+64 for a,b in spans)
        row['total_dma_cost']=row['dma_cost']+row['map_dma_cost'];previous=values
    summary=dict(glyphs=len(glyphs),frames=len(frames),max_required=max(r['required'] for r in stats[1:]),
                 max_pattern_dma=max(r['dma_cost'] for r in stats[1:]),max_total_dma=max(r['total_dma_cost'] for r in stats[1:]),
                 peak_live=max(len(set(b)-{0}) for b in bindings))
    print(summary,flush=True)
    (a.out/'stats.json').write_text(json.dumps(summary,indent=2))
    (a.out/'frames-stats.json').write_text(json.dumps(stats))
    (a.out/'glyphs.bin').write_bytes(b''.join(glyphs))
    (a.out/'jobs.bin').write_bytes(b''.join(struct.pack('<HHH',t+a.start,n,len(b))+b for t,n,b in jobs))
    (a.out/'bindings.bin').write_bytes(b''.join(struct.pack('<608H',*b) for b in bindings))

if __name__=='__main__':main()
