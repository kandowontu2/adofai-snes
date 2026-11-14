"""Exact final-state shortcuts for dense animation intervals already overdue.

The normal branch is byte-for-byte the original stream. Checkpoints enter
that branch at their original event, never into a partly applied shortcut.
"""
import json
import os
import struct
from pathlib import Path
from animation_bulk import HEADER, records, semantic_digest, batch

def unpack_events(data, chart):
    events=[]
    def put(t,k,i,v,payload=b''):events.append((t,k,i,v,payload))
    terminated=data+HEADER.pack(65535,255,0,0)
    for pos,end,t,k,i,v in records(terminated):
        if k==255:break
        payload=data[pos+7:end]
        if k in (24,26,32,33):continue
        if k==36:
            at=0
            for _ in range(i):
                cell,count,x,y=struct.unpack_from('<HHHH',payload,at);at+=8
                for j,value in enumerate(payload[at:at+count]):
                    cx,cy=chart['cell_coordinates'][cell+j]
                    put(t,9,cell+j,1,struct.pack('<HHB',cx,cy,value))
                at+=count
            assert at==len(payload)
        elif k==34:
            for n in range(i):
                slot,tag=struct.unpack_from('<HH',payload,n*8)
                put(t,4,slot,tag,payload[n*8+4:n*8+8]+payload[i*8+n*64:i*8+(n+1)*64])
        elif k==29:
            for j in range(i):
                cell,_,value=struct.unpack_from('<HHB',payload,5*j)
                x,y=chart['cell_coordinates'][cell]
                put(t,9,cell,1,struct.pack('<HHB',x,y,value))
        elif k==25:
            for j in range(i):
                slot,tag=struct.unpack_from('<HH',payload,4*j)
                put(t,27,slot,tag)
        elif k==20:
            for j in range(v):
                at=j*68;slot,tag=struct.unpack_from('<HH',payload,at)
                hints=payload[68*v+4*j:68*v+4*j+4]
                put(t,4,slot,tag,hints+payload[at+4:at+68])
        elif k in (17,18,19):
            size=1 if k==19 else 2
            for j in range(v):put(t,{17:2,18:3,19:1}[k],i+j,int.from_bytes(payload[j*size:(j+1)*size],'little'))
        elif k==8:
            for j in range(v):
                slot,color=struct.unpack_from('<BH',payload,j*3);put(t,7,slot,color)
        elif k in (0,5,9):
            if k==0:values=[v]
            elif k==9:values=payload[4:]
            else:values=payload
            for j,value in enumerate(values):
                x,y=chart['cell_coordinates'][i+j]
                put(t,9,i+j,1,struct.pack('<HHB',x,y,value))
        else:
            assert k in (1,2,3,4,6,7,10,11,12,13,14,15,16,22,23,27,28,35,41,42,43,44),k
            put(t,k,i,v,payload)
    return events

def state(events):
    """Include every observable field, and the aliased hardware map writes."""
    result={}
    for _,k,i,v,p in events:
        if k==9:
            x,y,value=struct.unpack('<HHB',p)
            result[('cell',i)]=value;result[('map',x&127,y&127)]=value
        elif k==4:result[(k,i)]=(v,p[4:])
        elif k in (1,2,3,7,27):result[(k,i)]=v
        elif k==11:
            result[('sampling',)]=(i,v);result[('projection',)]=(i,v)
        elif k==15:result[('projection',)]=(i,v)
        else:result[(k,)]=(i,v,p)
    return result

def shortcut(data,chart,end_time):
    events=unpack_events(data,chart);last={}
    for n,(_,k,i,v,p) in enumerate(events):
        key=(k,i) if k in (1,2,3,4,7,9,27) else (k,)
        last[key]=n
    retained=set(last.values())
    kept=[e for n,e in enumerate(events) if n in retained]
    assert state(events)==state(kept),'Catch-up changes final authored state'
    if len(kept)>=len(events):return None
    # Keep last-write order: wrapped cells and camera projection can alias.
    blob=bytearray();a=0
    while a<len(kept):
        _,k,i,v,p=kept[a];b=a+1
        if k==9:
            x,y,value=struct.unpack('<HHB',p)
            while b<len(kept) and b-a<128:
                _,nk,ni,nv,np=kept[b]
                if nk!=9 or ni!=i+b-a or struct.unpack('<HH',np[:4])!=(x+b-a,y):break
                b+=1
            if b-a>=3:
                blob+=HEADER.pack(end_time,9,i,b-a)+p[:4]+bytes(e[4][4] for e in kept[a:b])
            else:
                b=a+1;blob+=HEADER.pack(end_time,0,i,value)
        else:blob+=HEADER.pack(end_time,k,i,v)+p
        a=b
    encoded,_=batch(blob+HEADER.pack(65535,255,0,0))
    from animation_map_batch import batch as batch_map
    encoded,_=batch_map(encoded,chart)
    return encoded[:-7]

