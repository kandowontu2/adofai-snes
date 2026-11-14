"""Bounded per-frame MSU packets decoded by SA-1, with ROM seek indices."""
import collections,json,struct
from pathlib import Path
from animation_bulk import HEADER,records
LIMIT=14336
SUPPORTED={0,1,2,3,4,6,7,8,9,10,11,12,13,14,15,17,18,19,22,23,25,27,28,29,30,31,32,33,34,35,36,37,39,41,42,43,44}

def bulk_map_rows(data,chart):
    if not chart.get('stream_bulk_rows_trial'):return data
    rows=list(records(data));out=bytearray();j=0
    while j<len(rows):
        start=j;t=rows[j][2];body=bytearray()
        while j<len(rows) and rows[j][2:4]==(t,9):
            a,b,_,_,cell,count=rows[j]
            x,y=struct.unpack_from('<HH',data,a+7)
            if not count or (x&127)+count>128 or len(body)+8+count>LIMIT-14:break
            body+=struct.pack('<HH',cell,count)+data[a+7:b];j+=1
        if j-start>=3:out+=HEADER.pack(t,36,j-start,len(body))+body
        else:
            a,b,*_=rows[start];out+=data[a:b];j=start+1
    return bytes(out)

def bulk_inline_patterns(data,chart):
    if not chart.get('stream_direct_patterns_trial'):return data
    rows=list(records(data));out=bytearray();j=0
    while j<len(rows):
        a,b,t,k,i,v=rows[j];end=j+1
        if k==4:
            while end<len(rows) and end-j<128 and rows[end][2:4]==(t,4):end+=1
        group=rows[j:end]
        if len(group)>=3 and len({r[4] for r in group})==len(group):
            group=sorted(group,key=lambda r:r[4])
            body=b''.join(struct.pack('<HH',slot,tag)+data[p+7:p+11] for p,q,_,_,slot,tag in group)
            body+=b''.join(data[p+11:q] for p,q,_,_,slot,tag in group)
            out+=HEADER.pack(t,34,len(group),len(body))+body
        else:end=j+1;out+=data[a:b]
        j=end
    return bytes(out)

def direct_spill_packet(data,chart):
    """Route an inline OBJ image directly to its final RAM destination."""
    if not chart.get('stream_direct_spill_trial'):return data
    if chart.get('stream_direct_patterns_trial'):
        routes=[]
        for a,b,t,k,i,v in records(data):
            if k==4:routes.append((a+11,64,i*64))
            elif k==34:
                for n in range(i):
                    slot=struct.unpack_from('<H',data,a+7+n*8)[0]
                    routes.append((a+7+i*8+n*64,64,slot*64))
            elif k==22:
                glyphs=struct.unpack_from('<H',data,a+7)[0]
                image=a+7+34+(i&0x7FFF)*(4 if i&0x8000 else 6)
                if glyphs:routes.append((image,glyphs*32,0x9000))
                fast=image+glyphs*32
                if fast+40<=b:
                    visible,negative=struct.unpack_from('<HH',data,fast+4)
                    start=fast+40+negative
                    assert start+visible*4==b
                    if visible:routes.append((start,visible*4,0xec00))
        merged=[]
        for a,n,d in routes:
            if merged and a==merged[-1][0]+merged[-1][1] and d==merged[-1][2]+merged[-1][1]:
                old,size,dest=merged[-1];merged[-1]=(old,size+n,dest)
            else:merged.append((a,n,d))
        routes=merged
        if 0<len(routes)<=128:
            prefix=7+len(routes)*6
            table=b''.join(struct.pack('<HHH',a+prefix,n,d) for a,n,d in routes)
            assert len(data)+prefix<=16384
            return HEADER.pack(HEADER.unpack_from(data)[0],33,len(routes),len(table))+table+data
    images=[(a,t,i,struct.unpack_from('<H',data,a+7)[0])
            for a,b,t,k,i,v in records(data) if k==22]
    if not images:return data
    assert len(images)==1
    a,t,cells,glyphs=images[0]
    if not glyphs:return data
    start=a+7+34+(cells&0x7FFF)*(4 if cells&0x8000 else 6)
    size=glyphs*32
    assert start+size<=len(data)
    # Seven extra bytes precede the original packet. The worker ignores
    # this transport header; all ordinary record offsets remain coherent.
    return HEADER.pack(t,32,start+7,size)+data

