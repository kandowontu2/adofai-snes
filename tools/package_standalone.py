"""Publish verified self-contained ROMs and small per-cartridge downloads."""
import hashlib,json,shutil,zipfile
from pathlib import Path
from presentation_assets import WEIGHTS
ROOT=Path(__file__).resolve().parents[1]


def collect(catalog):
    worlds=[];roms=[]
    for rom in catalog['roms']:
        base=ROOT/'build/packs'/rom['key'];v=base/'verification'
        data=(base/'adofai.sfc').read_bytes();digest=hashlib.sha256(data).hexdigest()
        assert len(data)==0x800000 and digest==rom['rom_sha256']
        assert sum(data)&65535==int.from_bytes(data[0x40ffde:0x40ffe0],'little')
        assert not list(base.glob('*.msu')) and not list(base.glob('*.pcm'))
        def read(path):
            report=json.loads((v/path).read_text())
            assert report.get('rom_sha256',report.get('sha256'))==digest,(rom['key'],path,'Stale evidence')
            assert report.get('msu_sha256') is None
            return report
        menu=read(Path('menu-pages/result.json'));assert menu['songs']==len(rom['levels']) and menu['checked_published_pixels']
        for local,n in enumerate(rom['levels'],1):
            chart=json.loads((base/f'level{n}.json').read_text())
            checks=['controller','audio','render','mesen']+(['checkpoints','mesen-checkpoints'] if chart['checkpoints'] else [])
            for check in checks:assert read(Path(f'standalone-{check}-{local}.json'))['passed']
            controller=read(Path(f'perfect-{local}/result.json'));audio=read(Path(f'perfect-{local}/audio-check.json'))
            render=read(Path(f'render-{n}.json'));mesen=read(Path(f'mesen-{local}/manifest.json'))
            end=controller['final']
            assert end['state']==3 and end['step']==chart['steps'] and end['combo']==chart['hits'] and end['misses']==0
            assert end['msu_present']==end['msu_pcm']==end['tap_overruns']==end['pattern_vblank_overruns']==0
            assert sum(controller['judgments'])==chart['hits'] and controller['score']==sum(c*w for c,w in zip(controller['judgments'],WEIGHTS))
            assert audio['reference']=='decoded cartridge BRR' and min(w['correlation'] for w in audio['windows'])>.9 and abs(audio['drift_ms'])<20
            assert controller.get('muted_sound_channels')==audio.get('muted_sound_channels')==[3,4]
            assert render['ppu_chr_match'] and render['max_objects_per_line']<=17 and render['vblank_overruns']==0
            assert mesen['track_palette_samples']>100 and (v/f'mesen-{local}/result.txt').read_text().endswith('PASS\n')
            cp_count=len(chart['checkpoints'])
            checkpoint_audio=[]
            if cp_count:
                checkpoint=read(Path(f'checkpoints-{local}/result.json'))
                independent=read(Path(f'mesen-checkpoints-{local}/manifest.json'))
                assert checkpoint['final']['state']==3 and checkpoint['death_scene_frozen'] and checkpoint['checkpoints_used']==cp_count
                assert len(checkpoint['checkpoints'])==cp_count
                assert independent['track_palette_samples']>100 and (v/f'mesen-checkpoints-{local}/result.txt').read_text().endswith('PASS\n')
                for cp in checkpoint['checkpoints']:
                    assert min(w['correlation'] for w in cp['audio_windows'])>.9 and max(abs(w['offset_ms']) for w in cp['audio_windows'])<30
                    checkpoint_audio.append({k:cp[k] for k in ('trigger','floor','origin_frame','audio_windows')})
            worlds.append(dict(id=n,code=chart['code'],cartridge=rom['file'],combo=end['combo'],misses=0,
                               fixed_tile_positions=chart.get('standalone_fixed_tile_positions',False),preview=chart['readability_window'],
                               checkpoint_retries=cp_count,checkpoint_audio=checkpoint_audio,minimum_audio_correlation=min(w['correlation'] for w in audio['windows']),audio_drift_ms=audio['drift_ms'],ppu_palette_samples=mesen['track_palette_samples']))
        roms.append(dict(rom,bytes=len(data)))
    assert sorted(w['id'] for w in worlds)==list(range(1,62)) and sum(w['checkpoint_retries'] for w in worlds)==208
    speeds=json.loads((ROOT/'build/standalone-main-01-speed-verification/result.json').read_text())
    assert speeds['rom_sha256']==roms[0]['rom_sha256'] and len(speeds['speeds'])==16
    stress=json.loads((ROOT/'build/standalone-stress.json').read_text())
    assert stress['passed'] and len(stress['cases'])==3
    for case in stress['cases']:
        assert case['rom_sha256']==next(r['rom_sha256'] for r in roms if r['key']==case['pack'])
    return dict(verified=True,audio='12 kHz mono BRR at every speed; pitch follows speed',external_files_required=False,
                worlds=worlds,roms=roms,checkpoint_retries_per_core=208,cores=['Snes9x','Mesen'],
                speed_settings=speeds['speeds'],stress_checks=stress['cases'],hardware_tested=False)


