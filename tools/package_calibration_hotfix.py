"""Publish a calibration-only patch with explicit incremental verification.

The prior complete campaign reports remain attached with their original ROM
hashes. This release checks every cartridge's calibration and one complete
song, rather than claiming the full campaign was replayed again.
"""
import hashlib,json,shutil,zipfile
from pathlib import Path
import package_master as master_package
from package_standalone import archive
from verification_data import identity
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'build/packs/master'
BACKUP=ROOT/'build/calibration-hotfix-baseline'
DIST=ROOT/'dist'

def read(path):return json.loads(path.read_text())
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    build=read(ROOT/'build/calibration-hotfix-build.json')
    assert build['passed'] and build['unchanged_game_assets'] and build['unchanged_msu']
    current=identity(BASE/'adofai.sfc');assert current==build['master']
    prior=read(BACKUP/'master-verification.json')
    assert prior['verified'] and prior['rom_sha256']==sha(BACKUP/'master.sfc')
    assert prior['msu_sha256']==current['msu_sha256']
    fixed=ROOT/'build/packs/calibration-fix'
    checks={}
    for name in ('calibration','calibration-mesen','tap-sounds'):
        report=read(fixed/f'verification/{name}.json')
        assert report['passed'] and all(report[k]==current[k] for k in current)
        checks[name]=report;shutil.copyfile(fixed/f'verification/{name}.json',BASE/f'verification/{name}.json')
    assert len(checks['calibration']['metronome'])==14
    assert len(checks['calibration']['entry_sounds'])==5
    unit=read(ROOT/'build/calibration-fix-unit.json')
    assert unit['passed'] and unit['tests']==81 and all(unit[k]==current[k] for k in current)
    log=(ROOT/'build/calibration-fix-unit.log').read_text();assert 'Ran 81 tests' in log and '\nOK\n' in log
    catalog=read(ROOT/'build/standalone-catalog.json')
    standalone_checks=read(ROOT/'build/calibration-standalone-verification.json')
    assert standalone_checks['passed'] and len(standalone_checks['cartridges'])==len(catalog['roms'])==21
    assert {r['key']:r['rom_sha256'] for r in standalone_checks['cartridges']}=={r['key']:r['rom_sha256'] for r in catalog['roms']}
    stand_mesen=read(ROOT/'build/packs/standalone-main-01/verification/calibration-mesen.json')
    assert stand_mesen['passed'] and stand_mesen['rom_sha256']==catalog['roms'][0]['rom_sha256']
    scope='Calibration hotfix: new checks below; complete prior campaign evidence retained with its original hashes'
    files=[dict(row) for row in prior['files']]
    for row in files:
        if row['file']=='adofai.sfc':row['sha256']=current['rom_sha256']
    verification=dict(verified=True,verification_scope=scope,**current,regression_tests=81,
                      unchanged_chart_audio_graphics_payloads=True,unchanged_msu_and_pcm=True,
                      calibration_checks=checks,unit_tests=unit,prior_release=prior,
                      files=files,total_bytes=prior['total_bytes'])
    text='''ADOFAI SNES - calibration hotfix

The calibration ball now circles continuously on the audio clock. Tapping
does not move or restart it. The click sounds immediately on entry, then
every 0.5 seconds (the original 120-BPM cadence). Its SPC voice is restored whenever calibration starts,
including after gameplay, pause and retry.

If you installed the previous dataset-version-9 release, replacing only
adofai.sfc is sufficient. Its adofai.msu and all PCM files are unchanged.
For older releases, replace both ROM and MSU from the full update ZIP.

This hotfix passed 81 regression tests; actual calibration audio/video,
signed offsets and first/later beat measurements; Mesen orbit and SPC sound
checks through five entry flows; and calibration plus one full-song replay
in each of the 21 standalone cartridges. The earlier complete 61-song/208-
checkpoint campaign reports retain their original hashes in verification.
Those full campaign checks were not repeated for this calibration-only fix.
All compiled chart, music and graphics payload bytes are unchanged.
'''
    out=DIST/'adofai-msu-master'
    assert sha(out/'adofai.msu')==current['msu_sha256']
    shutil.copyfile(BASE/'adofai.sfc',out/'adofai.sfc')
    shutil.copyfile(ROOT/'README.md',out/'README.txt')
    (out/'verification.json').write_text(json.dumps(verification,indent=2))
    (out/'SHA256SUMS.txt').write_text(''.join(r['sha256']+'  '+r['file']+'\n' for r in files))
    update=DIST/'adofai-color-update';update.mkdir(exist_ok=True)
    for name in ('adofai.sfc','adofai.msu','verification.json'):shutil.copyfile(out/name,update/name)
    (update/'README.txt').write_text(text)
    (update/'SHA256SUMS.txt').write_text(current['rom_sha256']+'  adofai.sfc\n'+current['msu_sha256']+'  adofai.msu\n')
    update_files=[(update/name,name) for name in ('adofai.sfc','adofai.msu','verification.json','SHA256SUMS.txt','README.txt')]
    archive(DIST/'adofai-update.zip',update_files)
    for name in ('adofai-color-update.zip','adofai-readability-update.zip','adofai-native-scale-update.zip'):
        shutil.copyfile(DIST/'adofai-update.zip',DIST/name)
    archive(DIST/'adofai-calibration-hotfix.zip',[(out/'adofai.sfc','adofai.sfc')],text+'\nSHA256: '+current['rom_sha256']+'\n')
    print('Master calibration ROM-only and ROM/MSU update ZIPs CRC passed',flush=True)
    stand_out=DIST/'adofai-standalone'
    prior_stand=read(BACKUP/'standalone-verification.json')
    stand_report=dict(verified=True,verification_scope=scope,external_files_required=False,roms=catalog['roms'],
                      calibration_checks=standalone_checks,mesen_calibration_checks=stand_mesen,prior_release=prior_stand)
    stand_note=text[:text.index('If you installed')]+text[text.index('This hotfix passed'):]
    stand_text=(stand_out/'README.txt').read_text().split('\nCALIBRATION HOTFIX\n')[0]+'\nCALIBRATION HOTFIX\n'+stand_note
    (stand_out/'README.txt').write_text(stand_text)
    (stand_out/'catalog.json').write_text(json.dumps(catalog,indent=2))
    (stand_out/'verification.json').write_text(json.dumps(stand_report,indent=2))
    sums='';rom_files=[]
    for row in catalog['roms']:
        source=ROOT/'build/packs'/row['key']/'adofai.sfc';target=stand_out/row['file']
        assert sha(source)==row['rom_sha256']
        shutil.copyfile(source,target);assert sha(target)==row['rom_sha256']
        sums+=row['rom_sha256']+'  '+row['file']+'\n';rom_files.append((target,row['file']))
        archive(stand_out/Path(row['file']).with_suffix('.zip'),[(target,row['file'])],stand_text+'\nSHA256: '+row['rom_sha256']+'\n')
    (stand_out/'SHA256SUMS.txt').write_text(sums)
    extras=[(stand_out/name,name) for name in ('README.txt','catalog.json','verification.json','SHA256SUMS.txt')]
    archive(DIST/'adofai-standalone-roms.zip',rom_files+extras)
    shutil.copyfile(DIST/'adofai-standalone-roms.zip',DIST/'adofai-official-worlds.zip')
    archive(DIST/'adofai-main-worlds.zip',[(stand_out/r['file'],r['file']) for r in catalog['roms'] if r['key'].startswith('standalone-main-')],stand_text)
    shutil.copyfile(ROOT/'README.md',DIST/'README.txt')
    shutil.copyfile(ROOT/'build/calibration-fix-unit.log',ROOT/'build/latest-unit-tests.log')
    (ROOT/'build/latest-unit-tests.json').write_text(json.dumps(unit,indent=2))
    print('All 21 standalone ROMs, individual ZIPs and combined bundle CRC passed',flush=True)
    master_package.make_archive(out,DIST/'adofai-msu-master.zip')
    (ROOT/'build/calibration-hotfix-release.json').write_text(json.dumps(dict(passed=True,**current,
       standalone_cartridges=21,regression_tests=81,verification_scope=scope),indent=2))
    print('Calibration hotfix packaged in all current downloads',flush=True)

if __name__=='__main__':main()