def rom_index(data):
    """Only times vary: each MSU choice/seed record is exactly 544 bytes."""
    out=bytearray()
    for i,(time,size,offset) in enumerate(struct.iter_unpack('<HHI',data)):
        assert offset==i*544, 'Nonuniform packet directory'
        out+=struct.pack('<H',time)
    assert len(out)<=65536
    return bytes(out)


def compact_tags(data):
    rows=list(records(data));out=bytearray();a=0
    while a<len(rows):
        p,e,t,k,i,v=rows[a];b=a+1
        if k==27:
            while b<len(rows) and rows[b][2:4]==(t,27):b+=1
        if b-a>=3:
            body=b''.join(struct.pack('<HH',r[4],r[5]) for r in rows[a:b])
            out+=HEADER.pack(t,25,b-a,len(body))+body
        else:b=a+1;out+=data[p:e]
        a=b
    return bytes(out)


def compact_map_rows(data):
    """Combine adjacent writes, preserving every cell, timestamp and order."""
    rows=[]
    for a,b,t,k,i,v in records(data):
        if k==29:
            for cell,coord,value in struct.iter_unpack('<HHB',data[a+7:b]):
                rows.append((t,9,cell,1,struct.pack('<HHB',coord&127,coord>>7,value)))
        else:rows.append((t,k,i,v,data[a+7:b]))
    out=bytearray();j=0
    while j<len(rows):
        t,k,i,v,body=rows[j];j+=1
        if k==9:
            x,y=struct.unpack_from('<HH',body);pixels=bytearray(body[4:])
            while j<len(rows):
                nt,nk,ni,nv,nb=rows[j]
                if (nt,nk,ni)!=(t,9,i+len(pixels)):break
                nx,ny=struct.unpack_from('<HH',nb)
                if (nx,ny)!=(x+len(pixels),y) or (x&127)+len(pixels)+nv>128:break
                pixels+=nb[4:];j+=1
            v=len(pixels);body=struct.pack('<HH',x,y)+pixels
        out+=HEADER.pack(t,k,i,v)+body
    return bytes(out)


def batch_coordinates(data, *, alpha=False):
    """Use existing bulk-coordinate records without changing their ABI."""
    rows=list(records(data));out=bytearray();j=0
    while j<len(rows):
        a,b,t,k,i,v=rows[j];start=j;j+=1
        if k in ((1,2,3) if alpha else (2,3)):
            while j<len(rows) and j-start<(LIMIT-7)//7 and rows[j][2:5]==(t,k,i+j-start):j+=1
        count=j-start
        if count>=3:
            body=b''.join(struct.pack('<B' if k==1 else '<H',r[5]) for r in rows[start:j])
            out+=HEADER.pack(t,19 if k==1 else k+15,i,count)+body+bytes(7*(count-1)-len(body))
        else:
            j=start+1;out+=data[a:b]
    return bytes(out)

def inline_delta_hints(data, initial, patterns):
    """Exact span hints, valid only while the previous raw tag is resident."""
    tags=list(initial);out=bytearray()
    for a,b,t,k,i,v in records(data):
        body=data[a+7:b]
        if k==4:
            old=tags[i];before=patterns[old*64:old*64+64];after=body[4:]
            assert len(before)==len(after)==64
            changed=[j for j in range(64) if before[j]!=after[j]]
            start=changed[0] if changed else 0
            size=changed[-1]-start+1 if changed else 0
            body=struct.pack('<HBB',old,start,size)+after
            tags[i]=v
        out+=HEADER.pack(t,k,i,v)+body
    return bytes(out)


def row_dictionary(patterns):
    assert len(patterns)%64==0
    rows={};data=bytearray();index=bytearray()
    for at in range(0,len(patterns),8):
        row=patterns[at:at+8]
        if row not in rows:rows[row]=len(data);data+=row
        index+=struct.pack('<H',rows[row])
    assert len(data)<=65536
    index+=bytes((-len(index))%65536)
    return bytes(index+data),len(index)

