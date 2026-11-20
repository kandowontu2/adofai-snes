"""Budget optional scenery while preserving every gameplay pose and event.

Run against a staged, seed-compacted catalog. Required imagery (including
T3's fog/copies, replacement floors and hazards) remains in the OFF cache.
The plan only selects whether an additional decorative ON cache fits MSU-1.
"""
import argparse,concurrent.futures,hashlib,json,struct,sys
from pathlib import Path
from animation_bulk import records
from benchmark_snapshot_components import packets
from native_packet_codec import compact_prefix


def native_size(task):
    base,n,suffix=task
    index=(base/f'stream_index{suffix}{n}.bin').read_bytes()
    stream=(base/f'stream_data{suffix}{n}.bin').read_bytes()
    seeds=(base/f'mode1_seeds{suffix}{n}.bin').read_bytes()
    count=len(index)//8;removed=count*512;directory=count*544
    pointers=set();visited=set()
    for row in range(count):
        for choice in range(4):
            _,size,at=struct.unpack_from('<HHI',stream,row*544+choice*8);at&=0xfffffff
            while size:
                length=size&32767
                if at not in visited:
                    visited.add(at)
                    pointers.update(struct.unpack_from('<I',stream,at+a+7)[0]
                        for a,b,t,k,i,v in records(stream[at:at+length]) if k==42)
                if not size&32768:break
                at+=length;size=struct.unpack_from('<H',stream,at)[0];at+=2
    prefix=bytearray(b''.join(stream[i*544:i*544+32] for i in range(count)))
    prefix+=stream[directory:min(pointers)]
    for row in range(count):
        for choice in range(4):
            at=row*32+choice*8;_,size,offset=struct.unpack_from('<HHI',prefix,at)
            if size:struct.pack_into('<I',prefix,at+4,(offset&0xf0000000)|((offset&0xfffffff)-removed))
    encoded,_,_=compact_prefix(prefix,count)
    signature=hashlib.sha256(index+hashlib.sha256(stream).digest()+hashlib.sha256(seeds).digest()).hexdigest()
    result=dict(id=n,suffix=suffix,bytes=len(encoded)+len(seeds),signature=signature)
    print('NATIVE',n,suffix or 'on',result['bytes'],flush=True)
    return result


def variant_packets(base,n,suffix):
    # The common packet iterator takes a conventional stream filename.
    # OFF verifier folders retain exactly the same independent pose bytes.
    if suffix:
        chart=json.loads((base/f'level{n}.json').read_text())
        return packets(base/chart['vfx_off']['verification_source'],n)
    return packets(base,n)


def plan(base,out,max_bytes,workers,priority):
    ids=json.loads((base/'pack.json').read_text())['levels']
    optional={n for n in ids if (base/f'stream_index_vfx_off{n}.bin').exists()}
    tasks=[(base,n,suffix) for n in ids for suffix in (['','_vfx_off'] if n in optional else [''])]
    cache=out.with_name(out.stem+'-native.json')
    codec_sha=hashlib.sha256((Path(__file__).parent/'native_packet_codec.py').read_bytes()).hexdigest()
    if cache.exists():
        saved=json.loads(cache.read_text());assert saved['levels']==ids and saved.get('codec_sha256')==codec_sha,'Native codec changed; use a fresh storage report'
        source_stamp={str(base/f'stream_data{s}{n}.bin'):(base/f'stream_data{s}{n}.bin').stat().st_mtime_ns for _,n,s in tasks}
        assert saved['source_stamp']==source_stamp,'Native storage cache is stale'
        sizes=saved['sizes']
    else:
        with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:sizes=list(pool.map(native_size,tasks))
        source_stamp={str(base/f'stream_data{s}{n}.bin'):(base/f'stream_data{s}{n}.bin').stat().st_mtime_ns for _,n,s in tasks}
        cache.write_text(json.dumps(dict(levels=ids,sizes=sizes,source_stamp=source_stamp,codec_sha256=codec_sha),indent=2))
    costs={(r['id'],r['suffix']):r for r in sizes}
    seen=set();pool_bytes=0;native_bytes=0;signatures=set()
    for n in ids:
        suffix='_vfx_off' if n in optional else ''
        row=costs[n,suffix]
        if row['signature'] not in signatures:signatures.add(row['signature']);native_bytes+=row['bytes']
        for packet in variant_packets(base,n,suffix):
            key=hashlib.sha256(packet).digest()
            if key not in seen:seen.add(key);pool_bytes+=len(packet)
        print('GAMEPLAY POOL',n,pool_bytes,flush=True)
    fixed=32+sum((base/f'level{n}.brr').stat().st_size+(base/f'animation{n}.bin').stat().st_size+
        (base/f'chart{n}.bin').stat().st_size+len(json.loads((base/f'level{n}.json').read_text())['checkpoints'])*4 for n in ids)
    fixed+=sum(p.stat().st_size for n in ids for p in base.glob(f'animation{n}-checkpoint-*.bin'))
    total=fixed+native_bytes+pool_bytes;assert total<=max_bytes,('Required gameplay alone exceeds the budget',total,max_bytes)
    candidates=[]
    for n in optional:
        extra={}
        for packet in variant_packets(base,n,''):
            key=hashlib.sha256(packet).digest()
            if key not in seen:extra[key]=len(packet)
        native=costs[n,''];native_extra=0 if native['signature'] in signatures else native['bytes']
        candidates.append(dict(id=n,pool_bytes=sum(extra.values()),native_bytes=native_extra,
                               extra_bytes=sum(extra.values())+native_extra))
    selected=[];omitted=[]
    # Small scenes first keep the most complete optional scenes. Explicit
    # priority is available for a particular release's requested showcase.
    order={n:i for i,n in enumerate(priority)}
    for row in sorted(candidates,key=lambda r:(order.get(r['id'],len(order)),r['extra_bytes'],r['id'])):
        if total+row['extra_bytes']<=max_bytes:
            selected.append(row);total+=row['extra_bytes']
        else:omitted.append(row)
    report=dict(levels=ids,passed=True,max_bytes=max_bytes,estimated_upper_bound=total,
        required_pool_bytes=pool_bytes,required_native_bytes=native_bytes,fixed_bytes=fixed,
        source_sha256={str(n):hashlib.sha256((base/'source-imports'/f'level{n}.json').read_bytes()).hexdigest() for n in ids},
        selected_scenery=selected,omitted_scenery=omitted,
        note='Optional decoration-only ON caches; every gameplay frame, tile, required object and event is retained.')
    out.write_text(json.dumps(report,indent=2))
    print('STORAGE PLAN',len(ids),'charts;',len(selected),'optional scenes retained;',len(omitted),'omitted;',total,'bytes upper bound',flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--max-bytes',type=int,default=0xfc000000)
    p.add_argument('--workers',type=int,default=4);p.add_argument('--priority',type=int,nargs='*',default=[])
    a=p.parse_args();a.out.parent.mkdir(parents=True,exist_ok=True)
    plan(a.source.resolve(),a.out,a.max_bytes,a.workers,a.priority)