def archive(path,files,readme=None):
    temporary=path.with_suffix('.zip.partial')
    with zipfile.ZipFile(temporary,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for source,name in files:z.write(source,name)
        if readme:z.writestr('README.txt',readme)
    with zipfile.ZipFile(temporary) as z:assert z.testzip() is None
    temporary.replace(path)


def main():
    catalog=json.loads((ROOT/'build/standalone-catalog.json').read_text());verification=collect(catalog)
    out=ROOT/'dist/adofai-standalone';out.mkdir(parents=True,exist_ok=True)
    if (out/'catalog.json').exists():
        previous=json.loads((out/'catalog.json').read_text())
        retired={r['file'] for r in previous['roms']}-{r['file'] for r in catalog['roms']}
        legacy=out.parent/'legacy-standalone'
        for name in retired:
            for suffix in ('.sfc','.zip'):
                source=out/Path(name).with_suffix(suffix)
                if not source.exists():continue
                legacy.mkdir(exist_ok=True)
                target=legacy/source.name
                if target.exists():target=legacy/(source.stem+'-'+hashlib.sha256(source.read_bytes()).hexdigest()[:12]+source.suffix)
                assert source.resolve().is_relative_to(out.resolve()) and target.resolve().is_relative_to(legacy.resolve())
                if not target.exists():source.replace(target)
    readme='''ADOFAI SNES - standalone cartridges

Open any .sfc in a SNES emulator with 8-MiB ExHiROM support.
Each cartridge contains its songs, track animation and compressed music.
No MSU expansion, .msu file, .pcm file or separate music download is needed.
Music is 12-kHz mono BRR at all speeds, with pitch following speed.

The 61 songs are grouped into cartridges of at most 8 MiB. Categories
with multiple cartridges have numbered parts. Each ROM also has its own
small ZIP download. All cartridges include the current authored tile
colors, native scale, circular streaks, visibility, checkpoints, timing
options and independent orb colors. Zoom is removed. Busy sections can
still drop visual frames. Physical hardware has not been tested.

FT05-X, FT07-X, FT10-X, FT14-X, FT17-X and FT21-X use fixed tile positions
and simpler depth brightness to keep uploads within budget alongside BRR.
Their distant previews use route lines and tile markers; the current tile
retains authored fill. They retain the extended 16-floor / two-second route
preview, authored visibility and all timing/checkpoints. Passed tiles clear
immediately in these charts.
Their movement effects remain available in the MSU master.

The upcoming circle is removed. Landing tiles use exact coordinates.
Midspins have detached pointed tiles; full turns have detached rounded caps.
Displayed calibration 0 equals the previous +8 frames.
Calibration covers -30 to +30; held menu directions repeat after a delay.
Player taps and autoplay landings have percussion sounds. Decorative tile
movement respects the original planet sticking flags; the active nonsticky
route stays beneath the planets in expanded square sections.

UP/DOWN select a song; arrows indicate additional menu pages.
L/R adjust speed by 0.1x before starting. START launches/retries;
SELECT returns to the menu from death/results. B opens Options.

Cartridges and song codes:
'''
    files=[];sums=''
    for rom in verification['roms']:
        source=ROOT/'build/packs'/rom['key']/'adofai.sfc';target=out/rom['file'];shutil.copyfile(source,target)
        assert hashlib.sha256(target.read_bytes()).hexdigest()==rom['rom_sha256']
        files.append((target,rom['file']));sums+=rom['rom_sha256']+'  '+rom['file']+'\n'
        readme+=rom['file']+': '+', '.join(rom['codes'])+'\n'
    (out/'README.txt').write_text(readme)
    (out/'SHA256SUMS.txt').write_text(sums)
    (out/'verification.json').write_text(json.dumps(verification,indent=2))
    (out/'catalog.json').write_text(json.dumps(catalog,indent=2))
    extras=[(out/name,name) for name in ('README.txt','SHA256SUMS.txt','verification.json','catalog.json')]
    for rom in verification['roms']:
        archive(out/Path(rom['file']).with_suffix('.zip'),[(out/rom['file'],rom['file'])],
                readme+'\nThis download: '+rom['file']+'\nSHA256: '+rom['rom_sha256']+'\n')
    combined=ROOT/'dist/adofai-standalone-roms.zip';archive(combined,files+extras)
    # Existing bundle links remain current, now containing numbered parts.
    shutil.copyfile(combined,ROOT/'dist/adofai-official-worlds.zip')
    mainfiles=[(out/r['file'],r['file']) for r in verification['roms'] if r['key'].startswith('standalone-main-')]
    archive(ROOT/'dist/adofai-main-worlds.zip',mainfiles,readme)
    # Preserve earlier stock builds under an explicit legacy folder so the
    # old root filenames are not mistaken for this release's numbered parts.
    dist=out.parent.resolve()
    old_names=['adofai-main-worlds.sfc','adofai-bonus-worlds.sfc','adofai-extra-worlds.sfc',
               'adofai-crown-island.sfc','adofai-collaboration-worlds.sfc','adofai-joke-worlds.sfc']
    if any((dist/name).exists() for name in old_names):
        legacy=dist/'legacy-stock-audio';legacy.mkdir(exist_ok=True)
        for name in old_names+['README.txt','SHA256SUMS.txt','verification.json']:
            source=dist/name
            if not source.exists():continue
            target=legacy/name
            if target.exists():target=legacy/(source.stem+'-'+hashlib.sha256(source.read_bytes()).hexdigest()[:12]+source.suffix)
            assert source.resolve().is_relative_to(dist) and target.resolve().is_relative_to(dist)
            if not target.exists():source.replace(target)
    shutil.copyfile(ROOT/'README.md',dist/'README.txt')
    print('Packaged',len(files),'standalone cartridges, 61 songs:',combined,combined.stat().st_size,'bytes',flush=True)


if __name__=='__main__':main()