def compile_stream(data,chart):
    rows=list(records(data));out=bytearray();mapping={};windows=0;saved=0;j=0
    while j<len(rows)-1:
        ranges=chart.get('catchup_ranges')
        if ranges is not None and not any(a<=rows[j][2]<b for a,b in ranges):
            mapping[rows[j][0]]=len(out)
            out+=data[rows[j][0]:rows[j][1]]
            j+=1
            continue
        if 1440<=rows[j][2]<1560 or chart.get('id')==60 or chart.get('catchup_every_frame'):
            # Offer a four-frame shortcut at EVERY timestamp of the dense
            # zoom transition, so entering a normal branch cannot trap a
            # late renderer inside an entire fixed-size interval.
            groups=[]
            while j<len(rows)-1 and (chart.get('id')==60 or chart.get('catchup_every_frame') or rows[j][2]<1560) and (ranges is None or any(a<=rows[j][2]<b for a,b in ranges)):
                first=j;t=rows[j][2]
                while j<len(rows)-1 and rows[j][2]==t:j+=1
                groups.append(rows[first:j])
            fragments=[None]*len(groups);prefixes=[0]*len(groups)
            for i in range(len(groups)-1,-1,-1):
                group=groups[i];a=group[0][0];b=group[-1][1];normal=data[a:b]
                fragment=normal
                widths=(2,4,8) if chart.get('id')==60 and 7000<=group[0][2]<=7500 else tuple(chart.get('catchup_widths',[4]))
                for width in widths:
                    end=i+1
                    while end<len(groups) and groups[end][0][2]<group[0][2]+width:end+=1
                    source=data[a:groups[end-1][-1][1]]
                    fast=shortcut(source,chart,groups[end-1][-1][2])
                    skip=len(fragment)+sum(len(fragments[k]) for k in range(i+1,end))
                    if fast is not None and len(fast)+7<=65535 and skip<=65535:
                        prefix=HEADER.pack(group[0][2],21,groups[end-1][-1][2],len(fast))+fast+HEADER.pack(groups[end-1][-1][2],22,skip,0)
                        fragment=prefix+fragment
                        windows+=1;saved+=len(source)-len(fast)
                prefixes[i]=len(fragment)-len(normal);fragments[i]=fragment
            for group,prefix,fragment in zip(groups,prefixes,fragments):
                for r in group:mapping[r[0]]=len(out)+prefix+r[0]-group[0][0]
                out+=fragment
            continue
        first=j;bucket=rows[j][2]//4
        while j<len(rows)-1 and rows[j][2]//4==bucket:j+=1
        a=rows[first][0];b=rows[j-1][1];normal=data[a:b]
        fast=shortcut(normal,chart,rows[j-1][2])
        if fast is not None and len(fast)+7<=65535 and len(normal)<=65535:
            out+=HEADER.pack(rows[first][2],21,rows[j-1][2],len(fast))
            out+=fast+HEADER.pack(rows[j-1][2],22,len(normal),0)
            windows+=1;saved+=len(normal)-len(fast)
        normal_start=len(out)
        for r in rows[first:j]:mapping[r[0]]=normal_start+r[0]-a
        out+=normal
    mapping[rows[-1][0]]=len(out)
    out+=data[rows[-1][0]:]
    assert semantic_digest(data)==semantic_digest(out)
    return bytes(out),mapping,dict(windows=windows,bytes=len(out),original_bytes=len(data),shortcut_bytes_saved=saved)

