"""Package the verified master ROM, MSU data, and all PCM entry tracks."""
import argparse,hashlib,json,shutil,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'build/packs/master'
WEIGHTS=[20,40,75,100,100,100,75,40,20,0,0]
MEDIA=['menu.png','tech-pairs.png','tech-pairs.mp4','turkish-march.mp4','ce-x-colors.png','ce-x-colors.mp4','results-checkpoints.png','results-zero.png']

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        while data:=f.read(4*1024*1024):h.update(data)
    return h.hexdigest()

def collect():
    digest=sha(BASE/'adofai.sfc');data_digest=sha(BASE/'adofai.msu');v=BASE/'verification';worlds=[]
    with (BASE/'adofai.msu').open('rb') as f:assert f.read(14)==b'ADOFAI-MSU1\0\x0b\x00'
    for n in range(1,62):
        chart=json.loads((BASE/f'level{n}.json').read_text())
        def read(path):
            result=json.loads((v/path).read_text())
            assert result.get('rom_sha256',result.get('sha256'))==digest,('Stale evidence',n,str(path))
            assert result.get('msu_sha256')==data_digest,('Stale MSU evidence',n,str(path))
            return result
        for check in ['controller','audio','render','mesen']+(['checkpoints','mesen-checkpoints'] if chart['checkpoints'] else []):
            stamp=read(Path(f'master-{check}-{n}.json'))
            assert stamp['passed'],('Failed check',check,n)
        controller=read(Path(f'perfect-{n}/result.json'))
        audio=read(Path(f'perfect-{n}/audio-check.json'))
        render=read(Path(f'render-{n}.json'))
        mesen=read(Path(f'mesen-{n}/manifest.json'))
        end=controller['final']
        assert end['state']==3 and end['step']==chart['steps'] and end['combo']==chart['hits'] and end['misses']==0,(n,end)
        assert sum(controller['judgments'])==chart['hits']
        assert controller['score']==sum(c*w for c,w in zip(controller['judgments'],WEIGHTS))
        assert end['tap_overruns']==0 and end['pattern_vblank_overruns']==0
        assert audio['reference']=='MSU PCM' and min(w['correlation'] for w in audio['windows'])>.9 and abs(audio['drift_ms'])<20
        assert controller.get('muted_sound_channels')==audio.get('muted_sound_channels')==[3,4]
        assert render['ppu_chr_match'] and render['max_objects_per_line']<=17 and render['vblank_overruns']==0
        assert render['zoom_values']==1,('Fixed camera scale changed',n)
        assert (v/f'mesen-{n}/result.txt').read_text().endswith('PASS\n')
        assert mesen['track_palette_samples']>100,('Palette was not checked on the PPU',n)
        checkpoints=[]
        if chart['checkpoints']:
            checkpoint=read(Path(f'checkpoints-{n}/result.json'))
            independent=read(Path(f'mesen-checkpoints-{n}/manifest.json'))
            assert (v/f'mesen-checkpoints-{n}/result.txt').read_text().endswith('PASS\n')
            assert independent['track_palette_samples']>100,('Checkpoint palette was not checked',n)
            assert checkpoint['final']['state']==3 and checkpoint['death_scene_frozen']
            assert checkpoint.get('muted_sound_channels')==[3,4]
            assert len(checkpoint['checkpoints'])==len(chart['checkpoints'])
            assert checkpoint['checkpoints_used']==len(chart['checkpoints'])
            assert checkpoint['checkpoint_results_text'].endswith(f'{len(chart["checkpoints"]):03d}')
            for cp in checkpoint['checkpoints']:
                assert min(w['correlation'] for w in cp['audio_windows'])>.9
                assert max(abs(w['offset_ms']) for w in cp['audio_windows'])<30
                checkpoints.append({k:cp[k] for k in ('trigger','floor','origin_frame','audio_windows')})
        assert controller['checkpoint_results_text'].endswith('000')
        worlds.append(dict(id=n,code=chart['code'],title=chart['title'],hits=chart['hits'],combo=end['combo'],misses=end['misses'],
                           ignored_camera_events=chart.get('camera_zoom_events',0),preview_tiles=chart['readability_window']['preview'],simplified_depth=chart.get('simplified_depth',False),
                           track_color_groups=chart['track_color_groups'],track_color_peak=chart['track_color_peak'],ppu_palette_samples=mesen['track_palette_samples'],
                           score=controller['score'],judgments=controller['judgments'],audio_drift_ms=audio['drift_ms'],
                           minimum_audio_correlation=min(w['correlation'] for w in audio['windows']),
                           ppu_samples=render['cache_samples'],max_objects_per_line=render['max_objects_per_line'],
                           vblank_overruns=render['vblank_overruns'],mesen=mesen['summary'],checkpoint_retries=checkpoints))
    assert sum(len(w['checkpoint_retries']) for w in worlds)==208
    speeds=json.loads((ROOT/'build/master-speed-verification/result.json').read_text())
    assert speeds['rom_sha256']==digest and [s['speed'] for s in speeds['speeds']]==[n/10 for n in range(5,21)]
    assert speeds.get('msu_sha256')==data_digest
    for row in speeds['speeds']:
        assert row['rom_sha256']==digest and row['combo']==167 and row['misses']==0
        assert row.get('msu_sha256')==data_digest
        assert row['minimum_correlation']>.9 and abs(row['drift_ms'])<20
    stress=[]
    for name in ('speed20-41','speed20-61','speed05-35','speed20-53','speed20-60'):
        result=read(Path(f'{name}/result.json'));audio=read(Path(f'{name}/audio-check.json'))
        assert result['final']['state']==3 and result['final']['misses']==0 and result['final']['tap_overruns']==0
        assert result['final']['pattern_vblank_overruns']==0
        assert min(w['correlation'] for w in audio['windows'])>.9 and abs(audio['drift_ms'])<20
        if result['speed_tenths']==20:
            duration=(BASE/f'level{result["level"]}.brr').stat().st_size/9*16/12000
            assert result['final']['nmi_audio_ticks']*.008<=duration+.05,('Audio continued beyond its BRR data',name)
        stress.append(dict(code=result['code'],speed=result['speed_tenths']/10,combo=result['final']['combo'],misses=0,
                           minimum_audio_correlation=min(w['correlation'] for w in audio['windows']),drift_ms=audio['drift_ms'],
                           visual_frames_may_drop=True))
    log=(ROOT/'build/latest-unit-tests.log').read_text()
    unit=json.loads((ROOT/'build/latest-unit-tests.json').read_text())
    assert unit['tests']>=81 and f'Ran {unit["tests"]} tests' in log and '\nOK\n' in log
    assert unit['passed'] and unit['rom_sha256']==digest and unit['msu_sha256']==data_digest
    preview=json.loads((v/'preview/manifest.json').read_text());assert preview['rom_sha256']==digest and preview['msu_sha256']==data_digest
    menu=json.loads((v/'menu-pages/result.json').read_text())
    assert menu['rom_sha256']==digest and menu['songs']==61 and len(menu['pages'])==7
    assert menu['checked_published_pixels'] and menu['wraps_both_directions']
    deaths=[]
    for name in ('death-presentation-11-10','death-presentation-41-20','death-presentation-30-10'):
        result=read(Path(name)/'result.json')
        assert result['retains_completed_scene'] and result['frozen_frames']==90 and result['failure_text_visible']
        deaths.append(result)
    mesen_death=read(Path('death-mesen-11/result.json'))
    assert mesen_death['death_scene_stable'] and mesen_death['frozen_frames']==90
    version=read(Path('msu-version.json'));assert version['passed']
    calibration=read(Path('calibration.json'));assert calibration['passed']
    assert calibration['presentation']['passed'] and len(calibration['entry_sounds'])>=5
    calibration_mesen=read(Path('calibration-mesen.json'));assert calibration_mesen['passed']
    sounds=read(Path('tap-sounds.json'));assert sounds['passed']
    motion=read(Path('motion-sections.json'));assert motion['passed']
    streaks=[]
    for n in (30,46,60,61):
        result=read(Path(f'orbit-trails-{n}/result.json'))
        assert result['native_scale'] and result['detached_components']==0 and result['maximum_radial_error']<2.6
        assert result['samples']>100 and result['circular_samples']>100
        streaks.append(result)
    performance=[]
    for n in (11,41,46,60,61):
        after=read(Path(f'presentation-{n}/result.json'))
        before=json.loads((ROOT/f'build/packs/lookahead-before/verification/presentation-{n}/result.json').read_text())
        # Report against the immediately preceding release, including any
        # regression from the longer exact-geometry preview.
        performance.append(dict(code=after['code'],scope='90-second normal-speed Watch replay in Snes9x',
                                before_visual_fps=before['visual_fps'],after_visual_fps=after['visual_fps'],
                                before_longest_gap=before['longest_gap'],after_longest_gap=after['longest_gap'],
                                before_rom_sha256=before['rom_sha256']))
    return dict(verified=True,rom_sha256=digest,msu_sha256=data_digest,worlds=worlds,world_count=61,official_tech_count=22,checkpoint_retries=208,menu_page_indicators=menu,
                regression_tests=unit['tests'],speed_settings=speeds['speeds'],stress_checks=stress,hardware_tested=False,
                presentation_death_checks=deaths,mesen_death_check=mesen_death,presentation_performance=performance,
                calibration_checks=calibration,calibration_mesen_checks=calibration_mesen,tap_sound_checks=sounds,motion_section_checks=motion,
                orbit_streak_checks=streaks,camera_zoom_supported=False,camera_size_range=[1,1],track_colors_supported=True,track_color_cadence_frames=4,
                limitations=['MoveTrack translation and opacity supported; rotation/scale unsupported',
                             'Dense charts at increased speed may drop visual frames',
                             'Moving graphics sampled at about 7.5 Hz; the busiest charts may restrict movement to nearby floors',
                             'Local route preview uses 16 floors or two song seconds, limited by authored visibility',
                             'Distant outlines are neutral; all tile geometry preserves authored angles and segment lengths',
                             'The densest charts simplify track brightness while retaining contours and visibility',
                             'Camera zoom/pan/rotation, scenery, shaders and decorations not reproduced',
                             'Tile colors and neon fills approximate the original; textures and shader bloom are not reproduced',
                             'Color cycles use song time at about 15 Hz; Volume color uses its primary tint',
                             'Dense charts may clear passed tiles immediately'],
                audio=dict(normal_speed='44.1 kHz signed 16-bit stereo PCM',other_speeds='12 kHz mono BRR; pitch follows speed'))

