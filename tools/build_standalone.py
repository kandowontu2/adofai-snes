"""Build ordinary 8-MiB cartridges from the current compiled master charts.

The native renderer and animation format are shared. ROM bank reads replace
the MSU data port, and the SPC plays embedded 12-kHz BRR at every speed.
No .msu or .pcm file is created or required.
"""
import argparse,copy,hashlib,json,shutil,struct,subprocess,sys
from pathlib import Path
import campaign_assets as assets
from official_catalog import PACKS

ROOT=Path(__file__).resolve().parents[1]
MASTER=ROOT/'build/packs/master'
VARIANT=ROOT/'build/packs/standalone-cache'
# All cartridges use the same full silhouettes and authored movement as
# the master. The versioned PPU cache also protects BRR playback builds.
DENSE_CHARTS=set()
SA1=False
ADAPTIVE_AUDIO=False
FAST_CACHE=ROOT/'build/fast-audio-cache'
FAST_MUSIC={}
SOURCE_OVERRIDES={}


def source_for(n):
    return SOURCE_OVERRIDES.get(n,VARIANT if n in DENSE_CHARTS else MASTER)


def prepare_resident_variant(key,levels):
    # T3 EX's scene graphics exceed 8 MiB when every repeated bitmap is
    # inlined. Use the existing lossless paged dictionary for this cartridge.
    if not SA1 or levels!=[73]:return
    original=source_for(73)
    chart=json.loads((original/'level73.json').read_text())
    if chart.get('resident_pattern_format'):return
    import re
    target=ROOT/'build/packs'/key/'source';target.mkdir(parents=True,exist_ok=True)
    for p in original.iterdir():
        if p.is_file() and re.search(r'(?:level|animation|chart|track_chr|track_map|timeline|patterns|checkpoints|visibility_index|music)73(?:[-.]|$)',p.name):
            shutil.copyfile(p,target/p.name)
    from resident_patterns import prepare
    prepare(target,73,dense_prefetch=True)
    SOURCE_OVERRIDES[73]=target


def prepare_variants(levels):
    """Use stable positions where BRR competes with dense tile animation."""
    needed=sorted(DENSE_CHARTS.intersection(levels))
    if not needed:return
    VARIANT.mkdir(parents=True,exist_ok=True)
    for n in needed:
        for name in (f'level{n}.brr',f'level{n}-audio.json'):
            shutil.copyfile(MASTER/name,VARIANT/name)
        subprocess.run([sys.executable,str(ROOT/'tools/campaign_assets.py'),'--pack','master','--out',str(VARIANT),
                        '--levels',str(n),'--chart-cache-only','--preview-tiles','16','--past-tiles','0','--fixed-tile-positions','--compact-graphics'],check=True,cwd=ROOT)


def file_offset(cpu):
    if cpu>=0xC00000:return cpu-0xC00000
    if 0x400000<=cpu<(0x800000 if SA1 else 0x7E0000):return cpu
    raise ValueError(f'Nonlinear ROM data placement: {cpu:06x}')


def payload(charts,ui):
    blobs=dict(ui)
    if any(c.get('neo_cosmos') for c in charts):
        from neo_runtime_assets import binary_tables
        blobs['neo_tables']=binary_tables(MASTER,[c['id'] for c in charts])[0]
    for c in charts:
        n=c['id'];source=source_for(n)
        for prefix in ('chart','track_chr','track_map'):
            blobs[f'{prefix}{n}']=(source/f'{prefix}{n}.bin').read_bytes()
        if c.get('resident_pattern_format'):
            for prefix in ('resident_raw','resident_future'):blobs[f'{prefix}{n}']=(source/f'{prefix}{n}.bin').read_bytes()
        if c.get('native_stream_format'):blobs[f'resident_animation{n}']=(source/f'resident_animation{n}.bin').read_bytes()
        blobs[f'music{n}']=bytes(2)
        blobs[f'timeline{n}']=bytes(2)
        blobs[f'checkpoints{n}']=bytes(max(2,14*len(c['checkpoints'])))
        blobs[f'romdata{n}_music']=(source/f'level{n}.brr').read_bytes()
        if ADAPTIVE_AUDIO:
            if n not in FAST_MUSIC:
                original_out=assets.OUT;FAST_CACHE.mkdir(exist_ok=True);assets.OUT=FAST_CACHE
                FAST_MUSIC[n]=assets.encode_music(copy.deepcopy(c),rate=8000,suffix='-fast')
                assets.OUT=original_out
            blobs[f'romdata{n}_fastmusic']=FAST_MUSIC[n]
            blobs[f'fastseeks{n}']=b''.join(struct.pack('<I',round(cp['block']*2/3)*9) for cp in c['checkpoints']) or bytes(4)
        blobs[f'romdata{n}_animation']=(source/f'animation{n}.bin').read_bytes()
        blobs[f'romdata{n}_timeline']=bytes(2)
        blobs[f'romdata{n}_table']=bytes(max(4,4*len(c['checkpoints'])))
        for i,_ in enumerate(c['checkpoints']):
            blobs[f'romdata{n}_cp{i}']=(source/f'animation{n}-checkpoint-{i}.bin').read_bytes()
    return blobs


