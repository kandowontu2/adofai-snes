"""Build an isolated SA-1 master from the frozen compiled chart assets."""
import argparse,json,os,re,shutil,subprocess,sys
from pathlib import Path
import campaign_assets as assets
ROOT=Path(__file__).resolve().parents[1]

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,default=ROOT/'build/packs/sa1-master')
    ap.add_argument('--source',type=Path,default=ROOT/'build/packs/master')
    ap.add_argument('--no-pcm',action='store_true',help='Build ROM/data without regenerating unchanged PCM music')
    ap.add_argument('--stream-levels',nargs='+',type=int,default=[],
                    help='Compile canonical per-frame charts into SA-1 animation packets (requires a resident native master)')
    args=ap.parse_args()
    out=args.out.resolve();source=args.source.resolve();out.mkdir(parents=True,exist_ok=True)
    if not (out/'pack.json').exists():
        for p in source.iterdir():
            if not p.is_file():continue
            if p.suffix=='.pcm':os.link(p,out/p.name)
            else:shutil.copyfile(p,out/p.name)
    pack=json.loads((out/'pack.json').read_text());charts=[json.loads((out/f'level{n}.json').read_text()) for n in pack['levels']]
    if args.stream_levels:
        assert set(args.stream_levels)<=set(pack['levels']), 'Stream chart is absent from this pack'
        assert any(c.get('native_stream_format') for c in charts), 'Streaming requires the resident native master decoder'
        from sa1_stream import prepare
        for n in args.stream_levels:prepare(out,n)
        charts=[json.loads((out/f'level{n}.json').read_text()) for n in pack['levels']]
        from msu_assets import generate
        generate(out,charts,{c['id']:(out/f"level{c['id']}.brr").read_bytes() for c in charts},generate_pcm=not args.no_pcm)
    assets.OUT=out;blobs=assets.ui_assets(pack['title'],mode7=True)
    for c in charts:
        n=c['id']
        for prefix in ('chart','track_chr','track_map'):
            path=out/f'{prefix}{n}.bin';blob=path.read_bytes()
            if prefix=='track_chr':
                from track_packbits import decode,encode
                raw=decode(blob);packed=encode(raw)
                assert len(packed)<=len(blob) and decode(packed)==raw
                blob=packed;path.write_bytes(blob)
            blobs[f'{prefix}{n}']=blob
        if c.get('resident_pattern_format'):
            for prefix in ('resident_raw','resident_future'):blobs[f'{prefix}{n}']=(out/f'{prefix}{n}.bin').read_bytes()
        if c.get('sa1_stream_format'):
            from sa1_stream import rom_index
            blobs[f'stream_index{n}']=rom_index((out/f'stream_index{n}.bin').read_bytes())
            blobs[f'resident_stream{n}']=(out/f'resident_stream{n}.bin').read_bytes()
            if c.get('fallback_stream_packets'):
                for prefix in ('stream_index_fallback','resident_stream_fallback'):
                    data=(out/f'{prefix}{n}.bin').read_bytes()
                    blobs[f'{prefix}{n}']=rom_index(data) if prefix.startswith('stream_index') else data
        if c.get('native_stream_format'):blobs[f'resident_animation{n}']=(out/f'resident_animation{n}.bin').read_bytes()
        blobs[f'music{n}']=blobs[f'timeline{n}']=bytes(2)
        blobs[f'checkpoints{n}']=bytes(max(2,14*len(c['checkpoints'])))
    if any(c.get('neo_cosmos') for c in charts):
        from neo_runtime_assets import binary_tables
        blobs['neo_tables']=binary_tables(out,[c['id'] for c in charts])[0]
    assets.pack_payload(blobs,charts,msu=True,sa1=True);assets.common_tables(charts)
    if any(c.get('camera_rotation_versions') for c in charts):
        with (out/'adofai.msu').open('r+b') as f:
            f.seek(12);f.write(bytes([20 if any(c["id"]>=62 for c in charts) else 19 if any(c.get('adaptive_raster') for c in charts) else 18 if any(c.get('mode7_zoom_enabled') for c in charts) else 17 if any(c.get('camera_position_events',0) for c in charts) else 16 if any(c.get('native_layout_version',0)>=2 for c in charts) else 15 if any(c.get('track_separators_version') for c in charts) else 14 if any(c.get('opacity_curve_version') for c in charts) else 13,0]))
    compile_engine(out,generate_pcm=not args.no_pcm)

