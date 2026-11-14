"""Lossless 4-bpp track plans for unrotated charts; no temporal resampling."""
import argparse,bisect,collections,json,random,struct
from pathlib import Path
from resident_patterns import changes


def pack_palettes(colors):
    maximal=sorted((s for s in colors if not any(s<q for q in colors)),key=lambda s:tuple(sorted(s)))
    best=None
    for seed in range(128):
        order=list(maximal);random.Random(seed).shuffle(order);order.sort(key=lambda s:-len(s))
        palettes=[]
        for color in order:
            choices=[(len(color-set(p)),i) for i,p in enumerate(palettes) if len(set(p)|color)<=15]
            if choices:
                p=palettes[min(choices)[1]];p.extend(sorted(color-set(p)))
            else:palettes.append(sorted(color))
        if best is None or len(palettes)<len(best):best=palettes
        if len(best)<=6:return best
    raise ValueError(('Cannot preserve colors in six BG palettes',len(best)))


def encode_tile(pixels,palette):
    lookup={0:0,**{color:i+1 for i,color in enumerate(palette)}}
    out=bytearray(32)
    for y in range(8):
        for x in range(8):
            color=lookup[pixels[y*8+x]]
            for plane in range(4):out[(plane//2)*16+y*2+plane%2]|=((color>>plane)&1)<<(7-x)
    return bytes(out)


def decode_tile(glyph,palette):
    colors=[0]+list(palette);out=bytearray()
    for y in range(8):
        for x in range(8):
            value=sum(((glyph[(p//2)*16+y*2+p%2]>>(7-x))&1)<<p for p in range(4))
            out.append(colors[value])
    return bytes(out)


def compile_frames(chart,animation,patterns):
    assert not chart.get('camera_rotation_versions') and not chart.get('camera_raster_shift_versions')
    groups=collections.defaultdict(list)
    for time,kind,value in changes(animation):groups[time].append((kind,value))
    raw=[patterns[i:i+64] for i in range(0,len(patterns),64)]
    colors=[frozenset(p)-{0} for p in raw]
    tags=list(chart['pattern_initial']);active={0};palettes=[];frames=[];glyphs=[bytes(32)];glyph_ids={bytes(32):0};encodings={};repacked=0
    for time in range(max(groups)+1):
        for kind,value in groups[time]:
            if kind=='tag':tags[value[0]]=value[1]
            else:active=set(value)
        wanted={colors[tags[slot]] for slot in active}
        for color in sorted(wanted,key=lambda s:(-len(s),tuple(sorted(s)))):
            if any(color<=set(p) for p in palettes):continue
            choices=[(len(color-set(p)),i) for i,p in enumerate(palettes) if len(set(p)|color)<=15]
            if choices:palettes[min(choices)[1]].extend(sorted(color-set(palettes[min(choices)[1]])))
            elif len(palettes)<6:palettes.append(sorted(color))
            else:
                palettes=pack_palettes(wanted);repacked+=1;break
        refs={0:(0,0)}
        for slot in sorted(active-{0}):
            tag=tags[slot]
            if not tag:refs[slot]=(0,0);continue
            bank=next(i for i,p in enumerate(palettes) if colors[tag]<=set(p))
            key=(tag,tuple(palettes[bank]))
            if key not in encodings:
                glyph=encode_tile(raw[tag],palettes[bank])
                assert decode_tile(glyph,palettes[bank])==raw[tag]
                if glyph not in glyph_ids:glyph_ids[glyph]=len(glyphs);glyphs.append(glyph)
                encodings[key]=glyph_ids[glyph]
            refs[slot]=(encodings[key],bank)
        frames.append((refs,tuple(tuple(p) for p in palettes)))
    return glyphs,frames,repacked


def schedule(frames,glyphs,budget=3000,lookahead=64,*,bindings_size=256,bindings_out=None,
             initial_prefetch=False,ramp_prefetch=True,eviction_horizon=None,reuse_bindings=False,
             palette_size=16,palette_count=6,palette_offset=2,cache_capacity=1024,binding_shift=10,priorities_out=None):
    scenes=[{glyph for glyph,bank in refs.values()} for refs,pal in frames]
    glyph_bytes=len(glyphs[0])
    future=collections.defaultdict(list)
    for t,scene in enumerate(scenes):
        for glyph in scene:future[glyph].append(t)
    cache=[-1]*cache_capacity;cache[0]=0;locations={0:0};cursor=1;jobs=[];stats=[]
    last_bindings=None;last_palette=None
    horizon=collections.Counter(g for scene in scenes[1:lookahead+1] for g in scene)
    for t,(refs,palettes) in enumerate(frames):
        scene=scenes[t];uploads=[];next_uses={}
        def nextuse(glyph):
            if glyph not in next_uses:
                rows=future[glyph];i=bisect.bisect_right(rows,t)
                next_uses[glyph]=rows[i] if i<len(rows) else 65535
            return next_uses[glyph]
        def victims():return [i for i in range(1,cache_capacity) if cache[i] not in scene]
        def put(glyph,required=False,preferred=None):
            nonlocal cursor
            available=victims();far=max(nextuse(cache[i]) for i in available)
            deadline=t if required else nextuse(glyph)
            horizon=t+(lookahead if eviction_horizon is None else eviction_horizon)
            threshold=min(far,max(deadline+1,horizon))
            eligible=[i for i in available if nextuse(cache[i])>=threshold]
            slot=preferred if preferred is not None and preferred in available and preferred else min(eligible,key=lambda i:(i-cursor)%cache_capacity)
            if cache[slot]>=0:del locations[cache[slot]]
            cache[slot]=glyph;locations[glyph]=slot;uploads.append((slot,glyph));cursor=(slot+1)%cache_capacity
        preferences={}
        if reuse_bindings and last_bindings is not None:
            for logical,(glyph,bank) in refs.items():
                preferences.setdefault(glyph,last_bindings[logical]&((1<<binding_shift)-1))
        for glyph in sorted(scene-locations.keys()):put(glyph,required=True,preferred=preferences.get(glyph))
        required=len(uploads)
        def cost():
            # worker_mode1_prepare bridges one unchanged glyph between dirty
            # neighbors. Charge those exact runs, including the bridge bytes.
            spans=[]
            for slot in sorted(s for s,g in uploads):
                if spans and slot<=spans[-1][1]+2:spans[-1][1]=slot
                else:spans.append([slot,slot])
            return sum((b-a+1)*glyph_bytes+60 for a,b in spans)
        candidates=sorted(horizon.keys()-locations.keys(),key=lambda g:(nextuse(g),g))
        for glyph in candidates:
            # A render may consume two adjacent chart timestamps. Ramp up
            # speculative loading after an idle interval to avoid a double burst.
            ceiling=budget(t) if callable(budget) else budget
            if t==0 and initial_prefetch:ceiling=1000000
            if ramp_prefetch and stats and stats[-1]['uploads']==0:ceiling=min(ceiling,1000)
            if cost()+glyph_bytes+60>ceiling:break
            ahead=nextuse(glyph)
            available=victims()
            # Candidates are ordered by their next deadline. If none of the
            # available slots survives this candidate, later ones cannot be
            # prefetched either; scanning them is quadratic wasted work.
            if max(nextuse(cache[i]) for i in available)<=ahead:break
            put(glyph)
        if t+1<len(scenes):
            horizon.subtract(scenes[t+1])
            for g in scenes[t+1]:
                if horizon[g]==0:del horizon[g]
        if t+lookahead+1<len(scenes):horizon.update(scenes[t+lookahead+1])
        bindings=[0]*bindings_size
        for logical,(glyph,bank) in refs.items():
            bindings[logical]=locations[glyph]|((bank+palette_offset)<<binding_shift) if glyph else 0
        palette=[v for bank in range(palette_count) for v in ([0]+list(palettes[bank])+[0]*(palette_size-1-len(palettes[bank])) if bank<len(palettes) else [0]*palette_size)]
        flags=(1 if bindings!=last_bindings else 0)|(2 if palette!=last_palette else 0)
        payload=bytearray(struct.pack('<H',flags))
        if flags&1:payload+=struct.pack('<'+'H'*bindings_size,*bindings)
        if flags&2:payload+=bytes(palette)
        for slot,glyph in sorted(uploads):payload+=struct.pack('<H',slot)+glyphs[glyph]
        if flags or uploads:jobs.append((t,len(uploads),bytes(payload)))
        stats.append(dict(time=t,required=required,uploads=len(uploads),dma_cost=cost()))
        if bindings_out is not None:bindings_out.append(tuple(bindings))
        if priorities_out is not None:
            required=[i for i,g in enumerate(cache) if g>0 and g in scene]
            future_slots=sorted((i for i,g in enumerate(cache) if g>0 and g not in scene and nextuse(g)<65535),key=lambda i:(nextuse(cache[i]),i))
            priorities_out.append((len(required),tuple(required+future_slots)))
        last_bindings=bindings;last_palette=palette
    return jobs,stats


def compile_maps(c,timeline,trackmap,data):
 from verify_render import map_reader
 tile=map_reader(trackmap,c['map_height'],c.get('map_offset_shift',0));nodes=[]
 for off in c['visibility_offsets'][:c['visibility_cells']]:
  count=struct.unpack_from('<H',timeline,off)[0];rows=list(struct.iter_unpack('<HH',timeline[off+2:off+2+count*4]));nodes.append(([t for t,v in rows],[v for t,v in rows]))
 at=0;jobs={}
 while at<len(data):
  t,count,size=struct.unpack_from('<HHH',data,at);at+=6;jobs[t]=data[at:at+size];at+=size
 views={int(t):v for t,v in c['render_viewports'].items()};view=views[0];bindings=[0]*256;shadow=[0]*2048;out=bytearray()
 for t in range(max(views)+1):
  if t in jobs and struct.unpack_from('<H',jobs[t])[0]&1:bindings=list(struct.unpack_from('<256H',jobs[t],2))
  if t in views:view=views[t]
  x,y,w,h=view;changed={}
  for wy in range(y,y+h):
   for wx in range(x,x+w):
    logical=tile(wx,wy)
    if logical&0x2000:
     ts,vs=nodes[(logical&0x1fff)|((logical&0xc000)>>1)];i=bisect.bisect_right(ts,t)-1;logical=vs[i] if i>=0 else 0
    value=bindings[logical];addr=(wy&31)*32+(wx&31)+(1024 if wx&32 else 0)
    if shadow[addr]!=value:shadow[addr]=value;changed.setdefault(addr//32,[]).append(addr)
  payload=bytearray()
  for row,addresses in sorted(changed.items()):
   a,b=min(addresses),max(addresses)+1;payload+=struct.pack('<HH',a*2,(b-a)*2)+struct.pack('<'+'H'*(b-a),*shadow[a:b])
  if payload:out+=struct.pack('<HHH',t,len(changed),len(payload))+payload
 return out

def symbol_candidates(chart,animation,margin=32):
    """Conservative spatial index; runtime alpha and screen clipping remain final."""
    from animation_bulk import records,HEADER
    groups=collections.defaultdict(list)
    for a,b,t,k,i,v in records(animation):
        if k in (2,3,28):groups[t].append((k,i,v,animation[a+7:b]))
    views={int(t):v for t,v in chart['render_viewports'].items()}
    xs=[n['x'] for n in chart['notes']];ys=[n['y'] for n in chart['notes']]
    eligible=[];previous=None;view=views[0];out=bytearray()
    for t in range(max(max(groups),max(views))+1):
        for k,i,v,payload in groups.get(t,[]):
            if k==28:eligible=list(struct.unpack('<'+'H'*(len(payload)//2),payload))
            elif k==2:xs[i]=v if v<32768 else v-65536
            else:ys[i]=v if v<32768 else v-65536
        if t in views:view=views[t]
        x,y,w,h=view
        current=[n for n in eligible if x*8-margin<=xs[n]<(x+w)*8+margin and y*8-margin<=ys[n]<(y+h)*8+margin]
        if current!=previous:
            payload=struct.pack('<'+'H'*len(current),*current)
            out+=HEADER.pack(t,28,len(current),len(payload))+payload
            previous=current
    return bytes(out)


def icon_descriptors(chart):
    notes=chart['notes'];out=bytearray()
    assert len(notes)<=512
    for i,n in enumerate(notes):
        flags=n['flags'];icons=[(0,0)]*4
        if flags&3:icons[0]=(0x3220 if flags&3==1 else 0x3422,0)
        if flags&4:icons[1]=(0x3624+(2 if n['ccw'] else 0),-14 if flags&3 else 0)
        if flags&32:
            if n.get('hold_length',-1)>=0:icons[2]=(0x346A if n['hold_length']>=1 else 0x3268,0)
            elif i and notes[i-1].get('hold_length',-1)>=0:icons[2]=(0x346C if notes[i-1]['hold_length']>=1 else 0x326C,0)
            elif i and n.get('planets',2)!=notes[i-1].get('planets',2):icons[2]=(0x366E if n.get('planets',2)==3 else 0x3648,0)
        if flags&64:icons[3]=(0x364A,-14 if flags&55 else 0)
        for tile,dy in icons:out+=struct.pack('<Hbb',tile,1 if tile&255==106 else 0,dy)
    return bytes(out)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--source',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--levels',type=int,nargs='+',required=True);ap.add_argument('--budget',type=int,default=1000);ap.add_argument('--lookahead',type=int,default=256);args=ap.parse_args();args.out.mkdir(parents=True,exist_ok=True)
    for n in args.levels:
        c=json.loads((args.source/f'level{n}.json').read_text())
        glyphs,frames,repacked=compile_frames(c,(args.source/f'animation{n}.bin').read_bytes(),(args.source/f'patterns{n}.bin').read_bytes())
        print(n,'exact glyphs',len(glyphs),'palette repacks',repacked,flush=True)
        jobs,stats=schedule(frames,glyphs,args.budget,args.lookahead)
        (args.out/f'mode1_glyphs{n}.bin').write_bytes(b''.join(glyphs))
        (args.out/f'mode1_jobs{n}.bin').write_bytes(b''.join(struct.pack('<HHH',t,count,len(data))+data for t,count,data in jobs))
        (args.out/f'mode1_maps{n}.bin').write_bytes(compile_maps(c,(args.source/f'timeline{n}.bin').read_bytes(),(args.source/f'track_map{n}.bin').read_bytes(),(args.out/f'mode1_jobs{n}.bin').read_bytes()))
        (args.out/f'mode1_stats{n}.json').write_text(json.dumps(stats))
        print(n,'jobs',len(jobs),'peak DMA',max(r['dma_cost'] for r in stats),flush=True)

if __name__=='__main__':main()
