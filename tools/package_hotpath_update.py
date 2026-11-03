"""Publish the measured interpreter optimization with exact-build regression gates."""
import hashlib,json,zipfile
from pathlib import Path
from package_graphics_update import read,sha,copy,bound,graphics
from package_standalone import archive
from verification_data import identity

ROOT=Path(__file__).resolve().parents[1]
DIST=ROOT/'dist'
BASE=ROOT/'build/packs/sa1-hotpath-master'
NOTE='''ADOFAI SNES - animation interpreter optimization

Direct event dispatch, faster coordinate reads and less reference/audio
bookkeeping. Authored events, graphics quality and music data are unchanged.
Standalone music remains 12 kHz at 1x/below and 8 kHz above 1x.
61 charts in 29 standalone cartridges; each works without external files.

Master: keep the existing dataset-14 MSU file and all 269 PCM files.
The supplied update includes the matching MSU file for older installations.
Measured standalone 2x visual FPS: Heaven's Gateway 31.57 -> 34.17;
CE-TX 38.62 -> 39.16. Dense scenes still fall below 60 FPS.
See verification.json for exact-build checks. No physical hardware tests.
'''

def audio(folder,current):
    result=bound(folder/'result.json',current)
    check=bound(folder/'audio-check.json',current)
    assert result['final']['state']==3 and result['final']['misses']==0
    assert min(w['correlation'] for w in check['windows'])>.9 and abs(check['drift_ms'])<20
    return check

