"""Publish SA-1 artifacts only after checks bound to their exact hashes pass."""
import argparse,hashlib,json,zipfile
from pathlib import Path
from package_graphics_update import read,sha,copy,bound,graphics
from package_standalone import archive
from verification_data import identity
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'build/packs/sa1-release'
DIST=ROOT/'dist'
SELECTED=[1,12,22,26,31,39,41,45,46,50,53,60,61]
NOTE='''ADOFAI SNES - SA-1 and Mode 7 camera rotation

Use an emulator supporting SA-1 (and MSU-1 for the master).
Existing master users: close the game and replace BOTH adofai.sfc and
adofai.msu. Keep all 269 PCM files unchanged. Dataset 13 is required.
Standalone cartridges include BRR music and need no external files.

Authored camera rotation includes easing, full turns and checkpoint
restoration. Planets, symbols and trails follow the same rotation.
SA-1 prepares the track cache and projects sprites. Zoom remains removed;
authored camera panning, individual tile rotation and shader effects are
not implemented. Dense scenes can still drop visual frames. This is not
a guaranteed 60-FPS release. Physical hardware has not been tested.

Original tile visibility and movement remain. Recessed joins separate
pieces; accepted hits brighten their tile. No invented double-hit icons.
Calibration retains its immediate 120-BPM click, continuous orbit,
16 taps and -30..+30 adjustment (zero equals the former +8).

See verification.json for exact current test scope and artifact hashes.
'''

