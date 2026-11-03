"""Publish the validated adaptive Mode 7 renderer and scoped zoom charts."""
import hashlib,json,zipfile
from pathlib import Path
from package_graphics_update import read,sha,copy,bound,graphics
from package_standalone import archive
from verification_data import identity

ROOT=Path(__file__).resolve().parents[1]
DIST=ROOT/'dist'
BASE=ROOT/'build/packs/sa1-renderer-release-master'
NOTE='''ADOFAI SNES - adaptive Mode 7 renderer

Rewritten texture staging and temporal resolution switching for wider views.
Authored zoom enabled in XN-X, XS-X, AR-X, FT07-X.
The other charts retain fixed zoom; their renderer is updated.
Mad Piano Party II uses half-resolution textures and fixed zoom; dense
transitions can still stutter.
AR-X non-sticking floors now retain their authored initial planet positions.
Trails and small planet sprites follow zoom. Checkpoints restore raster scale.
Manual percussion commands no longer wait for the main rendering loop.

65 charts in the master. 64 charts in 32 self-contained standalone cartridges.
OOPARTS Nerfed has a separate single-song MSU package: its animation exceeds
the 8 MiB standalone cartridge limit. The complete chart is retained.
Mad Piano Party is FT11-X, in standalone Tech 08.
Added Mad Piano Party II (NumbEr07 & LUMI), Feral Easy and Medium,
and OOPARTS Nerfed (Lupel_2, original by Nephrolepis).
Master: replace BOTH adofai.sfc and adofai.msu (dataset 20).
Keep all 269 existing PCM files and add the 16 included new PCM files.
Existing music encodings and quality are unchanged.

Measured frame rates and exact build hashes are in verification.json.
Dense scenes still fall below 60 FPS. Camera panning is playfield-constrained;
planet sprite sizes are discrete. Extreme zoom charts are not enabled yet.
See verification.json for exact-build checks. No physical hardware testing.
'''