def mode1_row_dictionary(glyphs):
    rows={};index=bytearray();data=bytearray()
    assert len(glyphs)//32<=21845,'Mode 1 row-index address exceeds its 24-bit multiply bound'
    for at in range(0,len(glyphs),32):
        ids=[]
        for y in range(8):
            row=glyphs[at+y*2:at+y*2+2]+glyphs[at+16+y*2:at+18+y*2]
            if row not in rows:rows[row]=len(data)//4;data+=row
            ids.append(rows[row])
        assert len(rows)<=4096,'Mode 1 needs more than 4096 distinct lossless rows'
        for a,b in zip(ids[::2],ids[1::2]):index+=(a|(b<<12)).to_bytes(3,'little')
    return bytes(index+data)

def packets(data,chart):
    groups=collections.defaultdict(list)
    for p,e,t,k,i,v in records(data):
        if k==255:break
        assert k in SUPPORTED,(t,k)
        blob=data[p:e]
        if k==4 and chart.get('sa1_row_dictionary'):
            blob=HEADER.pack(t,27,i,v)
        if k==0:
            x,y=chart['cell_coordinates'][i]
            blob=HEADER.pack(t,9,i,1)+struct.pack('<HHB',x,y,v)
        assert len(blob)+7<=LIMIT
        groups[t].append(blob)
    index=bytearray();payload=bytearray()
    def put(t,chunk):
        chunk+=HEADER.pack(65535,255,0,0)
        chunk=direct_spill_packet(chunk,chart)
        index.extend(struct.pack('<HHI',t,len(chunk),len(payload)));payload.extend(chunk)
    for t,events in sorted(groups.items()):
        compact=batch_coordinates(compact_map_rows(compact_tags(b''.join(events)+HEADER.pack(65535,255,0,0))),alpha=chart.get('stream_bulk_alpha_trial',False))
        compact=bulk_inline_patterns(compact,chart)
        compact=bulk_map_rows(compact,chart)
        events=[compact[a:b] for a,b,_,k,_,_ in records(compact) if k!=255]
        chunk=bytearray()
        for event in events:
            if len(chunk)+len(event)+14>LIMIT:put(t,chunk);chunk=bytearray()
            chunk+=event
        if chunk:put(t,chunk)
    return bytes(index),bytes(payload)

def mode1_merge_frames(source,chart,end):
    """Keep the exact final cache/map state when several chart times are due."""
    from animation_catchup import unpack_events,state
    if chart.get('mode1_snapshot'):
        events=unpack_events(source,chart);last={}
        for j,(_,k,i,v,p) in enumerate(events):last[(k,i) if k in (1,2,3,7) else (k,)]=j
        kept=[e for j,e in enumerate(events) if j in set(last.values())]
        assert state(events)==state(kept),'Snapshot catch-up changed native state'
        return b''.join(HEADER.pack(end,k,i,v)+p for _,k,i,v,p in kept)+HEADER.pack(65535,255,0,0)
    regular=bytearray();glyphs={};words={};palette=None
    for a,b,t,k,i,v in records(source+HEADER.pack(65535,255,0,0)):
        if k==255:break
        payload=source[a+7:b]
        if k==30:
            flags=struct.unpack_from('<H',payload)[0];at=2
            assert flags&~2==0
            if flags&2:palette=payload[at:at+96];at+=96
            glyphs.update(struct.iter_unpack('<HH',payload[at:]))
        elif k==31:
            at=0
            for _ in range(i):
                dest,size=struct.unpack_from('<HH',payload,at);at+=4
                for off in range(0,size,2):words[dest+off]=struct.unpack_from('<H',payload,at+off)[0]
                at+=size
            assert at==len(payload)
        else:regular+=source[a:b]
    events=unpack_events(bytes(regular),chart);last={}
    for j,(_,k,i,v,p) in enumerate(events):last[(k,i) if k in (1,2,3,4,7,9,27) else (k,)]=j
    retained=set(last.values());kept=[e for j,e in enumerate(events) if j in retained]
    if state(events)!=state(kept):kept=events
    out=bytearray(b''.join(HEADER.pack(end,k,i,v)+p for _,k,i,v,p in kept))
    if glyphs or palette is not None:
        body=struct.pack('<H',2 if palette is not None else 0)+(palette or b'')
        body+=b''.join(struct.pack('<HH',slot,glyph) for slot,glyph in sorted(glyphs.items()))
        out+=HEADER.pack(end,30,len(glyphs),len(body))+body
    spans=[]
    for addr,value in sorted(words.items()):
        if spans and addr==spans[-1][0]+len(spans[-1][1]) and addr//64==spans[-1][0]//64:
            spans[-1][1].extend(struct.pack('<H',value))
        else:spans.append((addr,bytearray(struct.pack('<H',value))))
    if spans:
        body=b''.join(struct.pack('<HH',addr,len(values))+values for addr,values in spans)
        out+=HEADER.pack(end,31,len(spans),len(body))+body
    return bytes(out)+HEADER.pack(65535,255,0,0)


