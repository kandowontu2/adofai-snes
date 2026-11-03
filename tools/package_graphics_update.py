"""Publish the authored-visibility release with explicitly scoped evidence."""
import argparse,hashlib,json,shutil,zipfile
from pathlib import Path
from package_standalone import archive
from verification_data import identity
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'build/packs/master';DIST=ROOT/'dist'
PRIOR=ROOT/'build/feedback-release-baseline'
SELECTED=[1,11,22,23,26,31,39,41,44,45,46,50,53,60,61]

def read(p):return json.loads(p.read_text())
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def copy(source,target):
    target.parent.mkdir(parents=True,exist_ok=True)
    temporary=target.with_name(target.name+'.new');shutil.copyfile(source,temporary);temporary.replace(target)
def bound(p,current):
    r=read(p);assert all(r.get(k)==v for k,v in current.items()),('Stale evidence',str(p))
    assert r.get('passed',True),('Failed evidence',str(p));return r

def graphics(pack,speeds):
    base=ROOT/'build/packs'/pack;current=identity(base/'adofai.sfc');rows=[]
    for n in read(base/'pack.json')['levels']:
        for speed in speeds:
            suffix='' if speed==1 else f'-speed-{round(speed*10)}'
            r=bound(base/f'verification/render-{n}{suffix}.json',current)
            assert r['completed_song'] and r['every_frame'] and r['ppu_chr_match']
            assert r['vblank_overruns']==r['cache_capacity_errors']==0
            assert r['max_objects_per_line']<=17 and not r['tile_flashes']
            assert r['final_state']==3 and r['combo']==r['expected_hits']
            rows.append(r)
    return rows

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--check-only',action='store_true');args=ap.parse_args()
    current=identity(BASE/'adofai.sfc');v=BASE/'verification'
    with (BASE/'adofai.msu').open('rb') as f:assert f.read(14)==b'ADOFAI-MSU1\0\x0c\0'
    pixels=graphics('master',[1,1.3,2]);assert len(pixels)==183
    visibility=bound(v/'authored-visibility.json',current);assert len(visibility['worlds'])==61
    unit=bound(ROOT/'build/latest-unit-tests.json',current);assert unit['tests']>=85
    unit_log=(ROOT/'build/latest-unit-tests.log').read_text();assert f'Ran {unit["tests"]} tests' in unit_log and '\nOK\n' in unit_log
    regression=bound(ROOT/'build/master-verification-controller-audio-mesen-checkpoints-mesen-checkpoints.json',current)
    assert [r['level'] for r in regression['results']]==SELECTED and all(r.get('passed') for r in regression['results'])
    checks={name:bound(v/(name+'.json'),current) for name in ('calibration','calibration-mesen','tap-sounds','msu-version','hit-lighting')}
    assert len(checks['calibration']['metronome'])==14 and len(checks['calibration']['entry_sounds'])==5
    speeds=bound(ROOT/'build/master-speed-verification/result.json',current)
    assert [r['speed'] for r in speeds['speeds']]==[n/10 for n in range(5,21)]
    assert all(r['minimum_correlation']>.9 and abs(r['drift_ms'])<20 for r in speeds['speeds'])
    menu=bound(v/'menu-pages/result.json',current);assert menu['songs']==61 and menu['checked_published_pixels']
    presentation={str(n):bound(v/f'presentation-{n}/result.json',current) for n in (31,46)}
    stress=[]
    for name in ('speed20-41','speed20-61','speed05-35','speed20-53','speed20-60','speed13-31','speed20-31'):
        r=bound(v/name/'result.json',current);a=bound(v/name/'audio-check.json',current)
        assert r['final']['state']==3 and r['final']['misses']==r['final']['tap_overruns']==r['final']['pattern_vblank_overruns']==0
        assert min(w['correlation'] for w in a['windows'])>.9 and abs(a['drift_ms'])<20
        stress.append(dict(code=r['code'],speed=r['speed_tenths']/10,combo=r['final']['combo'],audio=a))
    deaths=[bound(v/name/'result.json',current) for name in ('death-presentation-11-10','death-presentation-41-20','death-presentation-30-10')]
    assert all(r['retains_completed_scene'] and r['frozen_frames']==90 for r in deaths)
    catalog=read(ROOT/'build/standalone-catalog.json');stand_pixels=[]
    for row in catalog['roms']:
        assert identity(ROOT/'build/packs'/row['key']/'adofai.sfc')==dict(rom_sha256=row['rom_sha256'],msu_sha256=None)
        stand_pixels.extend(graphics(row['key'],[1,2]))
    assert len(stand_pixels)==122 and sorted(n for r in catalog['roms'] for n in r['levels'])==list(range(1,62))
    stand_cal=read(ROOT/'build/calibration-standalone-verification.json')
    assert stand_cal['passed'] and {r['key']:r['rom_sha256'] for r in stand_cal['cartridges']}=={r['key']:r['rom_sha256'] for r in catalog['roms']}
    first=catalog['roms'][0];stand_mesen=bound(ROOT/'build/packs'/first['key']/'verification/calibration-mesen.json',dict(rom_sha256=first['rom_sha256'],msu_sha256=None))
    demo=ROOT/'build/packs/standalone-demo'
    assert len(graphics('standalone-demo',[1,1.3,2]))==3
    old=read(PRIOR/'master-verification.json');assert old['verified']
    files=[dict(r) for r in old['files']]
    for r in files:
        p=BASE/r['file'];actual=sha(p)
        if p.suffix=='.pcm':assert actual==r['sha256'],('PCM changed',p.name)
        r.update(sha256=actual,bytes=p.stat().st_size)
    print('PASS: current graphics, gameplay, audio, calibration, standalone and unchanged PCM gates',flush=True)
    if args.check_only:return
    scope='Current: all 61 charts at 1.0x/1.3x/2.0x with every displayed PPU frame checked; selected 15 charts with real-controller, audio, Mesen and checkpoint retries; all 16 speeds on the first song; calibration and stress checks. Prior full campaign reports retain their original hashes.'
    verification=dict(verified=True,verification_scope=scope,**current,world_count=61,official_tech_count=22,
        files=files,total_bytes=sum(r['bytes'] for r in files),unchanged_pcm=True,hardware_tested=False,
        authored_visibility=visibility,ppu_replays=pixels,regression_tests=unit['tests'],unit_tests=unit,
        controller_and_checkpoint_checks=regression,calibration_checks=checks,speed_settings=speeds,
        stress_checks=stress,death_checks=deaths,menu=menu,presentation=presentation,prior_release=old)
    text='''ADOFAI SNES - authored visibility, camera and graphics update

Close the game and replace BOTH adofai.sfc and adofai.msu. Keep all 269
PCM files unchanged. Dataset version 12 rejects older MSU files.

Original appearance/disappearance, opacity and tile ordering replace the
invented reveal window. Full silhouettes are shared by master/standalone.
The camera follows the occupied route without its previous look-ahead.
The invented double-hit diamonds are removed. Recessed joins separate
adjacent pieces. Accepted hits brighten their tile using authored glow
strength; this approximates the original glow with palette brightness.
Landing crosses, rings and bursts remain removed.

A versioned PPU cache protects displayed graphics at faster speeds. Music
and input timing continue while an intact frame is held. Dense charts can
still drop visual frames. The busiest charts merge colors; FT11 also
shares outer contours. Camera zoom, authored camera rotation, scenery and
shader bloom are not reproduced. Camera rotation is feasible but is not
implemented in this build. Music quality is unchanged.

Calibration keeps the immediate click, original 120-BPM cadence, continuous
orbit and 16 taps. Displayed zero equals the former +8; range is -30..+30.

See verification.json for current checks and their precise scope. Earlier
complete campaign evidence keeps its original hashes under prior_release.
Physical hardware has not been tested.
'''
    out=DIST/'adofai-msu-master';out.mkdir(exist_ok=True)
    for name in ('adofai.sfc','adofai.msu'):copy(BASE/name,out/name)
    for r in files:
        if r['file'].endswith('.pcm'):
            p=out/r['file']
            if not p.exists() or sha(p)!=r['sha256']:copy(BASE/r['file'],p)
    copy(ROOT/'README.md',out/'README.txt')
    (out/'verification.json').write_text(json.dumps(verification,indent=2))
    (out/'SHA256SUMS.txt').write_text(''.join(r['sha256']+'  '+r['file']+'\n' for r in files))
    update=DIST/'adofai-graphics-update';update.mkdir(exist_ok=True)
    for name in ('adofai.sfc','adofai.msu','verification.json'):copy(out/name,update/name)
    (update/'README.txt').write_text(text)
    (update/'SHA256SUMS.txt').write_text(current['rom_sha256']+'  adofai.sfc\n'+current['msu_sha256']+'  adofai.msu\n')
    archive(DIST/'adofai-update.zip',[(update/name,name) for name in ('adofai.sfc','adofai.msu','verification.json','SHA256SUMS.txt','README.txt')])
    print('Published verified master ROM/MSU update',flush=True)
    for folder in ('adofai-color-update','adofai-readability-update'):
        for name in ('adofai.sfc','adofai.msu','verification.json','SHA256SUMS.txt','README.txt'):copy(update/name,DIST/folder/name)
    for name in ('adofai-graphics-update.zip','adofai-color-update.zip','adofai-readability-update.zip','adofai-native-scale-update.zip','adofai-calibration-hotfix.zip'):
        copy(DIST/'adofai-update.zip',DIST/name)
    stand=DIST/'adofai-standalone';stand.mkdir(exist_ok=True);rom_files=[];sums=''
    stand_note='ADOFAI SNES - self-contained cartridges\n\nEach ROM contains its own 12-kHz BRR music and animation. No external\nMSU or PCM files are required. All use the current engine, full silhouettes\nand authored visibility. See catalog.json for songs in each numbered part.\n\n'+text[text.index('Original appearance'):]
    stand_report=dict(verified=True,verification_scope='Current: every chart at 1.0x/2.0x with every displayed frame checked; calibration and one full controller replay per cartridge; Mesen calibration in the shared first cartridge. Prior complete campaign evidence retains its original hashes.',external_files_required=False,
                      roms=catalog['roms'],ppu_replays=stand_pixels,calibration_checks=stand_cal,mesen_calibration=stand_mesen,prior_release=read(PRIOR/'standalone-verification.json'))
    for row in catalog['roms']:
        target=stand/row['file'];copy(ROOT/'build/packs'/row['key']/'adofai.sfc',target)
        assert sha(target)==row['rom_sha256'];sums+=row['rom_sha256']+'  '+row['file']+'\n';rom_files.append((target,row['file']))
        archive(target.with_suffix('.zip'),[(target,row['file'])],stand_note+'\nSHA256: '+row['rom_sha256']+'\n')
    previous=read(PRIOR/'standalone-catalog.json')
    retired={r['file'] for r in previous['roms']}-{r['file'] for r in catalog['roms']}
    legacy=DIST/'legacy-standalone';legacy.mkdir(exist_ok=True)
    for name in retired:
        for file in (stand/name,(stand/name).with_suffix('.zip')):
            assert file.resolve().is_relative_to(stand.resolve())
            if file.exists():file.replace(legacy/(file.stem+'-pre-graphics'+file.suffix))
    for name,data in (('catalog.json',catalog),('verification.json',stand_report)):(stand/name).write_text(json.dumps(data,indent=2))
    (stand/'README.txt').write_text(stand_note);(stand/'SHA256SUMS.txt').write_text(sums)
    extra=[(stand/name,name) for name in ('README.txt','catalog.json','verification.json','SHA256SUMS.txt')]
    archive(DIST/'adofai-standalone-roms.zip',rom_files+extra)
    copy(DIST/'adofai-standalone-roms.zip',DIST/'adofai-official-worlds.zip')
    archive(DIST/'adofai-main-worlds.zip',[(stand/r['file'],r['file']) for r in catalog['roms'] if r['key'].startswith('standalone-main-')],stand_note)
    print('Published',len(catalog['roms']),'standalone cartridges and collection ZIPs',flush=True)
    copy(ROOT/'README.md',DIST/'README.txt')
    for source,name in ((v/'presentation-31/frame-120.png','preview.png'),(v/'presentation-31/motion.gif','preview.gif'),
                        (v/'calibration-presentation/capture.png','calibration.png'),(v/'death-presentation-11-10/frozen.png','checkpoint-death.png')):
        copy(source,DIST/name)
    copy(demo/'adofai.sfc',DIST/'adofai-level1-demo.sfc')
    archive(DIST/'adofai-level1-demo.zip',[(DIST/'adofai-level1-demo.sfc','adofai-level1-demo.sfc')],stand_note)
    copy(DIST/'adofai-level1-demo.zip',DIST/'ADOFAI (SNES).zip')
    full=[(out/r['file'],r['file']) for r in files]+[(out/name,name) for name in ('README.txt','verification.json','SHA256SUMS.txt')]
    print('Writing and CRC-checking full master archive',flush=True)
    archive(DIST/'adofai-msu-master.zip',full)
    report=dict(passed=True,**current,standalone_cartridges=len(catalog['roms']),master_ppu_replays=183,standalone_ppu_replays=122,
                selected_controller_worlds=SELECTED,regression_tests=unit['tests'],unchanged_pcm=True)
    (ROOT/'build/graphics-release.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report),flush=True)
    print('Master, standalone and all update ZIPs passed CRC and tested-ROM hash checks',flush=True)

if __name__=='__main__':main()
