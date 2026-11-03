"""Publish the dataset-14 update, with evidence bound to every cartridge."""
import argparse,json
from pathlib import Path
from package_graphics_update import read,sha,copy,bound,graphics
from package_standalone import archive
from verification_data import identity

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'build/packs/sa1-safe-v14'
DIST=ROOT/'dist'
NOTE='''ADOFAI SNES - SA-1 rendering and authored-behavior update

61 charts; standalone cartridges need no external audio files.
Master users must replace BOTH adofai.sfc and adofai.msu (dataset 14).
Keep the existing 269 PCM files. They have not changed.

This update corrects imported event times, local beat durations, movement
units, eased disappearance and zero-scale hiding. It adds authored hit
samples and changes, plus four countdown beats on checkpoint retries.
R's moving tiles update at 30 Hz. Cache preparation and video transfers
have been optimized, including the long held picture in Feral Insane.

Dense scenes still drop visual frames. Very dense standalone charts at 2x
can remain severely slow. This is not a locked-60-FPS release.
Zoom, authored camera panning, individual tile rotation and gradual tile
scaling remain unsupported. Palette/fade precision is limited by SNES
graphics. Physical hardware has not been tested.

Calibration remains 120 BPM with continuous orbit, 16 taps and -30..+30
adjustment; zero is the former +8. START retries; SELECT returns to menu.
See verification.json for exact hashes and verification scope.
'''