def prepare(key,title,levels):
    out=ROOT/'build/packs'/key;out.mkdir(parents=True,exist_ok=True)
    assets.OUT=out
    charts=[copy.deepcopy(json.loads((source_for(n)/f'level{n}.json').read_text())) for n in levels]
    ui=assets.ui_assets(title,mode7=True)
    blobs=payload(charts,ui)
    assets.pack_payload(blobs,charts,msu=True,rom_data=True,sa1=SA1)
    locations=json.loads((out/'placements.json').read_text())
    image=bytearray(bytes(0x10000)+(out/'sa1_payload.bin').read_bytes()) if SA1 else bytearray((out/'payload0.bin').read_bytes()+bytes(0x8000)+(out/'payload1.bin').read_bytes())
    descriptors=bytearray()
    for c in charts:
        n=c['id'];where=lambda suffix:file_offset(locations[f'romdata{n}_{suffix}'])
        snapshots=[where(f'cp{i}') for i,_ in enumerate(c['checkpoints'])]
        table=b''.join(struct.pack('<I',p) for p in snapshots)
        image[where('table'):where('table')+len(table)]=table
        fast=where('fastmusic') if ADAPTIVE_AUDIO else 0
        seeks=locations[f'fastseeks{n}'] if ADAPTIVE_AUDIO else where('timeline')
        descriptors+=struct.pack('<IHHIIHHI',where('music'),fast&65535,fast>>16,where('animation'),where('table'),
                                 c['visibility_cells'],int(bool(c.get('pattern_versions'))),seeks)
        if ADAPTIVE_AUDIO:shutil.copyfile(FAST_CACHE/f'level{n}-fast.brr',out/f'level{n}-fast.brr')
        (out/f'level{n}.json').write_text(json.dumps(c,indent=2))
        # Verification reads original timelines and pattern dictionaries.
        for name in (f'chart{n}.bin',f'track_chr{n}.bin',f'track_map{n}.bin',f'timeline{n}.bin',f'patterns{n}.bin',f'level{n}.brr',f'animation{n}.bin'):
            shutil.copyfile(source_for(n)/name,out/name)
        for source in (source_for(n)/f'level{n}-audio.json',FAST_CACHE/f'level{n}-fast-audio.json'):
            if source.exists():shutil.copyfile(source,out/source.name)
    for name,blob in ui.items():(out/(name+'.bin')).write_bytes(blob)
    (out/'payload0.bin').write_bytes(image[:0x408000])
    (out/'payload1.bin').write_bytes(image[0x410000:])
    if SA1:(out/'sa1_payload.bin').write_bytes(image[0x10000:])
    (out/'msu_descriptors.bin').write_bytes(descriptors)
    (out/'pack.json').write_text(json.dumps(dict(code=key,title=title,levels=levels,standalone=True,fast_audio_rate=8000 if ADAPTIVE_AUDIO else None),indent=2))
    (out/'manifest.json').write_text(json.dumps(charts,indent=2))
    assets.common_tables(charts,adaptive_audio=ADAPTIVE_AUDIO)
    if ADAPTIVE_AUDIO:
        with (out/'addresses.inc').open('a') as f:f.write('FAST_AUDIO_BUILD = 1\n')
    return out


def build(key,title,levels):
    prepare_resident_variant(key,levels)
    out=prepare(key,title,levels)
    if SA1:
        from build_sa1 import compile_engine
        compile_engine(out)
    else:
        subprocess.run([sys.executable,str(ROOT/'build_campaign.py'),'--pack','master','--out',str(out),'--skip-assets'],check=True,cwd=ROOT)
    row=dict(key=key,title=title,levels=levels,file='adofai-'+key.replace('standalone-','')+'.sfc',
             rom_sha256=hashlib.sha256((out/'adofai.sfc').read_bytes()).hexdigest(),
             codes=[json.loads((out/f'level{n}.json').read_text())['code'] for n in levels])
    print(json.dumps(row),flush=True)
    return row