def compile_engine(out, *, generate_pcm=True):
    # Cached packs embed the SPC driver in the payload, not spc.bin. Refresh
    # it on engine rebuilds so audio fixes reach existing release variants.
    from spc_campaign import assemble as assemble_spc
    driver = assemble_spc(calibration_period=125)
    addresses = (out/'addresses.inc').read_text()
    if 'SA1_WRAM_RENDERER' not in addresses:
        addresses+='\nSA1_WRAM_RENDERER = 1\n'
        (out/'addresses.inc').write_text(addresses)
    expected = int(re.search(r'SPC_DRIVER_BYTES = (\d+)', addresses).group(1))
    assert len(driver) == expected, 'SPC driver size changed; regenerate pack assets'
    location = json.loads((out/'placements.json').read_text())['spc_driver']
    offset = location-0xC00000 if location >= 0xC00000 else location
    with (out/'sa1_payload.bin').open('r+b') as payload:
        assert 0x10000 <= offset and offset+len(driver)-0x10000 <= os.fstat(payload.fileno()).st_size
        payload.seek(offset-0x10000)
        payload.write(driver)
    (out/'spc_driver.bin').write_bytes(driver)
    (out/'spc.bin').write_bytes(driver)
    # Color presets are editable source, including when rebuilding frozen packs.
    from presentation_assets import tables as presentation_tables
    table_path=out/'tables.inc'
    colors=re.search(r'^orb_colors:.*$',presentation_tables(assets.FPS),re.M).group(0)
    current=table_path.read_text()
    adaptive='audio_speed_pitches:' in current
    speed_tables=presentation_tables(assets.FPS,compact=True,adaptive_audio=adaptive).split('judgment_weights:')[0]
    current=re.sub(r'speed_pitches:.*?(?=judgment_weights:)',lambda _:speed_tables,current,flags=re.S)
    from menu_sets import tables as menu_tables,write_count as write_menu_count
    menu_levels=json.loads((out/'pack.json').read_text())['levels']
    current=re.sub(r'^level_view_insets:.*\n','',current,flags=re.M)
    current=re.sub(r'^level_bitmap_prefetch:.*\n','',current,flags=re.M)
    bitmap_enabled=lambda c:bool(c.get('bitmap_prefetch_versions')) and c.get('bitmap_prefetch_enabled',True)
    current='level_bitmap_prefetch: .byte '+','.join(str(int(bitmap_enabled(json.loads((out/f'level{n}.json').read_text())))) for n in menu_levels)+'\n'+current
    current='level_view_insets: .byte '+','.join(str(json.loads((out/f'level{n}.json').read_text()).get('viewport_inset',0)) for n in menu_levels)+'\n'+current
    current=current.split('MENU_SET_COUNT =')[0].split('; MENU_SET_TABLES')[0]+menu_tables(menu_levels)
    if 'NEO_BUILD = 1' in addresses:
        from neo_runtime_assets import tables as neo_tables
        current+=neo_tables(out,menu_levels)
        current+='\n.segment "NEOCODE"\nlevel_early_dma: .byte '+','.join(str(int(json.loads((out/f'level{n}.json').read_text()).get('early_vblank_trial',False))) for n in menu_levels)+'\n.segment "RODATA"\n'
    write_menu_count(out,menu_levels)
    assert re.search(r'^orb_colors:.*$',current,re.M), 'Missing planet color table'
    table_path.write_text(re.sub(r'^orb_colors:.*$',lambda _:colors,current,flags=re.M))
    from hit_timing import patch_pack as patch_hit_timing
    patch_hit_timing(out)
    from animation_references import patch_pack as patch_references
    patch_references(out)
    from animation_bulk import patch_pack as patch_animation
    patch_animation(out)
    from animation_catchup import patch_pack as patch_catchup
    patch_catchup(out)
    from animation_sparse import patch_pack as patch_sparse
    patch_sparse(out)
    from embedded_hit_audio import patch_pack as patch_embedded_audio
    patch_embedded_audio(out, generate_pcm=generate_pcm)
    from planet_assets import patch_pack
    patch_pack(out)
    # Frozen standalone packs retain their linker config. Migrate that
    # layout before compiling the new banked camera helper as well.
    config=out/'sa1.cfg'
    if config.exists():
        text=config.read_text().replace('STATE: start=$1800,size=$0420','STATE: start=$1800,size=$04A0').replace('STATE: start=$1800,size=$0410','STATE: start=$1800,size=$04A0').replace('FASTIRAM: start=$003100,size=$0600','FASTIRAM: start=$003100,size=$0680').replace('FASTIRAM: start=$001000','FASTIRAM: start=$003100').replace('STATE: start=$1800,size=$0404','STATE: start=$1800,size=$04A0')
        if 'CAMERAEXT:' not in text:
            text=text.replace('WORKER: start=$018000,size=$8000,type=ro,file=%O,fill=yes;',
                'WORKER: start=$018000,size=$7000,type=ro,file=%O,fill=yes;\n CAMERAEXT: start=$01F000,size=$1000,type=ro,file=%O,fill=yes;')
            text=text.replace('SA1CODE: load=WORKER,type=ro;',
                'SA1CODE: load=WORKER,type=ro;\n CAMERA: load=CAMERAEXT,type=ro;')
        if 'POLLWRAM:' not in text:
            text=text.replace(' STATE:', ' POLLWRAM: start=$001000,size=$0800,type=rw;\n STATE:')
            text=text.replace(' BSS: load=STATE,type=bss;', ' BSS: load=STATE,type=bss;\n FASTWRAM: load=ROM,run=POLLWRAM,type=ro,define=yes;')
        text=text.replace('FASTWRAM: load=ROM,','FASTWRAM: load=CAMERAEXT,')
        if 'SA1_WRAM_RENDERER = 1' in (out/'addresses.inc').read_text():
            text=text.replace('FASTIRAM: start=$003100,size=$0680','FASTIRAM: start=$000800,size=$0600')
            text=text.replace('FASTIRAM: start=$000800,size=$0800','FASTIRAM: start=$000800,size=$0600')
            text=text.replace('FASTIRAM: start=$000800,size=$0680','FASTIRAM: start=$000800,size=$0600')
            text=text.replace('POLLWRAM: start=$001000,size=$0800','POLLWRAM: start=$000E00,size=$0A00')
        text=text.replace('ZP: start=$000000,size=$00FF','ZP: start=$000000,size=$0100')
        text=text.replace('STATE: start=$1800,size=$04A0','STATE: start=$1800,size=$0500')
        if 'NEO_BUILD' in addresses and 'NEOBANK:' not in text:
            text=text.replace(' PAY: start=$810000,size=$7F0000',
                ' NEOBANK: start=$028000,size=$2000,type=ro,file=%O,fill=yes;\n PAY: start=$812000,size=$7EE000')
            text=text.replace(' SA1PAYLOAD:', ' NEOCODE: load=NEOBANK,type=ro;\n SA1PAYLOAD:')
        if 'SA1_MODE1_BUILD' in addresses:
            text=text.replace('FASTIRAM: start=$000800,size=$0600','FASTIRAM: start=$000800,size=$0640')
            text=text.replace('POLLWRAM: start=$000E00,size=$0A00','POLLWRAM: start=$000E40,size=$09C0')
        if 'SA1_FASTROM_HELPERS = 1' in addresses:
            text=text.replace('CAMERAEXT: start=$01F000','CAMERAEXT: start=$81F000').replace('NEOBANK: start=$028000','NEOBANK: start=$828000')
        if 'NEO_CODE_BYTES = $3000' in addresses:
            text=text.replace('size=$2000,type=ro,file=%O,fill=yes;\n PAY: start=$812000,size=$7EE000',
                              'size=$3000,type=ro,file=%O,fill=yes;\n PAY: start=$813000,size=$7ED000')
        config.write_text(text)
    if not (out/'sa1_worker.bin').exists():(out/'sa1_worker.bin').write_bytes(bytes(32768))
    subprocess.run([sys.executable,str(ROOT/'build_campaign.py'),'--pack','master','--out',str(out),'--skip-assets'],cwd=ROOT,check=True)
    # Resolve engine labels before relocating worker-private temporaries.
    # Explicit shared buffers carry jobs; each CPU keeps its own scratch.
    from sa1_layout import worker_layout, worker_symbols, worker_config
    layout=worker_layout((ROOT/'src/campaign.s').read_text())
    (out/'sa1_layout.inc').write_text(layout)
    (out/'sa1_symbols.inc').write_text(worker_symbols((out/'adofai.lbl').read_text()))
    (out/'sa1_worker.cfg').write_text(worker_config())
    sys.path.insert(0,str(ROOT));from build import command
    subprocess.run([command('ca65'),'--cpu','65816','-I',str(out),'-I',str(ROOT/'src'),'-g','-o',str(out/'sa1_worker.o'),str(ROOT/'src/sa1_worker.s')],check=True)
    subprocess.run([command('ld65'),'-C',str(out/'sa1_worker.cfg'),'-o',str(out/'sa1_worker.bin'),'-Ln',str(out/'sa1_worker.lbl'),str(out/'sa1_worker.o')],check=True)
    subprocess.run([sys.executable,str(ROOT/'build_campaign.py'),'--pack','master','--out',str(out),'--skip-assets'],cwd=ROOT,check=True)

if __name__=='__main__':main()