def patch_level(out,level):
    out=Path(out);pack=json.loads((out/'pack.json').read_text())
    if level not in pack['levels']:return
    chart_path=out/f'level{level}.json';chart=json.loads(chart_path.read_text())
    if chart.get('catchup_disabled'):return
    # Expanded hold shortcuts belong to the streamed master, not an 8 MiB ROM.
    if level in (66,71) and 'ROM_DATA_BUILD' in (out/'addresses.inc').read_text():return
    if level in (66,71):
        chart['catchup_every_frame']=True
        chart['catchup_widths']=[4,8,16]
        notes=chart['notes']
        chart['catchup_ranges']=[(max(0,n['frame']-2),notes[i+1]['frame']+2) for i,n in enumerate(notes[:-1]) if n.get('hold_length',-1)>=0]
    if chart.get('catchup_format')==5:return
    standalone='ROM_DATA_BUILD' in (out/'addresses.inc').read_text()
    target=out/('sa1_payload.bin' if standalone else 'adofai.msu')
    image=bytearray(target.read_bytes());bias=0x10000 if standalone else 0
    descriptors=bytearray((out/'msu_descriptors.bin').read_bytes());at=pack['levels'].index(level)*24
    old,table=struct.unpack_from('<II',descriptors,at+8)
    stored_length=chart['animation_bytes']
    original=bytes(image[old-bias:old-bias+stored_length])
    if not standalone and old+len(original)==len(image):image=image[:old]
    prior_mapping=None
    if chart.get('catchup_format'):
        restored=bytearray();prior_mapping={}
        for p,e,t,k,i,v in records(original):
            if k==21:continue
            prior_mapping[p]=len(restored);restored+=original[p:e]
        original=bytes(restored)
    stream,mapping,report=compile_stream(original,chart)
    if standalone:
        destination=old
        locations=json.loads((out/'placements.json').read_text())
        delta=len(stream)-stored_length;cut=old+stored_length
        assert delta<=0 or not any(image[len(image)-delta:])
        image[old-bias:cut-bias]=stream
        if delta>0:del image[len(image)-delta:]
        elif delta<0:image+=bytes(-delta)
        offset=lambda a:a-0xC00000 if a>=0xC00000 else a
        for name,address in list(locations.items()):
            n=offset(address)
            if n>=cut:
                assert name.startswith(f'romdata{level}_'),name
                n+=delta;locations[name]=n+0xC00000 if n<0x400000 else n
        for field in (0,4,12):
            value=struct.unpack_from('<I',descriptors,at+field)[0]
            if value>=cut:struct.pack_into('<I',descriptors,at+field,value+delta)
        if table>=cut:table+=delta
        for c in range(len(chart['checkpoints'])):
            pointer=struct.unpack_from('<I',image,table-bias+c*4)[0]
            if pointer>=cut:struct.pack_into('<I',image,table-bias+c*4,pointer+delta)
    else:
        destination=len(image);image+=stream
    struct.pack_into('<I',descriptors,at+8,destination)
    for c in range(len(chart['checkpoints'])):
        snapshot=struct.unpack_from('<I',image,table-bias+c*4)[0]-bias
        cursor=struct.unpack_from('<I',image,snapshot+4)[0]
        if prior_mapping is not None:cursor=prior_mapping[cursor]
        struct.pack_into('<I',image,snapshot+4,mapping[cursor])
        loose=out/f'animation{level}-checkpoint-{c}.bin'
        if loose.exists():
            blob=bytearray(loose.read_bytes());struct.pack_into('<I',blob,4,mapping[cursor]);loose.write_bytes(blob)
    chart['animation_bytes']=len(stream);chart['catchup_format']=5
    temp=target.with_suffix(target.suffix+'.catchup-tmp');temp.write_bytes(image);os.replace(temp,target)
    (out/'msu_descriptors.bin').write_bytes(descriptors)
    (out/f'animation{level}.bin').write_bytes(stream)
    if standalone:(out/'placements.json').write_text(json.dumps(locations,indent=2))
    chart_path.write_text(json.dumps(chart,indent=2))
    (out/f'animation-catchup-{level}.json').write_text(json.dumps(dict(passed=True,**report),indent=2))


def patch_pack(out):
    for level in (23,66,71):
        patch_level(out,level)