def make_update(out,verification):
    update=ROOT/'dist/adofai-color-update';update.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(out/'adofai.sfc',update/'adofai.sfc')
    shutil.copyfile(out/'adofai.msu',update/'adofai.msu')
    text='''ADOFAI SNES - geometry, movement, calibration and percussion update

Close the running game and replace BOTH adofai.sfc and adofai.msu in
your existing master folder. Keep their names and reopen adofai.sfc.
Keep all 269 PCM files; the music is unchanged.

The song menu now shows up/down arrows when more songs are available
above or below the visible page.

The local route preview now extends at least 16 floors or two song seconds
ahead, subject to original appearance triggers. Distant tiles use subdued
outlines; nearby landing tiles use exact positions and authored colors.
The camera leads gently toward upcoming floors. The upcoming circle is
removed. Midspins use detached pointed tiles; full turns use rounded caps.
Displayed calibration 0 now equals the previous +8 frames.
Calibration extends from -30 to +30, with held directions repeating.
Player taps and autoplay landings now play percussion alongside the music.
Decorative tile movement no longer teleports nonsticky planet pivots.
Expanded square sections keep the physical route beneath the planets.
It Go's failure-only scattering no longer runs on successful landings.
Equal tile angles and lengths retain the same shape throughout the preview.

Original ColorTrack/RecolorTrack events now set tile colors and styles,
including ranges, gaps, easing, repeats, stripes and color cycles.
Neon tiles have dark interiors and colored one-pixel edges. NeonLight
tiles have colored fills. Texture detail and bloom are approximated.
Colors animate at about 15 Hz; audio-volume colors use the primary tint.
Checkpoint retries restore the authored palette along with the route.

Camera zoom has been removed. Track pixels stay at native scale.
Streaks follow the balls' circular orbits, taper, and fade after landing.
Old position-history zigzags and detached tail fragments are removed.
Death keeps a completed scene rather than mixing new and old graphics.
The fixed scale also permits a smaller track cache.

turkish-march.mp4 is a four-second capture around tiles 310..334. It
includes every emulated video frame, including rendering frame drops.

90-second normal-speed Watch replay measurements in Snes9x:
'''
    for row in verification['presentation_performance']:
        text+=f"{row['code']}: {row['before_visual_fps']} -> {row['after_visual_fps']} visual FPS\n"
    text+='''Busy sections can still drop frames. All 61 charts, 208 checkpoint
retries in both emulator cores, 59 unit tests, 16 speed settings, five
stress runs, and four frozen-scene regression checks passed. Pixel checks
on Turkish March, FT21 and FT22 found no detached streak components;
moving streaks follow the 24-pixel circular orbit.

Included replacement MSU data SHA256:
'''+verification['msu_sha256']+'\n'
    text=text.replace('59 unit tests',str(verification['regression_tests'])+' unit tests')
    (update/'README.txt').write_text(text)
    (update/'verification.json').write_text(json.dumps(verification,indent=2))
    (update/'SHA256SUMS.txt').write_text(verification['rom_sha256']+'  adofai.sfc\n'+verification['msu_sha256']+'  adofai.msu\n')
    shutil.copyfile(out/'turkish-march.mp4',update/'turkish-march.mp4')
    shutil.copyfile(out/'ce-x-colors.png',update/'ce-x-colors.png')
    shutil.copyfile(out/'ce-x-colors.mp4',update/'ce-x-colors.mp4')
    archive=ROOT/'dist/adofai-color-update.zip'
    temporary=archive.with_suffix('.zip.partial')
    with zipfile.ZipFile(temporary,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for name in ('adofai.sfc','adofai.msu','README.txt','verification.json','SHA256SUMS.txt','turkish-march.mp4','ce-x-colors.png','ce-x-colors.mp4'):z.write(update/name,name)
    with zipfile.ZipFile(temporary) as z:
        assert z.testzip() is None
        assert hashlib.sha256(z.read('adofai.sfc')).hexdigest()==verification['rom_sha256']
        assert hashlib.sha256(z.read('adofai.msu')).hexdigest()==verification['msu_sha256']
    temporary.replace(archive)
    # Keep the earlier download link current as well.
    for name in ('adofai-update.zip','adofai-readability-update.zip','adofai-native-scale-update.zip'):
        previous=ROOT/'dist'/name
        alias=previous.with_suffix('.zip.partial');shutil.copyfile(archive,alias);alias.replace(previous)
    print(f'ROM + MSU update CRC passed: {archive} ({archive.stat().st_size:,} bytes)',flush=True)

def make_archive(out,archive):
    verification=json.loads((out/'verification.json').read_text())
    names={f['file'] for f in verification['files']}|{'README.txt','verification.json','SHA256SUMS.txt',*MEDIA}
    temporary=archive.with_suffix('.zip.partial')
    with zipfile.ZipFile(temporary,'w',zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True) as z:
        for i,name in enumerate(sorted(names)):
            z.write(out/name,name)
            if i%30==0:print(f'Archived {i+1}/{len(names)} files',flush=True)
    with zipfile.ZipFile(temporary) as z:
        assert set(z.namelist())==names
        assert z.testzip() is None
    temporary.replace(archive)
    print(f'ZIP64 CRC check passed: {archive} ({archive.stat().st_size:,} bytes)',flush=True)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--skip-zip',action='store_true');args=ap.parse_args()
    verification=collect();out=ROOT/'dist/adofai-msu-master';out.mkdir(parents=True,exist_ok=True)
    data=(BASE/'adofai.sfc').read_bytes()
    assert len(data)==0x800000 and sum(data)&65535==int.from_bytes(data[0x40ffde:0x40ffe0],'little')
    manifest=json.loads((BASE/'msu-manifest.json').read_text())
    tracks=[t['track'] for world in manifest['levels'] for t in world['tracks']]
    assert len(tracks)==len(set(tracks))==269
    files=[BASE/'adofai.sfc',BASE/'adofai.msu']+[BASE/f'adofai-{t}.pcm' for t in tracks]
    hashes=[]
    for i,source in enumerate(files):
        if source.suffix=='.pcm':
            with source.open('rb') as f:assert f.read(4)==b'MSU1'
            assert (source.stat().st_size-8)%4==0
        shutil.copyfile(source,out/source.name)
        hashes.append(dict(file=source.name,bytes=source.stat().st_size,sha256=sha(out/source.name)))
        if i%30==0:print(f'Staged {i+1}/{len(files)} files',flush=True)
    verification['files']=hashes
    verification['total_bytes']=sum(f['bytes'] for f in hashes)
    shutil.copyfile(ROOT/'README.md',out/'README.txt')
    (out/'verification.json').write_text(json.dumps(verification,indent=2))
    (out/'SHA256SUMS.txt').write_text(''.join(f'{f["sha256"]}  {f["file"]}\n' for f in hashes))
    for name in MEDIA:
        source=BASE/'verification/orbit-trails-46/motion.mp4' if name=='turkish-march.mp4' else BASE/'verification/orbit-trails-30/motion.mp4' if name=='ce-x-colors.mp4' else BASE/'verification/preview'/name
        shutil.copyfile(source,out/name)
    (out/'tech-pairs.gif').unlink(missing_ok=True)
    make_update(out,verification)
    archive=ROOT/'dist/adofai-msu-master.zip'
    if not args.skip_zip:
        make_archive(out,archive)
    print(f'Packaged 61 worlds, 208 verified checkpoint retries, 269 PCM files; {verification["total_bytes"]:,} extracted bytes.',flush=True)

if __name__=='__main__':main()
