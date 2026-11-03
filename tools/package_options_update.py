"""Publish the source-verified Options native placement correction."""
import hashlib,json,zipfile
from pathlib import Path
from package_graphics_update import read,sha,copy,bound,graphics
from package_standalone import archive
from verification_data import identity

ROOT=Path(__file__).resolve().parents[1]
DIST=ROOT/'dist'
BASE=ROOT/'build/packs/sa1-options-master'
NOTE='''ADOFAI SNES - Options native layout correction

Options now uses its authored native floor positions instead of rebuilding
all sections into one continuous path. The original level-controller setting
also makes the planets follow its moving floors. No arbitrary disappearing
rule was added. Timing, music samples and all other chart assets are unchanged.

Master: replace BOTH adofai.sfc and adofai.msu (dataset 16).
Keep the existing 269 PCM files. No PCM download is needed.
Standalone: replace Crown Island (XO-X / XT-X). The other 28 ROMs are unchanged.
See verification.json for exact-build checks. No physical hardware tests.
'''

def main():
    cat=read(ROOT/'build/sa1-options-standalone-catalog.json')
    oldcat=read(DIST/'adofai-standalone/catalog.json')
    assert len(cat['roms'])==29 and sorted(n for r in cat['roms'] for n in r['levels'])==list(range(1,62))
    crown=ROOT/'build/packs/sa1-options-crown-01';crown_id=identity(crown/'adofai.sfc')
    unchanged=[]
    for r,old in zip(cat['roms'],oldcat['roms']):
        assert r['file']==old['file'] and r['levels']==old['levels']
        assert sha(ROOT/'build/packs'/r['key']/'adofai.sfc')==r['rom_sha256']
        if 25 not in r['levels']:
            assert r['rom_sha256']==old['rom_sha256'];unchanged.append(r)
    assert len(unchanged)==28
    calibration=read(ROOT/'build/options-calibration.json')
    assert calibration['passed'] and calibration['rom_sha256']==crown_id['rom_sha256']
    standalone_pixels=graphics(crown.name,[1,1.1,2]);assert len(standalone_pixels)==6
    current=identity(BASE/'adofai.sfc');master_pixels=[]
    matrix=read(ROOT/'build/options-master-graphics.json');assert matrix['passed'] and len(matrix['results'])==12
    for row in matrix['results']:
        assert all(row[k]==v for k,v in current.items())
        n=row['level'];speed=row['speed'];suffix='' if speed==1 else f'-speed-{round(speed*10)}'
        r=bound(BASE/f'verification/render-{n}{suffix}.json',current)
        assert r['completed_song'] and r['every_frame'] and r['ppu_chr_match']
        assert r['vblank_overruns']==r['cache_capacity_errors']==0 and not r['tile_flashes']
        assert r['final_state']==3 and r['combo']==r['expected_hits']
        master_pixels.append(r)
    layouts=[bound(p/'verification/sa1-layout.json',identity(p/'adofai.sfc')) for p in (BASE,crown)]
    bound(BASE/'verification/msu-version.json',current)
    with (BASE/'adofai.msu').open('rb') as f:assert f.read(14)==b'ADOFAI-MSU1\0\x10\0'
    unit=bound(ROOT/'build/sa1-options-master-unit-tests.json',current);assert unit['tests']>=110
    cps=read(ROOT/'build/options-checkpoints.json');assert cps['passed'] and len(cps['results'])==3
    checkpoint_checks=[]
    for row in cps['results']:
        folder=Path(row['folder']);evidence=identity(ROOT/'build/packs'/row['pack']/'adofai.sfc')
        assert all(row[k]==v for k,v in evidence.items()) and (folder/'result.txt').read_text().endswith('PASS\n')
        checkpoint_checks.append(bound(folder/'ppu-verification.json',evidence))
    priorbase=ROOT/'build/packs/sa1-sound-final-master'
    for n in range(1,62):
        assert sha(BASE/f'level{n}.brr')==sha(priorbase/f'level{n}.brr')
        if n==25:continue
        for name in [f'level{n}.json']+[f'{prefix}{n}.bin' for prefix in ('chart','track_chr','track_map','patterns','animation','visibility_index')]+[p.name for p in priorbase.glob(f'animation{n}-checkpoint-*.bin')]:
            assert sha(BASE/name)==sha(priorbase/name),(n,name)
    before=read(priorbase/'level25.json');after=read(BASE/'level25.json')
    assert before['checkpoints']==after['checkpoints']
    for a,b in zip(before['notes'],after['notes']):
        for key in ('frame','time','angle','rate','flags','speed','spin_kind'):assert a[key]==b[key],(a['step'],key)
    common=dict(verified=True,hardware_tested=False,unit_tests=unit,checkpoint_checks=checkpoint_checks,
        previous_release_sha256=sha(ROOT/'build/sound-final-release.json'),
        source_hashes={str(p.relative_to(ROOT)):sha(p) for p in (ROOT/'src').glob('*') if p.is_file()},
        verification_scope='Options layout correction only. New Crown ROM: both charts at 1/1.1/2x, calibration and layout. New master: XO-X, XT-X, CE-TX and R at 1/1.3/2x, layout and dataset-version guard. Every-frame full-song PPU checks. All five Options checkpoints in Mesen at standalone 1x/2x and master 1x, with sampled pixel comparisons. 110 unit tests. Other 28 standalone ROMs and 60 master chart datasets verified byte-identical to the previous audited release. Music bytes unchanged.')
    stand_report=dict(**common,roms=cat['roms'],ppu_replays=standalone_pixels,layouts=layouts,calibration_checks=calibration,unchanged_cartridges=unchanged)
    prior=read(DIST/'adofai-msu-master/verification.json');files=[]
    for old in prior['files']:
        p=BASE/old['file'];digest=sha(p)
        if p.suffix=='.pcm':assert digest==old['sha256']
        files.append(dict(file=p.name,sha256=digest,bytes=p.stat().st_size))
    assert sum(r['file'].endswith('.pcm') for r in files)==269
    master_report=dict(**common,**current,dataset_version=16,world_count=61,files=files,unchanged_pcm=True,ppu_replays=master_pixels)
    print('PASS: exact-build Options layout gates',flush=True)
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
    master=DIST/'adofai-msu-master'
    for name in ('adofai.sfc','adofai.msu'):copy(BASE/name,master/name)
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
    (ROOT/'build/options-release.json').write_text(json.dumps(dict(passed=True,**current,cartridges=29,master_checks=12,standalone_checks=6,checkpoint_checks=checkpoint_checks,audited_archives=[str(p) for p,e in audits]),indent=2))
    print('PASS: Options layout ROMs and archives published and audited',flush=True)

if __name__=='__main__':main()