def nested_bound(path,current):
    report=read(path);assert report['passed']
    assert report['cases'] and all(all(r.get(k)==v for k,v in current.items()) for r in report['cases'])
    return report

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--check-only',action='store_true');a=ap.parse_args()
    current=identity(BASE/'adofai.sfc');v=BASE/'verification'
    with (BASE/'adofai.msu').open('rb') as f:assert f.read(14)==b'ADOFAI-MSU1\0\x0e\0'
    pixels=graphics(BASE.name,[1,1.3,2]);assert len(pixels)==183
    checks={n:bound(v/(n+'.json'),current) for n in ('sa1-layout','authored-visibility','calibration','calibration-mesen','tap-sounds','hit-lighting','msu-version','sound-banks')}
    checks['countdown']=nested_bound(v/'checkpoint-countdown.json',current)
    checks['menu']=bound(v/'menu-pages/result.json',current)
    assert len(checks['authored-visibility']['worlds'])==61 and checks['menu']['songs']==61
    unit=bound(ROOT/'build/sa1-safe-v14-unit-tests.json',current);assert unit['tests']>=102
    regression=bound(ROOT/'build/sa1-safe-v14-verification-controller-audio-checkpoints-mesen-checkpoints.json',current)
    assert [r['level'] for r in regression['results']]==[24,25,31,43,44,45] and all(r.get('passed') for r in regression['results'])
    mesen=[bound(v/f'mesen-{n}-autoplay/ppu-verification.json',current) for n in (24,25,43,44,45)]
    catalog=read(ROOT/'build/sa1-safe-standalone-catalog.json')
    assert sorted(n for r in catalog['roms'] for n in r['levels'])==list(range(1,62))
    calibration=read(ROOT/'build/safe-calibration-standalone.json')
    assert calibration['passed'] and {r['key']:r['rom_sha256'] for r in calibration['cartridges']}=={r['key']:r['rom_sha256'] for r in catalog['roms']}
    stand_pixels=[];layouts=[];stand_mesen=[];performance=[]
    for row in catalog['roms']:
        base=ROOT/'build/packs'/row['key'];expected=dict(rom_sha256=row['rom_sha256'],msu_sha256=None)
        assert identity(base/'adofai.sfc')==expected
        layouts.append(bound(base/'verification/sa1-layout.json',expected))
        stand_pixels.extend(graphics(row['key'],[1,2]))
        for path in (base/'verification').glob('mesen-*-autoplay/ppu-verification.json'):stand_mesen.append(bound(path,expected))
        for path in (base/'verification').glob('performance-*/result.json'):performance.append(bound(path,expected))
        row['file']=row['file'].replace('sa1-safe-','sa1-')
    assert len(stand_pixels)==122
    assert {r['code'] for r in stand_mesen}>={'XO-X','XT-X','FT04-X','FT05-X','FT06-X'}
    assert {r['code'] for r in performance}>={'FT04-X','FT05-X','FT06-X'}
    retry_base=ROOT/'build/packs/sa1-safe-tech-03'
    standalone_countdown=nested_bound(retry_base/'verification/checkpoint-countdown.json',identity(retry_base/'adofai.sfc'))
    stress_base=ROOT/'build/packs/sa1-safe-tech-10'
    stress_identity=identity(stress_base/'adofai.sfc')
    stress_audio=bound(stress_base/'verification/transport-audio-2x/audio-check.json',stress_identity)
    assert min(r['correlation'] for r in stress_audio['windows'])>.9 and abs(stress_audio['drift_ms'])<20
    assert 'FT21-X' in {r['code'] for r in performance}
    demo=ROOT/'build/packs/sa1-safe-demo';demo_checks=graphics(demo.name,[1,1.3,2])
    files=[]
    prior=read(DIST/'adofai-msu-master/verification.json')
    for old in prior['files']:
        p=BASE/old['file'];digest=sha(p)
        if p.suffix=='.pcm':assert digest==old['sha256'],('PCM changed',p.name)
        files.append(dict(file=p.name,sha256=digest,bytes=p.stat().st_size))
    assert sum(r['file'].endswith('.pcm') for r in files)==269
    source_hashes={p.relative_to(ROOT).as_posix():sha(p) for folder in ('src','tools') for p in sorted((ROOT/folder).rglob('*')) if p.is_file() and p.suffix in ('.s','.inc','.py','.lua','.cfg')}
    report=dict(verified=True,source_hashes=source_hashes,**current,dataset_version=14,world_count=61,files=files,unchanged_pcm=True,
        hardware_tested=False,ppu_replays=pixels,checks=checks,unit_tests=unit,controller_and_checkpoint_checks=regression,mesen_ppu=mesen,
        verification_scope='All 61 master charts: complete-song, every displayed PPU frame at 1.0x/1.3x/2.0x. Six affected charts: controller, waveform audio and checkpoint retries in Snes9x/Mesen. Five affected charts: Mesen committed video-memory checks. Calibration in both cores; authored sample banks and four audible retry beats checked. No physical hardware tests.')
    standalone=dict(verified=True,source_hashes=source_hashes,roms=catalog['roms'],external_files_required=False,ppu_replays=stand_pixels,
        layouts=layouts,calibration_checks=calibration,mesen_ppu=stand_mesen,performance=performance,high_speed_audio=stress_audio,checkpoint_countdown=standalone_countdown,hardware_tested=False,
        verification_scope='All 61 standalone charts: complete-song, every displayed PPU frame at 1.0x/2.0x. Every cartridge: embedded data layout, calibration and controller replay. Five affected charts: Mesen committed video-memory checks. No physical hardware tests.')
    print('PASS: exact-build release gates and unchanged PCM',flush=True)
    if a.check_only:return
    copy(ROOT/'README.md',DIST/'README.md')
    copy(ROOT/'README.md',DIST/'README.txt')
    for source,name in [(v/'calibration-presentation/capture.png','calibration.png'),(v/'checkpoints-31/death.png','checkpoint-death.png'),(v/'checkpoints-31/retry.png','checkpoint-retry.png'),(v/'checkpoints-31/clear.png','results.png'),(ROOT/'build/packs/sa1-safe-collab-02/verification/performance-31/frame-120.png','preview.png'),(ROOT/'build/packs/sa1-safe-collab-02/verification/performance-31/motion.gif','preview.gif')]:copy(source,DIST/name)
    master=DIST/'adofai-msu-master';master.mkdir(exist_ok=True)
    for r in files:
        if not (master/r['file']).exists() or sha(master/r['file'])!=r['sha256']:copy(BASE/r['file'],master/r['file'])
    (master/'verification.json').write_text(json.dumps(report,indent=2));(master/'README.txt').write_text(NOTE)
    (master/'SHA256SUMS.txt').write_text(''.join(r['sha256']+'  '+r['file']+'\n' for r in files))
    names=('adofai.sfc','adofai.msu','verification.json','README.txt','SHA256SUMS.txt')
    update=DIST/'adofai-sa1-update';update.mkdir(exist_ok=True)
    for name in names:copy(master/name,update/name)
    (update/'SHA256SUMS.txt').write_text(current['rom_sha256']+'  adofai.sfc\n'+current['msu_sha256']+'  adofai.msu\n')
    archive(DIST/'adofai-update.zip',[(update/n,n) for n in names])
    for name in ('sa1','graphics','color','readability','native-scale','calibration-hotfix'):
        target='adofai-'+name+('-update' if name not in ('calibration-hotfix',) else '')
        copy(DIST/'adofai-update.zip',DIST/(target+'.zip'))
    for folder in ('adofai-graphics-update','adofai-color-update','adofai-readability-update'):
        for name in names:copy(update/name,DIST/folder/name)
    stand=DIST/'adofai-standalone';previous=read(stand/'catalog.json');rom_files=[]
    for row in catalog['roms']:
        target=stand/row['file'];copy(ROOT/'build/packs'/row['key']/'adofai.sfc',target)
        rom_files.append((target,row['file']))
        archive(target.with_suffix('.zip'),[(target,row['file'])],NOTE+'\nSongs: '+', '.join(row['codes'])+'\n')
    legacy=DIST/'legacy-standalone';legacy.mkdir(exist_ok=True)
    for name in {r['file'] for r in previous['roms']}-{r['file'] for r in catalog['roms']}:
        for p in (stand/name,(stand/name).with_suffix('.zip')):
            assert p.resolve().is_relative_to(stand.resolve()) and legacy.resolve().is_relative_to(DIST.resolve())
            if p.exists():p.replace(legacy/(p.stem+'-pre-dataset14'+p.suffix))
    for name,data in (('catalog.json',catalog),('verification.json',standalone)):(stand/name).write_text(json.dumps(data,indent=2))
    (stand/'README.txt').write_text(NOTE);(stand/'SHA256SUMS.txt').write_text(''.join(r['rom_sha256']+'  '+r['file']+'\n' for r in catalog['roms']))
    archive(DIST/'adofai-standalone-roms.zip',rom_files+[(stand/n,n) for n in ('README.txt','catalog.json','verification.json','SHA256SUMS.txt')])
    copy(DIST/'adofai-standalone-roms.zip',DIST/'adofai-official-worlds.zip')
    archive(DIST/'adofai-main-worlds.zip',[(stand/r['file'],r['file']) for r in catalog['roms'] if '-main-' in r['key']],NOTE)
    copy(demo/'adofai.sfc',DIST/'adofai-level1-demo.sfc')
    archive(DIST/'adofai-level1-demo.zip',[(DIST/'adofai-level1-demo.sfc','adofai-level1-demo.sfc')],NOTE)
    copy(DIST/'adofai-level1-demo.zip',DIST/'ADOFAI (SNES).zip')
    archive(DIST/'adofai-msu-master.zip',[(master/r['file'],r['file']) for r in files]+[(master/n,n) for n in ('README.txt','verification.json','SHA256SUMS.txt')])
    import zipfile,hashlib
    audits=[]
    pairs=[(DIST/'adofai-update.zip',{'adofai.sfc':current['rom_sha256'],'adofai.msu':current['msu_sha256']}),
        (DIST/'adofai-msu-master.zip',{r['file']:r['sha256'] for r in files}),
        (DIST/'adofai-standalone-roms.zip',{r['file']:r['rom_sha256'] for r in catalog['roms']})]
    pairs += [(stand/Path(r['file']).with_suffix('.zip'),{r['file']:r['rom_sha256']}) for r in catalog['roms']]
    for path,expected in pairs:
        with zipfile.ZipFile(path) as z:
            assert len(z.namelist())==len(set(z.namelist()))
            for name,digest in expected.items():
                with z.open(name) as f:assert hashlib.file_digest(f,'sha256').hexdigest()==digest,(path,name)
        audits.append(str(path))
    (ROOT/'build/final-release.json').write_text(json.dumps(dict(passed=True,**current,master_checks=183,standalone_checks=122,cartridges=len(catalog['roms']),audited_archives=audits),indent=2))
    print('PASS: published archives match the verified artifacts',flush=True)

if __name__=='__main__':main()