def audit_archives():
    catalog=read(ROOT/'build/sa1-standalone-catalog.json');current=identity(BASE/'adofai.sfc')
    master={'adofai.sfc':current['rom_sha256'],'adofai.msu':current['msu_sha256']}
    checks=[(DIST/'adofai-update.zip',master),(DIST/'adofai-sa1-update.zip',master),(DIST/'adofai-msu-master.zip',master),
            (DIST/'adofai-standalone-roms.zip',{r['file']:r['rom_sha256'] for r in catalog['roms']}),
            (DIST/'adofai-level1-demo.zip',{'adofai-level1-demo.sfc':sha(ROOT/'build/packs/sa1-demo/adofai.sfc')})]
    checks += [(DIST/'adofai-standalone'/Path(r['file']).with_suffix('.zip'),{r['file']:r['rom_sha256']}) for r in catalog['roms']]
    rows=[]
    for path,expected in checks:
        with zipfile.ZipFile(path) as z:
            assert len(z.namelist())==len(set(z.namelist())),('Duplicate archive entries',path)
            for name,digest in expected.items():assert hashlib.sha256(z.read(name)).hexdigest()==digest,(path,name)
            if path.name=='adofai-msu-master.zip':
                files=read(DIST/'adofai-msu-master/verification.json')['files']
                assert sum(n.endswith('.pcm') for n in z.namelist())==269
                assert all(z.getinfo(r['file']).file_size==r['bytes'] for r in files)
        rows.append(dict(file=path.name,bytes=path.stat().st_size,checked_artifacts=list(expected)))
    (ROOT/'build/sa1-archive-audit.json').write_text(json.dumps(dict(passed=True,**current,archives=rows),indent=2))
    print('PASS: download archives contain the exact verified ROM/MSU bytes',flush=True)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--check-only',action='store_true');args=ap.parse_args()
    current=identity(BASE/'adofai.sfc');v=BASE/'verification'
    with (BASE/'adofai.msu').open('rb') as f:assert f.read(14)==b'ADOFAI-MSU1\0\x0d\0'
    pixels=graphics('sa1-release',[1,1.3,2]);assert len(pixels)==183
    checks={name:bound(v/(name+'.json'),current) for name in ('sa1-layout','authored-visibility','calibration','calibration-mesen','hit-lighting','tap-sounds','msu-version')}
    assert len(checks['authored-visibility']['worlds'])==61
    unit=bound(ROOT/'build/sa1-release-unit-tests.json',current);assert unit['tests']>=93
    regression=bound(ROOT/'build/sa1-release-verification-controller-audio-mesen-checkpoints-mesen-checkpoints.json',current)
    assert [r['level'] for r in regression['results']]==SELECTED and all(r.get('passed') for r in regression['results'])
    menu=bound(v/'menu-pages/result.json',current);assert menu['songs']==61
    profiles={str(n):bound(v/f'presentation-{n}/result.json',current) for n in (31,46,53)}
    trails=bound(v/'orbit-trails-53/result.json',current);assert trails['detached_components']==0 and trails['checked_components']>8000
    catalog=read(ROOT/'build/sa1-standalone-catalog.json');stand_pixels=[];layouts=[]
    assert sorted(n for r in catalog['roms'] for n in r['levels'])==list(range(1,62))
    for row in catalog['roms']:
        base=ROOT/'build/packs'/row['key'];expected=dict(rom_sha256=row['rom_sha256'],msu_sha256=None)
        assert identity(base/'adofai.sfc')==expected
        layouts.append(bound(base/'verification/sa1-layout.json',expected))
        stand_pixels.extend(graphics(row['key'],[1,2]))
    assert len(stand_pixels)==122
    stand_mesen=[]
    for key,folder in [('sa1-standalone-main-01','mesen-7'),('sa1-standalone-tech-07','mesen-checkpoints-2')]:
        base=ROOT/'build/packs'/key
        stand_mesen.append(bound(base/'verification'/folder/'manifest.json',identity(base/'adofai.sfc')))
        assert (base/'verification'/folder/'result.txt').read_text().endswith('PASS\n')
    calibration=read(ROOT/'build/sa1-calibration-standalone-verification.json')
    assert calibration['passed'] and {r['key']:r['rom_sha256'] for r in calibration['cartridges']}=={r['key']:r['rom_sha256'] for r in catalog['roms']}
    demo=ROOT/'build/packs/sa1-demo';demo_checks=graphics('sa1-demo',[1,1.3,2]);assert len(demo_checks)==3
    prior=read(ROOT/'build/feedback-release-baseline/master-verification.json')
    files=[]
    for old in prior['files']:
        p=BASE/old['file'];digest=sha(p)
        if p.suffix=='.pcm':assert digest==old['sha256'],('PCM changed',p.name)
        files.append(dict(file=p.name,sha256=digest,bytes=p.stat().st_size))
    assert sum(r['file'].endswith('.pcm') for r in files)==269
    report=dict(verified=True,**current,world_count=61,official_tech_count=22,dataset_version=13,
        verification_scope='All 61 charts at 1.0x, 1.3x and 2.0x: every displayed PPU frame. Selected 13 charts: controller, waveform audio, Snes9x and Mesen checkpoint retries. Calibration in both emulators. All standalone charts at 1.0x and 2.0x; calibration and a controller replay in every cartridge. No physical hardware testing.',
        hardware_tested=False,files=files,unchanged_pcm=True,ppu_replays=pixels,checks=checks,
        unit_tests=unit,controller_and_checkpoint_checks=regression,menu=menu,presentation=profiles,rotated_trails=trails)
    standalone=dict(verified=True,external_files_required=False,roms=catalog['roms'],ppu_replays=stand_pixels,
        layouts=layouts,calibration_checks=calibration,mesen_banking_and_rotation=stand_mesen,hardware_tested=False,
        verification_scope='All 61 charts at 1.0x/2.0x, every displayed PPU frame; embedded payload bytes and banking; calibration and one controller replay per cartridge in Snes9x. Mesen: standalone 7-X complete song and FT14-X checkpoint retries.')
    print('PASS: SA-1 release gates and unchanged PCM hashes',flush=True)
    if args.check_only:return
    master=DIST/'adofai-msu-master';master.mkdir(exist_ok=True,parents=True)
    for r in files:
        target=master/r['file']
        if not target.exists() or sha(target)!=r['sha256']:copy(BASE/r['file'],target)
    (master/'verification.json').write_text(json.dumps(report,indent=2))
    (master/'README.txt').write_text(NOTE)
    (master/'SHA256SUMS.txt').write_text(''.join(r['sha256']+'  '+r['file']+'\n' for r in files))
    update=DIST/'adofai-sa1-update';update.mkdir(exist_ok=True)
    for name in ('adofai.sfc','adofai.msu','verification.json','README.txt'):copy(master/name,update/name)
    (update/'SHA256SUMS.txt').write_text(current['rom_sha256']+'  adofai.sfc\n'+current['msu_sha256']+'  adofai.msu\n')
    names=('adofai.sfc','adofai.msu','verification.json','README.txt','SHA256SUMS.txt')
    archive(DIST/'adofai-update.zip',[(update/name,name) for name in names])
    copy(DIST/'adofai-update.zip',DIST/'adofai-sa1-update.zip')
    for folder in ('adofai-graphics-update','adofai-color-update','adofai-readability-update'):
        for name in names:copy(update/name,DIST/folder/name)
    for name in ('adofai-graphics-update.zip','adofai-color-update.zip','adofai-readability-update.zip','adofai-native-scale-update.zip','adofai-calibration-hotfix.zip'):
        copy(DIST/'adofai-update.zip',DIST/name)
    stand=DIST/'adofai-standalone';stand.mkdir(exist_ok=True);rom_files=[]
    previous=read(stand/'catalog.json') if (stand/'catalog.json').exists() else dict(roms=[])
    for row in catalog['roms']:
        target=stand/row['file'];copy(ROOT/'build/packs'/row['key']/'adofai.sfc',target)
        assert sha(target)==row['rom_sha256'];rom_files.append((target,row['file']))
        archive(target.with_suffix('.zip'),[(target,row['file'])],NOTE+'\nSongs: '+', '.join(row['codes'])+'\n')
    legacy=DIST/'legacy-standalone';legacy.mkdir(exist_ok=True)
    for name in {r['file'] for r in previous['roms']}-{r['file'] for r in catalog['roms']}:
        for p in (stand/name,(stand/name).with_suffix('.zip')):
            assert p.resolve().is_relative_to(stand.resolve())
            if p.exists():p.replace(legacy/(p.stem+'-pre-sa1'+p.suffix))
    for name,data in (('catalog.json',catalog),('verification.json',standalone)):(stand/name).write_text(json.dumps(data,indent=2))
    (stand/'README.txt').write_text(NOTE)
    (stand/'SHA256SUMS.txt').write_text(''.join(r['rom_sha256']+'  '+r['file']+'\n' for r in catalog['roms']))
    archive(DIST/'adofai-standalone-roms.zip',rom_files+[(stand/n,n) for n in ('README.txt','catalog.json','verification.json','SHA256SUMS.txt')])
    copy(DIST/'adofai-standalone-roms.zip',DIST/'adofai-official-worlds.zip')
    archive(DIST/'adofai-main-worlds.zip',[(stand/r['file'],r['file']) for r in catalog['roms'] if r['key'].startswith('sa1-standalone-main-')],NOTE)
    copy(demo/'adofai.sfc',DIST/'adofai-level1-demo.sfc')
    archive(DIST/'adofai-level1-demo.zip',[(DIST/'adofai-level1-demo.sfc','adofai-level1-demo.sfc')],NOTE)
    copy(DIST/'adofai-level1-demo.zip',DIST/'ADOFAI (SNES).zip')
    copy(ROOT/'README.md',DIST/'README.txt')
    for source,name in [('presentation-31/frame-120.png','preview.png'),('presentation-31/motion.gif','preview.gif'),('presentation-53/frame-120.png','rotation-preview.png'),('calibration-presentation/capture.png','calibration.png')]:
        copy(v/source,DIST/name)
    print('Published master update and 22 standalone cartridges; writing full PCM archive',flush=True)
    archive(DIST/'adofai-msu-master.zip',[(master/r['file'],r['file']) for r in files]+[(master/n,n) for n in ('README.txt','verification.json','SHA256SUMS.txt')])
    audit_archives()
    (ROOT/'build/sa1-release.json').write_text(json.dumps(dict(passed=True,**current,master_checks=len(pixels),standalone_checks=len(stand_pixels),cartridges=len(catalog['roms']),unchanged_pcm=True),indent=2))
    print('PASS: packaged archives CRC checked; SA-1 release published',flush=True)

if __name__=='__main__':main()