def indexed_packets(data,chart):
    """Offer exact final-state deltas when multiple timestamps are overdue.

    Normal playback still has every authored frame. These alternatives remove
    overwritten writes only, never a visible intermediate presentation.
    """
    from animation_catchup import unpack_events,state
    index,payload=packets(data,chart)
    counts=tuple(chart.get('stream_merge_counts',(2,4,8)))
    assert len(counts)==3 and tuple(sorted(set(counts)))==counts and 1<counts[0] and counts[-1]<=15
    tagged=counts!=(2,4,8)
    assert not tagged or not chart.get('mode1_tracks'), 'Variable catchup counts are currently Mode 7 only'
    entries=list(struct.iter_unpack('<HHI',index));out=bytearray(payload);table=bytearray()
    tags=list(chart.get('pattern_initial',[0]*256))
    assert len(tags)==256
    for i,entry in enumerate(entries):
        table+=struct.pack('<HHI',*entry)
        for count in counts:
            if chart.get('mode1_projected') and not chart.get('mode1_snapshot'):
                # Inline screen-cache writes stay in their canonical order.
                # The decoder can consume multiple timestamps when running
                # faster, without substituting a reduced-frequency stream.
                table+=bytes(8);continue
            if i+count>len(entries):table+=bytes(8);continue
            span=entries[i:i+count]
            source=b''.join(payload[o:o+n-7] for t,n,o in span)
            end=span[-1][0]
            if chart.get('mode1_tracks'):
                blob=mode1_merge_frames(source,chart,end)
            else:
                events=unpack_events(source,chart);last={}
                for j,(_,k,idx,v,p) in enumerate(events):
                    last[(k,idx) if k in (1,2,3,4,7,9,27) else (k,)]=j
                retained=set(last.values())
                kept=[e for j,e in enumerate(events) if j in retained]
                if state(events)!=state(kept):table+=bytes(8);continue
                blob=b''.join(HEADER.pack(end,k,idx,v)+p for _,k,idx,v,p in kept)
                from animation_map_batch import batch
                blob,_=batch(compact_tags(blob+HEADER.pack(65535,255,0,0)),chart)
                blob=batch_coordinates(compact_map_rows(blob),alpha=chart.get('stream_bulk_alpha_trial',False))
                blob=bulk_inline_patterns(blob,chart)
                blob=bulk_map_rows(blob,chart)
            if len(blob)>=len(source):table+=bytes(8);continue
            chunks=[];chunk=bytearray()
            for a,b,t,k,idx,v in records(blob):
                if k==255:break
                if len(chunk)+b-a+14>LIMIT:
                    chunks.append(bytes(chunk)+HEADER.pack(65535,255,0,0));chunk=bytearray()
                chunk+=blob[a:b]
            chunks.append(bytes(chunk)+HEADER.pack(65535,255,0,0))
            chunks=[direct_spill_packet(c,chart) for c in chunks]
            sizes=[len(c)|(0x8000 if j+1<len(chunks) else 0) for j,c in enumerate(chunks)]
            table+=struct.pack('<HHI',end,sizes[0],len(out))
            out+=chunks[0]
            for size,chunk in zip(sizes[1:],chunks[1:]):out+=struct.pack('<H',size)+chunk
        table+=struct.pack('<256H',*tags)
        t,n,o=entry
        chunk=payload[o:o+n]
        for a,b,_,kind,slot,tag in records(chunk):
            if kind in (4,27):tags[slot]=tag
            elif kind==34:
                for at in range(slot):
                    logical,raw=struct.unpack_from('<HH',chunk,a+7+at*8);tags[logical]=raw
            elif kind==25:
                for at in range(a+7,b,4):
                    logical,raw=struct.unpack_from('<HH',chunk,at);tags[logical]=raw
    # The terminal entry supplies the final state if a seed occurs after
    # the last animation event. It is never an executable packet.
    table+=bytes(32)+struct.pack('<256H',*tags)
    # Keep only the eight-byte primary seek index in cartridge ROM. The
    # optional alternatives are read in one 32-byte MSU transfer per job.
    primary=bytearray()
    for i,(t,n,o) in enumerate(entries):
        primary+=struct.pack('<HHI',t,n,i*544)
    primary+=struct.pack('<HHI',65535,0,len(entries)*544)
    for i in range(len(entries)):
        for j in range(4):
            at=i*544+j*8
            t,n,o=struct.unpack_from('<HHI',table,at)
            if n:
                offset=o+len(table)
                assert offset<0x10000000, 'Stream-relative offset exceeds descriptor range'
                if tagged:offset|=((1,)+counts)[j]<<28
                struct.pack_into('<I',table,at+4,offset)
    return bytes(primary),bytes(table+out)

