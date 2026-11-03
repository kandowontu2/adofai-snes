"""Build an isolated SA-1 master from the frozen compiled chart assets."""
import argparse,json,os,re,shutil,subprocess,sys
from pathlib import Path
import campaign_assets as assets
ROOT=Path(__file__).resolve().parents[1]

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,default=ROOT/'build/packs/sa1-master')
    ap.add_argument('--source',type=Path,default=ROOT/'build/packs/master');args=ap.parse_args()
    out=args.out.resolve();source=args.source.resolve();out.mkdir(parents=True,exist_ok=True)
    if not (out/'pack.json').exists():
        for p in source.iterdir():
            if not p.is_file():continue
            if p.suffix=='.pcm':os.link(p,out/p.name)
            else:shutil.copyfile(p,out/p.name)
    pack=json.loads((out/'pack.json').read_text());charts=[json.loads((out/f'level{n}.json').read_text()) for n in pack['levels']]
    assets.OUT=out;blobs=assets.ui_assets(pack['title'],mode7=True)
    for c in charts:
        n=c['id']
        for prefix in ('chart','track_chr','track_map'):blobs[f'{prefix}{n}']=(out/f'{prefix}{n}.bin').read_bytes()
        blobs[f'music{n}']=blobs[f'timeline{n}']=bytes(2)
        blobs[f'checkpoints{n}']=bytes(max(2,14*len(c['checkpoints'])))
    assets.pack_payload(blobs,charts,msu=True,sa1=True);assets.common_tables(charts)
    if any(c.get('camera_rotation_versions') for c in charts):
        with (out/'adofai.msu').open('r+b') as f:
            f.seek(12);f.write(bytes([20 if any(c["id"]>=62 for c in charts) else 19 if any(c.get('adaptive_raster') for c in charts) else 18 if any(c.get('mode7_zoom_enabled') for c in charts) else 17 if any(c.get('camera_position_events',0) for c in charts) else 16 if any(c.get('native_layout_version',0)>=2 for c in charts) else 15 if any(c.get('track_separators_version') for c in charts) else 14 if any(c.get('opacity_curve_version') for c in charts) else 13,0]))
    compile_engine(out)

def compile_engine(out):
    from hit_timing import patch_pack as patch_hit_timing
    patch_hit_timing(out)
    from animation_references import patch_pack as patch_references
    patch_references(out)
    from animation_bulk import patch_pack as patch_animation
    patch_animation(out)
    from animation_catchup import patch_pack as patch_catchup
    patch_catchup(out)
    from planet_assets import patch_pack
    patch_pack(out)
    # Frozen standalone packs retain their linker config. Migrate that
    # layout before compiling the new banked camera helper as well.
    config=out/'sa1.cfg'
    if config.exists():
        text=config.read_text().replace('size=$0600,type=rw','size=$0680,type=rw').replace('FASTIRAM: start=$001000','FASTIRAM: start=$003100').replace('STATE: start=$1800,size=$0404','STATE: start=$1800,size=$0410')
        if 'CAMERAEXT:' not in text:
            text=text.replace('WORKER: start=$018000,size=$8000,type=ro,file=%O,fill=yes;',
                'WORKER: start=$018000,size=$7000,type=ro,file=%O,fill=yes;\n CAMERAEXT: start=$01F000,size=$1000,type=ro,file=%O,fill=yes;')
            text=text.replace('SA1CODE: load=WORKER,type=ro;',
                'SA1CODE: load=WORKER,type=ro;\n CAMERA: load=CAMERAEXT,type=ro;')
        if 'POLLWRAM:' not in text:
            text=text.replace(' STATE:', ' POLLWRAM: start=$001000,size=$0800,type=rw;\n STATE:')
            text=text.replace(' BSS: load=STATE,type=bss;', ' BSS: load=STATE,type=bss;\n FASTWRAM: load=ROM,run=POLLWRAM,type=ro,define=yes;')
        text=text.replace('FASTWRAM: load=ROM,','FASTWRAM: load=CAMERAEXT,')
        config.write_text(text)
    if not (out/'sa1_worker.bin').exists():(out/'sa1_worker.bin').write_bytes(bytes(32768))
    subprocess.run([sys.executable,str(ROOT/'build_campaign.py'),'--pack','master','--out',str(out),'--skip-assets'],cwd=ROOT,check=True)
    # Data labels retain the main engine's layout; the worker's absolute
    # temporary accesses use bank $40, and its direct page is private IRAM.
    layout=(ROOT/'src/campaign.s').read_text().split('.segment "ZEROPAGE"')[0]
    layout=layout.replace('M7_CACHE_READY=M7_SHARED_BASE+$FC46','M7_CACHE_READY=$400004')
    (out/'sa1_layout.inc').write_text(layout)
    labels=re.findall(r'al ([0-9A-Fa-f]+) \.([\w]+)',(out/'adofai.lbl').read_text())
    (out/'sa1_symbols.inc').write_text('\n'.join(f'{name} = ${int(value,16):04X}' for value,name in labels if int(value,16)<0x100 or 0x1800<=int(value,16)<0x2000))
    (out/'sa1_worker.cfg').write_text('MEMORY { ROM: start=$8000,size=$7000,type=ro,file=%O,fill=yes; }\nSEGMENTS { CODE: load=ROM,type=ro; }\n')
    sys.path.insert(0,str(ROOT));from build import command
    subprocess.run([command('ca65'),'--cpu','65816','-I',str(out),'-I',str(ROOT/'src'),'-g','-o',str(out/'sa1_worker.o'),str(ROOT/'src/sa1_worker.s')],check=True)
    subprocess.run([command('ld65'),'-C',str(out/'sa1_worker.cfg'),'-o',str(out/'sa1_worker.bin'),'-Ln',str(out/'sa1_worker.lbl'),str(out/'sa1_worker.o')],check=True)
    subprocess.run([sys.executable,str(ROOT/'build_campaign.py'),'--pack','master','--out',str(out),'--skip-assets'],cwd=ROOT,check=True)

if __name__=='__main__':main()