def main():
    cat=read(ROOT/'build/sa1-hotpath-standalone-catalog.json')
    assert len(cat['roms'])==29 and sorted(n for r in cat['roms'] for n in r['levels'])==list(range(1,62))
    assert read(ROOT/'build/hotpath-selected.json')['passed']
    assert read(ROOT/'build/hotpath-extra-audio.json')['passed']
    calibration=read(ROOT/'build/hotpath-calibration.json')
    assert calibration['passed']
    assert {r['key']:r['rom_sha256'] for r in calibration['cartridges']}=={r['key']:r['rom_sha256'] for r in cat['roms']}
    standalone_pixels=[];layouts=[]
    for r in cat['roms']:
        base=ROOT/'build/packs'/r['key'];current=identity(base/'adofai.sfc')
        assert current==dict(rom_sha256=r['rom_sha256'],msu_sha256=None)
        standalone_pixels+=graphics(r['key'],[1,1.1,2])
        layouts.append(bound(base/'verification/sa1-layout.json',current))
        prior=base.with_name(r['key'].replace('sa1-hotpath-','sa1-adaptive-'))
        for n in r['levels']:
            for suffix in ('.brr','-fast.brr'):
                assert sha(base/f'level{n}{suffix}')==sha(prior/f'level{n}{suffix}')
        r['file']=r['file'].replace('sa1-adaptive-','sa1-')
    current=identity(BASE/'adofai.sfc');master_pixels=graphics(BASE.name,[1,1.3,2])
    assert len(master_pixels)==len(standalone_pixels)==183
    assert current['msu_sha256']==identity(ROOT/'build/packs/sa1-safe-v14/adofai.sfc')['msu_sha256']
    demo=ROOT/'build/packs/sa1-hotpath-demo';demo_id=identity(demo/'adofai.sfc')
    graphics(demo.name,[1,1.1,2])
    unit=bound(ROOT/'build/sa1-hotpath-demo-unit-tests.json',demo_id)
    demo_calibration=bound(demo/'verification/calibration.json',demo_id)
    perf=[]
    for pack,n,path in [('sa1-hotpath-tech-15',60,'hotpath2-performance-60'),('sa1-hotpath-collab-02',31,'hotpath-performance-31')]:
        perf.append(bound(ROOT/f'build/{path}/result.json',identity(ROOT/f'build/packs/{pack}/adofai.sfc')))
    extra_audio=[]
    for r in read(ROOT/'build/hotpath-extra-audio.json')['results']:
        extra_audio.append(audio(Path(r['folder']),identity(ROOT/f"build/packs/{r['pack']}/adofai.sfc")))
    ce=ROOT/'build/packs/sa1-hotpath-collab-02';ce_id=identity(ce/'adofai.sfc')
    extra_audio.append(audio(ce/'verification/audio-31-20',ce_id))
    mesen=bound(ce/'verification/mesen-2-speed-20-autoplay/ppu-verification.json',ce_id)
    heaven=ROOT/'build/packs/sa1-hotpath-tech-15'
    checkpoints=bound(heaven/'verification/checkpoints-1-speed-20/result.json',identity(heaven/'adofai.sfc'))
    assert checkpoints['final']['state']==3 and checkpoints['death_scene_frozen']
    common=dict(verified=True,hardware_tested=False,performance=perf,unit_tests=unit,audio_checks=extra_audio,
        checkpoint_check=checkpoints,mesen_ppu=mesen,calibration_matrix=demo_calibration,
        source_hashes={str(p.relative_to(ROOT)):sha(p) for p in (ROOT/'src').glob('*') if p.is_file()},
        verification_scope='All 61 standalone charts at 1/1.1/2x and master charts at 1/1.3/2x: full-song every-frame PPU checks. All 29 cartridges: layout, calibration and controller gameplay. 106 unit tests. Selected BRR waveform, checkpoint and independent Mesen PPU checks. Music and authored datasets unchanged.')
    stand_report=dict(**common,roms=cat['roms'],ppu_replays=standalone_pixels,layouts=layouts,calibration_checks=calibration)
    prior=read(DIST/'adofai-msu-master/verification.json');files=[]
    for old in prior['files']:
        p=BASE/old['file'];digest=sha(p)
        if p.suffix in ('.pcm','.msu'):assert digest==old['sha256']
        files.append(dict(file=p.name,sha256=digest,bytes=p.stat().st_size))
    assert sum(r['file'].endswith('.pcm') for r in files)==269
    master_report=dict(**common,**current,dataset_version=14,world_count=61,files=files,unchanged_pcm=True,ppu_replays=master_pixels)
    print('PASS: exact-build optimization gates',flush=True)
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
    copy(demo/'adofai.sfc',DIST/'adofai-level1-demo.sfc')
    archive(DIST/'adofai-level1-demo.zip',[(DIST/'adofai-level1-demo.sfc','adofai-level1-demo.sfc')],NOTE)
    copy(DIST/'adofai-level1-demo.zip',DIST/'ADOFAI (SNES).zip')
    master=DIST/'adofai-msu-master';copy(BASE/'adofai.sfc',master/'adofai.sfc')
    (master/'verification.json').write_text(json.dumps(master_report,indent=2));(master/'README.txt').write_text(NOTE)
    (master/'SHA256SUMS.txt').write_text(''.join(r['sha256']+'  '+r['file']+'\n' for r in files))
    names=['adofai.sfc','adofai.msu','README.txt','verification.json','SHA256SUMS.txt']
    update=DIST/'adofai-sa1-update'
    for name in names:copy(master/name,update/name)
    (update/'SHA256SUMS.txt').write_text(current['rom_sha256']+'  adofai.sfc\n'+current['msu_sha256']+'  adofai.msu\n')
    archive(DIST/'adofai-update.zip',[(update/n,n) for n in names])
    for name in ('sa1','graphics','color','readability','native-scale','calibration-hotfix'):
        target='adofai-'+name+('-update' if name!='calibration-hotfix' else '')
        copy(DIST/'adofai-update.zip',DIST/(target+'.zip'))
    for folder in ('adofai-graphics-update','adofai-color-update','adofai-readability-update'):
        for name in names:copy(update/name,DIST/folder/name)
    for name in ('README.md','README.txt'):copy(ROOT/'README.md',DIST/name)
    print('Publishing complete master archive',flush=True)
    archive(DIST/'adofai-msu-master.zip',[(master/r['file'],r['file']) for r in files]+[(master/n,n) for n in ('README.txt','verification.json','SHA256SUMS.txt')])
    audits=[(DIST/'adofai-msu-master.zip',{r['file']:r['sha256'] for r in files}),
        (DIST/'adofai-update.zip',{'adofai.sfc':current['rom_sha256'],'adofai.msu':current['msu_sha256']}),
        (DIST/'adofai-standalone-roms.zip',{r['file']:r['rom_sha256'] for r in cat['roms']})]
    audits += [(stand/Path(r['file']).with_suffix('.zip'),{r['file']:r['rom_sha256']}) for r in cat['roms']]
    for path,expected in audits:
        with zipfile.ZipFile(path) as z:
            assert len(z.namelist())==len(set(z.namelist()))
            for name,digest in expected.items():
                with z.open(name) as f:assert hashlib.file_digest(f,'sha256').hexdigest()==digest,(path,name)
    (ROOT/'build/hotpath-release.json').write_text(json.dumps(dict(passed=True,**current,cartridges=29,master_checks=183,standalone_checks=183,performance=perf,audited_archives=[str(p) for p,e in audits]),indent=2))
    print('PASS: optimized ROMs and archives published and audited',flush=True)

if __name__=='__main__':main()