def mode1_seeds(index,data):
    entries=list(struct.iter_unpack('<HHI',index))[:-1]
    count=entries[-1][0]//64+2
    result=bytearray(count*4);cache=[0]*1024;palette=bytes(96);tilemap=bytearray(4096);cursor=0;symbols=b''
    for seed in range(count):
        while cursor<len(entries) and entries[cursor][0]<seed*64:
            _,_,choice=entries[cursor];_,size,offset=struct.unpack_from('<HHI',data,choice)
            packet=data[offset:offset+size]
            for a,b,t,k,i,v in records(packet):
                at=a+7
                if k==30:
                    flags=struct.unpack_from('<H',packet,at)[0];at+=2
                    assert flags&~2==0
                    if flags&2:palette=packet[at:at+96];at+=96
                    for slot,glyph in struct.iter_unpack('<HH',packet[at:b]):cache[slot]=glyph
                elif k==28:symbols=packet[at:b]
                elif k==31:
                    for _ in range(i):
                        dest,length=struct.unpack_from('<HH',packet,at);at+=4
                        tilemap[dest:dest+length]=packet[at:at+length];at+=length
            cursor+=1
        struct.pack_into('<I',result,seed*4,len(result))
        result+=struct.pack('<H',cursor)+palette+tilemap+struct.pack('<1024H',*cache)+struct.pack('<H',len(symbols))+symbols
    return bytes(result)