def main():
    global SA1,MASTER,ADAPTIVE_AUDIO
    ap=argparse.ArgumentParser();ap.add_argument('--levels',nargs='+',type=int)
    ap.add_argument('--key',default='standalone-sample');ap.add_argument('--title',default='STANDALONE WORLDS')
    ap.add_argument('--resume-catalog',type=Path);ap.add_argument('--adaptive-audio',action='store_true');ap.add_argument('--key-prefix');ap.add_argument('--catalog',type=Path);ap.add_argument('--individual',action='store_true');ap.add_argument('--sa1',action='store_true');ap.add_argument('--source',type=Path);args=ap.parse_args()
    SA1=args.sa1
    ADAPTIVE_AUDIO=args.adaptive_audio
    if args.source:MASTER=args.source.resolve()
    if args.levels:
        prepare_variants(args.levels)
        row=build(args.key,args.title,args.levels)
        catalog=ROOT/f'build/{"sa1-" if SA1 else ""}standalone-catalog.json'
        if catalog.exists():
            data=json.loads(catalog.read_text())
            if any(r['key']==row['key'] for r in data['roms']):
                data['roms']=[row if r['key']==row['key'] else r for r in data['roms']]
                catalog.write_text(json.dumps(data,indent=2))
        return
    from import_community import COMMUNITY
    community=[c['id'] for c in COMMUNITY if not c.get('requires_msu')]
    for c in COMMUNITY:
        if c.get('requires_msu'):print(f"{c['code']}: requires a separate MSU package; excluded from self-contained cartridges",flush=True)
    prepare_variants([*range(1,62),*community])
    groups={k:dict(v) for k,v in PACKS.items()}
    groups['tech']=dict(title='FEATURED TECH',levels=list(range(40,62)))
    if community:groups['community']=dict(title='COMMUNITY CHARTS',levels=community)
    if all((MASTER/f'level{n}.json').exists() for n in range(66,75)):
        groups['neo']=dict(title='NEO COSMOS',levels=list(range(66,75)))
    rows=json.loads(args.resume_catalog.read_text())['roms'] if args.resume_catalog else []
    for row in rows:
        assert hashlib.sha256((ROOT/'build/packs'/row['key']/'adofai.sfc').read_bytes()).hexdigest()==row['rom_sha256']
    completed={n for row in rows for n in row['levels']}
    for category,meta in groups.items():
        remaining=[n for n in meta['levels'] if n not in completed]
        part=1+max([int(row['key'].rsplit('-',1)[1]) for row in rows if f'-{category}-' in row['key']] or [0])
        while remaining:
            count=1 if args.individual else len(remaining)
            if ADAPTIVE_AUDIO and count>1:
                # Reject obviously oversized groups using on-disk byte counts
                # before regenerating UI, sound banks and address tables.
                def estimate(n):
                    source=source_for(n)
                    names=[f'chart{n}.bin',f'track_chr{n}.bin',f'track_map{n}.bin',f'level{n}.brr',f'animation{n}.bin',f'visibility_index{n}.bin',f'hitnotes{n}.bin',f'hitbank{n}.bin']
                    return sum((source/name).stat().st_size for name in names if (source/name).exists())+sum(p.stat().st_size for p in source.glob(f'animation{n}-checkpoint-*.bin'))+((FAST_CACHE/f'level{n}-fast.brr').stat().st_size if (FAST_CACHE/f'level{n}-fast.brr').exists() else (source/f'level{n}.brr').stat().st_size*2//3+32)
                sizes=[estimate(n) for n in remaining]
                while count>1 and sum(sizes[:count])>0x7c0000:count-=1
            while True:
                key=f'{args.key_prefix or ("sa1-standalone" if SA1 else "standalone")}-{category}-{part:02d}'
                title=f'{meta["title"]} {part}' if part>1 or count<len(meta['levels']) else meta['title']
                # Test the actual bank allocator, including alignment and
                # fragmentation, before selecting the cartridge boundary.
                try:prepare(key,title,remaining[:count]);break
                except RuntimeError as exc:
                    if '8 MiB cartridge is full' not in str(exc) or count==1:raise
                    count-=1
            rows.append(build(key,title,remaining[:count]))
            remaining=remaining[count:];part+=1
    destination=args.catalog or ROOT/f'build/{"sa1-" if SA1 else ""}standalone-catalog.json'
    destination.write_text(json.dumps(dict(audio='12 kHz BRR at 1x and below; 8 kHz above 1x' if ADAPTIVE_AUDIO else 'embedded 12 kHz BRR',external_files_required=False,roms=rows),indent=2))
    print('Built',len(rows),'standalone cartridges covering',sum(len(r['levels']) for r in rows),'songs',flush=True)


if __name__=='__main__':main()