def main():
    current=identity(BASE/'adofai.sfc')
    cat=read(ROOT/'build/sa1-renderer-release-standalone-catalog.json')
    assert len(cat['roms'])==32 and sorted(n for r in cat['roms'] for n in r['levels'])==list(range(1,65))
    calibration=read(ROOT/'build/renderer-standalone-calibration.json')
    added_calibration=read(ROOT/'build/renderer-release-added-calibration.json')
    assert added_calibration['passed']
    calibration['cartridges']+=added_calibration['cartridges']
    assert calibration['passed']
    assert {r['key']:r['rom_sha256'] for r in calibration['cartridges']}=={r['key']:r['rom_sha256'] for r in cat['roms']}
    master_pixels=graphics(BASE.name,[1,2]);standalone_pixels=[];layouts=[]
    for row in cat['roms']:
        base=ROOT/'build/packs'/row['key'];evidence=identity(base/'adofai.sfc')
        assert row['rom_sha256']==evidence['rom_sha256']
        standalone_pixels+=graphics(row['key'],[1,2])
        layouts.append(bound(base/'verification/sa1-layout.json',evidence))
    assert len(master_pixels)==130 and len(standalone_pixels)==128
    for n in (20,22,23,46):
        r=bound(BASE/f'verification/render-{n}-speed-13.json',current)
        assert r['completed_song'] and r['every_frame'] and r['ppu_chr_match'] and not r['tile_flashes']
        assert r['vblank_overruns']==r['cache_capacity_errors']==0
        master_pixels.append(r)
    bound(BASE/'verification/msu-version.json',current)
    layouts.append(bound(BASE/'verification/sa1-layout.json',current))
    with (BASE/'adofai.msu').open('rb') as f:assert f.read(14)==b'ADOFAI-MSU1\0\x14\0'
    checkpoint_checks=[]
    for n in (20,22,23,46,63,64):
        folder=BASE/f'verification/mesen-checkpoints-{n}'
        assert (folder/'result.txt').read_text().endswith('PASS\n')
        checkpoint_checks.append(bound(folder/'ppu-verification.json',current))
    for row in cat['roms']:
        base=ROOT/'build/packs'/row['key'];evidence=identity(base/'adofai.sfc')
        for local,n in enumerate(row['levels'],1):
            if n in (20,22,23,46,63,64):
                folder=base/f'verification/mesen-checkpoints-{local}'
                assert (folder/'result.txt').read_text().endswith('PASS\n')
                checkpoint_checks.append(bound(folder/'ppu-verification.json',evidence))
            if n in (62,63,64):
                report=bound(base/f'verification/render-{n}-speed-13.json',evidence)
                assert report['completed_song'] and report['every_frame'] and report['ppu_chr_match']
                assert not report['tile_flashes'] and report['vblank_overruns']==report['cache_capacity_errors']==0
                standalone_pixels.append(report)
    manual=bound(BASE/'verification/manual-feedback-25-10.json',current)
    assert manual['taps']==401 and manual['max_delay_frames']==0
    crown=ROOT/'build/packs/sa1-renderer-crown-01'
    standalone_manual=bound(crown/'verification/manual-feedback-2-10.json',identity(crown/'adofai.sfc'))
    assert standalone_manual['max_delay_frames']<=1
    master_calibration=bound(BASE/'verification/calibration.json',current)
    demo=ROOT/'build/packs/sa1-renderer-demo';demo_id=identity(demo/'adofai.sfc')
    demo_pixels=graphics(demo.name,[1,2]);demo_calibration=bound(demo/'verification/calibration.json',demo_id)
    log=(ROOT/'build/renderer-release-units.log').read_text()
    assert 'Ran 125 tests' in log and '\nOK\n' in log
    profiles=[bound(ROOT/f'build/renderer-release-profile-{name}/result.json',current) for name in ('xs','ar','turkish','mpp2')]
    arrays=bound(BASE/'verification/large-arrays.json',current)
    menu=bound(BASE/'verification/menu-pages/result.json',current);assert menu['songs']==65
    omega=ROOT/'build/packs/sa1-renderer-omega-msu';omega_id=identity(omega/'adofai.sfc')
    omega_report=dict(verified=True,**omega_id,world_count=1,external_files_required=True,
                      ppu_replays=graphics(omega.name,[1,2]),calibration=bound(omega/'verification/calibration.json',omega_id),
                      arrays=bound(omega/'verification/large-arrays.json',omega_id),
                      mesen=bound(omega/'verification/mesen-1/ppu-verification.json',omega_id),
                      performance=bound(ROOT/'build/renderer-omega-profile/result.json',omega_id))
    assert (omega/'verification/mesen-1/result.txt').read_text().endswith('PASS\n')
    prior=ROOT/'build/packs/sa1-options-master'
    for n in range(1,62):assert sha(BASE/f'level{n}.brr')==sha(prior/f'level{n}.brr')
    baseline=ROOT/'build/renderer-previous-release.json'
    if not baseline.exists():copy(DIST/'adofai-msu-master/verification.json',baseline)
    old=read(baseline);files=[]
    for row in old['files']:
        p=BASE/row['file'];digest=sha(p)
        if p.suffix=='.pcm':assert digest==row['sha256']
        files.append(dict(file=p.name,sha256=digest,bytes=p.stat().st_size))
    assert sum(r['file'].endswith('.pcm') for r in files)==269
    existing={r['file'] for r in files};new_pcm=sorted(p.name for p in BASE.glob('adofai-*.pcm') if p.name not in existing)
    assert len(new_pcm)==16
    files += [dict(file=name,sha256=sha(BASE/name),bytes=(BASE/name).stat().st_size) for name in new_pcm]
    common=dict(verified=True,hardware_tested=False,unit_tests=dict(passed=True,tests=125),
                zoom_enabled_levels=[20,22,23,46],fixed_zoom_levels=[n for n in range(1,66) if n not in (20,22,23,46)],
                limitations=['Dense animation is not consistently 60 FPS','Camera panning remains playfield-constrained','Discrete planet sprite sizes','Extreme zoom values not enabled'],
                checkpoint_checks=checkpoint_checks,manual_feedback=manual,standalone_manual_feedback=standalone_manual,
                performance_profiles=profiles,demo_checks=dict(**demo_id,ppu_replays=demo_pixels,calibration=demo_calibration),layouts=layouts)
    stand_report=dict(**common,cartridges=cat['roms'],calibration=calibration,ppu_replays=standalone_pixels)
    master_report=dict(**common,**current,dataset_version=20,world_count=65,files=files,existing_pcm_unchanged=True,new_pcm=new_pcm,ppu_replays=master_pixels,calibration=master_calibration,arrays=arrays,menu=menu)
    print('PASS: exact-build renderer release gates',flush=True)
    stand=DIST/'adofai-standalone';rom_files=[]
    for r in cat['roms']:
        target=stand/r['file'];copy(ROOT/'build/packs'/r['key']/'adofai.sfc',target);rom_files.append((target,r['file']))
        archive(target.with_suffix('.zip'),[(target,r['file'])],NOTE+'\nSongs: '+', '.join(r['codes'])+'\n')
    for name,value in [('catalog.json',cat),('verification.json',stand_report)]: (stand/name).write_text(json.dumps(value,indent=2))
    (stand/'README.txt').write_text(NOTE)
    (stand/'SHA256SUMS.txt').write_text(''.join(r['rom_sha256']+'  '+r['file']+'\n' for r in cat['roms']))
    archive(DIST/'adofai-standalone-roms.zip',rom_files+[(stand/n,n) for n in ('README.txt','catalog.json','verification.json','SHA256SUMS.txt')])
    copy(DIST/'adofai-standalone-roms.zip',DIST/'adofai-official-worlds.zip')
    archive(DIST/'adofai-main-worlds.zip',[(stand/r['file'],r['file']) for r in cat['roms'] if '-main-' in r['key']],NOTE)
    demo=ROOT/'build/packs/sa1-renderer-demo'
    copy(demo/'adofai.sfc',DIST/'adofai-level1-demo.sfc')
    archive(DIST/'adofai-level1-demo.zip',[(DIST/'adofai-level1-demo.sfc','adofai-level1-demo.sfc')],NOTE)
    copy(DIST/'adofai-level1-demo.zip',DIST/'ADOFAI (SNES).zip')
    master=DIST/'adofai-msu-master'
    for name in ['adofai.sfc','adofai.msu',*new_pcm]:copy(BASE/name,master/name)
    (master/'verification.json').write_text(json.dumps(master_report,indent=2));(master/'README.txt').write_text(NOTE)
    (master/'SHA256SUMS.txt').write_text(''.join(r['sha256']+'  '+r['file']+'\n' for r in files))
    names=['adofai.sfc','adofai.msu','README.txt','verification.json','SHA256SUMS.txt',*new_pcm]
    update=DIST/'adofai-sa1-update'
    for name in names:copy(master/name,update/name)
    update_hashes={r['file']:r['sha256'] for r in files if r['file'] in names}
    (update/'SHA256SUMS.txt').write_text(''.join(digest+'  '+name+'\n' for name,digest in update_hashes.items()))
    archive(DIST/'adofai-update.zip',[(update/n,n) for n in names])
    for name in ('sa1','graphics','color','readability','native-scale','calibration-hotfix'):
        target='adofai-'+name+('-update' if name!='calibration-hotfix' else '')
        copy(DIST/'adofai-update.zip',DIST/(target+'.zip'))
    for folder in ('adofai-graphics-update','adofai-color-update','adofai-readability-update'):
        for name in names:copy(update/name,DIST/folder/name)
    for name in ('README.md','README.txt'):copy(ROOT/'README.md',DIST/name)
    omega_dist=DIST/'adofai-omega-msu'
    omega_hashes={name:sha(omega/name) for name in ('adofai.sfc','adofai.msu','adofai-65.pcm')}
    for name in omega_hashes:copy(omega/name,omega_dist/name)
    (omega_dist/'verification.json').write_text(json.dumps(omega_report,indent=2))
    (omega_dist/'README.txt').write_text('OOPARTS Nerfed - Lupel_2 (original by Nephrolepis), music by Camellia.\nExtract all files together and open adofai.sfc. Requires SA-1 and MSU-1 support.\nKeep adofai.msu and adofai-65.pcm beside the ROM.\n'+NOTE)
    (omega_dist/'SHA256SUMS.txt').write_text(''.join(digest+'  '+name+'\n' for name,digest in omega_hashes.items()))
    archive(DIST/'adofai-omega-msu.zip',[(omega_dist/name,name) for name in [*omega_hashes,'README.txt','verification.json','SHA256SUMS.txt']])
    print('Publishing complete master archive',flush=True)
    archive(DIST/'adofai-msu-master.zip',[(master/r['file'],r['file']) for r in files]+[(master/n,n) for n in ('README.txt','verification.json','SHA256SUMS.txt')])
    audits=[(DIST/'adofai-msu-master.zip',{r['file']:r['sha256'] for r in files}),
        (DIST/'adofai-update.zip',update_hashes),
        (DIST/'adofai-omega-msu.zip',omega_hashes),
        (DIST/'adofai-standalone-roms.zip',{r['file']:r['rom_sha256'] for r in cat['roms']})]
    audits += [(stand/Path(r['file']).with_suffix('.zip'),{r['file']:r['rom_sha256']}) for r in cat['roms']]
    for path,expected in audits:
        with zipfile.ZipFile(path) as z:
            assert len(z.namelist())==len(set(z.namelist()))
            for name,digest in expected.items():
                with z.open(name) as f:assert hashlib.file_digest(f,'sha256').hexdigest()==digest,(path,name)
    (ROOT/'build/renderer-release.json').write_text(json.dumps(dict(passed=True,**current,cartridges=32,master_charts=65,standalone_charts=64,pcm_files=285,master_checks=len(master_pixels),standalone_checks=len(standalone_pixels),checkpoint_checks=checkpoint_checks,audited_archives=[str(p) for p,e in audits]),indent=2))
    print('PASS: Renderer ROMs and archives published and audited',flush=True)

if __name__=='__main__':main()