def prepare(folder,level,*,inline_patterns=False):
    folder=Path(folder);path=folder/f'level{level}.json';c=json.loads(path.read_text())
    if c.get('sa1_stream_format') in (3,4,5,6,7,8,9,10,11,13,14,15,16):
        # Engine rebuilds may already have bulk-packed the canonical fallback
        # stream. Its immutable SA-1 packets remain valid; do not compile that
        # different format a second time.
        for name in ('stream_index','stream_data','resident_stream'):
            assert (folder/f'{name}{level}.bin').is_file(), 'Missing SA-1 stream asset; regenerate from canonical chart assets'
        assert (folder/f'stream_index{level}.bin').stat().st_size==c['stream_packets']*8
        return
    assert not c.get('sa1_stream_format'),'Older stream format: regenerate this chart from canonical assets first'
    assert not c.get('catchup_format') and not c.get('native_stream_format')
    assert not c.get('bitmap_prefetch_versions'),'Streaming shares the bitmap-prefetch work memory'
    assert c.get('motion_step')==1,'Streaming expects full per-frame motion assets'
    # Inline packets carry pixels and a 16-bit identity, not an entry in the
    # resident row-dictionary lookup arena. FE00..FEFF remain checkpoint tags.
    assert c['pattern_count']<=(0xFE00 if inline_patterns else 32768),'Raw pattern lookup exceeds SA-1 work memory'
    dictionary,row_offset=(bytes(2),0) if inline_patterns else row_dictionary((folder/f'patterns{level}.bin').read_bytes())
    (folder/f'resident_stream{level}.bin').write_bytes(dictionary)
    c.update(sa1_row_dictionary=int(not inline_patterns),sa1_inline_patterns=inline_patterns,sa1_delta_patterns=inline_patterns,stream_row_offset=row_offset)
    if inline_patterns and level in (67,69,72,74):c['stream_merge_counts']=[2,3,5]
    animation=(folder/f'animation{level}.bin').read_bytes()
    if inline_patterns:
        from animation_catchup import unpack_events
        animation=b''.join(HEADER.pack(t,k,i,v)+p for t,k,i,v,p in unpack_events(animation,c))+HEADER.pack(65535,255,0,0)
    if inline_patterns:
        animation=inline_delta_hints(animation,c['pattern_initial'],(folder/f'patterns{level}.bin').read_bytes())
        if level in (67,69,72,74) and c.get('stream_spill_trial'):
            from stream_spill import prepare_spills
            animation=prepare_spills(folder,level,c,animation)
            c['stream_obj_spill']=True
        if c.get('projected_spill_frames'):
            from projected_spill import append_packets
            animation=append_packets(c,animation)
            c['stream_obj_spill']=True
    jobs=folder/f'mode1_jobs{level}.bin'
    if jobs.exists():
        # Keep the established full-detail renderer for accelerated playback.
        # Both streams originate from the same canonical per-frame chart.
        fallback=dict(c);fallback.pop('mode1_tracks',None)
        fallback_index,fallback_data=indexed_packets(animation,fallback)
        (folder/f'stream_index_fallback{level}.bin').write_bytes(fallback_index)
        (folder/f'stream_data_fallback{level}.bin').write_bytes(fallback_data)
        (folder/f'resident_stream_fallback{level}.bin').write_bytes((folder/f'resident_stream{level}.bin').read_bytes())
        c['fallback_stream_packets']=len(fallback_index)//8
        c['fallback_stream_row_offset']=c['stream_row_offset']
        c['mode1_tracks']=1
        from mode1_tracks import symbol_candidates,icon_descriptors
        candidates=symbol_candidates(c,animation)
        (folder/f'mode1_icons{level}.bin').write_bytes(icon_descriptors(c))
        animation=bytearray(b''.join(animation[a:b] for a,b,t,k,i,v in records(animation) if k not in (0,4,9,25,27,14,28,29,255)))
        animation+=candidates
        glyphs=(folder/f'mode1_glyphs{level}.bin').read_bytes()
        (folder/f'resident_stream{level}.bin').write_bytes(mode1_row_dictionary(glyphs))
        c['mode1_glyph_count']=len(glyphs)//32
        c['stream_row_offset']=0
        blob=jobs.read_bytes();at=0
        ids={glyphs[i:i+32]:i//32 for i in range(0,len(glyphs),32)}
        while at<len(blob):
            t,count,size=struct.unpack_from('<HHH',blob,at);at+=6
            payload=blob[at:at+size];at+=size
            flags=struct.unpack_from('<H',payload)[0];head=2+512*bool(flags&1)+96*bool(flags&2)
            compact=struct.pack('<H',flags&2)+(payload[2+512*bool(flags&1):head] if flags&2 else b'')+b''.join(payload[j:j+2]+struct.pack('<H',ids[payload[j+2:j+34]]) for j in range(head,len(payload),34))
            animation+=HEADER.pack(t,30,count,len(compact))+compact
        blob=(folder/f'mode1_maps{level}.bin').read_bytes();at=0
        while at<len(blob):
            t,count,size=struct.unpack_from('<HHH',blob,at);at+=6
            animation+=HEADER.pack(t,31,count,size)+blob[at:at+size];at+=size
        animation+=HEADER.pack(65535,255,0,0)
    index,data=indexed_packets(animation,c)
    # The runtime stores two-byte timestamps, not these eight-byte build
    # records. Validate the actual cartridge table before writing anything.
    rom_index(index)
    if c.get('mode1_tracks'):(folder/f'mode1_seeds{level}.bin').write_bytes(mode1_seeds(index,data))
    (folder/f'stream_index{level}.bin').write_bytes(index)
    (folder/f'stream_data{level}.bin').write_bytes(data)
    c.update(sa1_stream_format=10 if c.get('stream_bulk_rows_trial') else 9 if c.get('stream_spill_delta_trial') else 8 if c.get('stream_direct_patterns_trial') else 5 if c.get('stream_direct_spill_trial') else 4 if c.get('stream_merge_counts') else 3,catchup_disabled=True,stream_packets=len(index)//8)
    path.write_text(json.dumps(c,indent=2))
    print(c['code'],len(index)//8,'SA-1 packets',len(data),'bytes',flush=True)
