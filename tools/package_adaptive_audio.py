"""Publish the optional-quality tradeoff only in standalone cartridges."""
import argparse,json,hashlib,zipfile
from pathlib import Path
from package_graphics_update import read,sha,copy,bound,graphics
from package_standalone import archive
from verification_data import identity
ROOT=Path(__file__).resolve().parents[1];DIST=ROOT/'dist';CAT=ROOT/'build/sa1-adaptive-standalone-catalog.json'
NOTE='''ADOFAI SNES - automatic standalone audio quality

61 charts. No external MSU or PCM files are required.
At 0.5x through 1.0x: original 12-kHz mono BRR music, unchanged.
Above 1.0x: 8-kHz mono BRR, generated from the original music source.
Selection is automatic; returning to 1.0x restores the original quality.
Pitch still follows speed. Hit sounds and calibration are unchanged.
Both streams fit in each 8-MiB SA-1 cartridge, with additional cartridge
parts where needed. Consult catalog.json for current song groupings.

This reduces high-speed audio traffic by one third. Dense levels can
still drop frames; this is not a locked-60-FPS build. Check verification.json
for exact tested cartridge hashes and measured performance. Emulator-tested;
physical hardware has not been tested. The MSU master is unchanged.
'''
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--check-only',action='store_true');a=ap.parse_args()
 cat=read(CAT);assert sorted(n for r in cat['roms'] for n in r['levels'])==list(range(1,62))
 master=identity(DIST/'adofai-msu-master/adofai.sfc');assert master['rom_sha256']==read(ROOT/'build/final-release.json')['rom_sha256']
 calibration=read(ROOT/'build/adaptive-calibration-standalone.json');assert calibration['passed']
 assert {r['key']:r['rom_sha256'] for r in calibration['cartridges']}=={r['key']:r['rom_sha256'] for r in cat['roms']}
 assert read(ROOT/'build/adaptive-selected.json')['passed']
 checks=[];layouts=[];switches=[];audio=[];retries=[];performance=[];mesen=[]
 for r in cat['roms']:
  base=ROOT/'build/packs'/r['key'];current=identity(base/'adofai.sfc');assert current==dict(rom_sha256=r['rom_sha256'],msu_sha256=None)
  assert read(base/'pack.json')['fast_audio_rate']==8000
  checks+=graphics(r['key'],[1,1.1,2]);layouts.append(bound(base/'verification/sa1-layout.json',current));switches.append(bound(base/'verification/adaptive-switching.json',current))
  for n in r['levels']:
   assert sha(base/f'level{n}.brr')==sha(ROOT/f'build/packs/sa1-safe-v14/level{n}.brr')
   if n in (1,24,31,43,44,45,60):
    for speed in (11,20):
     folder=base/f'verification/adaptive-audio-{n}-{speed}'
     result=bound(folder/'result.json',current);report=bound(folder/'audio-check.json',current)
     assert result['final']['state']==3 and result['final']['misses']==result['final']['tap_overruns']==result['final']['pattern_vblank_overruns']==0
     assert min(w['correlation'] for w in report['windows'])>.9 and abs(report['drift_ms'])<20
     audio.append(dict(level=n,speed=speed/10,**report))
   if n in (24,43,44,60):
    local=r['levels'].index(n)+1
    for speed in ([11,20] if n==60 else [20]):
     result=bound(base/f'verification/checkpoints-{local}-speed-{speed}/result.json',current)
     assert result['final']['state']==3 and result['death_scene_frozen'];retries.append(result)
   if n in (31,60):
    performance.append(bound(base/f'verification/adaptive-performance-{n}/result.json',current))
    local=r['levels'].index(n)+1;speed=11 if n==31 else 20
    mesen.append(bound(base/f'verification/mesen-{local}-speed-{speed}-autoplay/ppu-verification.json',current))
   if n==60:
    countdown=read(base/'verification/checkpoint-countdown.json');assert countdown['passed']
    assert all(all(case.get(k)==v for k,v in current.items()) for case in countdown['cases'])
  r['file']=r['file'].replace('sa1-adaptive-','sa1-')
 assert len(checks)==183 and len(audio)==14 and len(retries)==5
 demo=ROOT/'build/packs/sa1-adaptive-demo';demo_checks=graphics(demo.name,[1,1.1,2])
 unit=bound(ROOT/'build/sa1-adaptive-demo-unit-tests.json',identity(demo/'adofai.sfc'));assert unit['tests']>=106
 report=dict(verified=True,roms=cat['roms'],audio=cat['audio'],external_files_required=False,ppu_replays=checks,layouts=layouts,calibration=calibration,switching=switches,audio_checks=audio,checkpoints=retries,countdown=countdown,performance=performance,mesen=mesen,unit_tests=unit,master_unchanged=master,hardware_tested=False,
  verification_scope='61 standalone charts at 1.0x/1.1x/2.0x: complete-song every-frame PPU checks. All cartridges: layout, switching, calibration and gameplay. Seven selected charts: music waveform at 1.1x/2x. Four charts: every checkpoint at 2x; Heaven\'s Gateway also 1.1x. Mesen PPU replays of CE-TX and Heaven\'s Gateway. Normal music bytes unchanged.')
 print('PASS: adaptive-audio release gates',flush=True)
 if a.check_only:return
 stand=DIST/'adofai-standalone';previous=read(stand/'catalog.json');files=[]
 for r in cat['roms']:
  target=stand/r['file'];copy(ROOT/'build/packs'/r['key']/'adofai.sfc',target);files.append((target,r['file']))
  archive(target.with_suffix('.zip'),[(target,r['file'])],NOTE+'\nSongs: '+', '.join(r['codes'])+'\n')
 legacy=DIST/'legacy-standalone';legacy.mkdir(exist_ok=True)
 for name in {r['file'] for r in previous['roms']}-{r['file'] for r in cat['roms']}:
  for p in (stand/name,(stand/name).with_suffix('.zip')):
   assert p.resolve().is_relative_to(stand.resolve()) and legacy.resolve().is_relative_to(DIST.resolve())
   if p.exists():p.replace(legacy/(p.stem+'-before-adaptive'+p.suffix))
 (stand/'catalog.json').write_text(json.dumps(cat,indent=2));(stand/'verification.json').write_text(json.dumps(report,indent=2));(stand/'README.txt').write_text(NOTE)
 (stand/'SHA256SUMS.txt').write_text(''.join(r['rom_sha256']+'  '+r['file']+'\n' for r in cat['roms']))
 archive(DIST/'adofai-standalone-roms.zip',files+[(stand/n,n) for n in ('README.txt','catalog.json','verification.json','SHA256SUMS.txt')])
 copy(DIST/'adofai-standalone-roms.zip',DIST/'adofai-official-worlds.zip')
 archive(DIST/'adofai-main-worlds.zip',[(stand/r['file'],r['file']) for r in cat['roms'] if '-main-' in r['key']],NOTE)
 copy(demo/'adofai.sfc',DIST/'adofai-level1-demo.sfc');archive(DIST/'adofai-level1-demo.zip',[(DIST/'adofai-level1-demo.sfc','adofai-level1-demo.sfc')],NOTE);copy(DIST/'adofai-level1-demo.zip',DIST/'ADOFAI (SNES).zip')
 copy(ROOT/'README.md',DIST/'README.md');copy(ROOT/'README.md',DIST/'README.txt')
 assert {p.name for p in stand.glob('*.sfc')}=={r['file'] for r in cat['roms']}
 for path in [DIST/'adofai-standalone-roms.zip']+[stand/Path(r['file']).with_suffix('.zip') for r in cat['roms']]:
  with zipfile.ZipFile(path) as z:
   for r in cat['roms']:
    if r['file'] in z.namelist():assert hashlib.sha256(z.read(r['file'])).hexdigest()==r['rom_sha256']
 assert identity(DIST/'adofai-msu-master/adofai.sfc')==master
 (ROOT/'build/adaptive-release.json').write_text(json.dumps(dict(passed=True,cartridges=len(cat['roms']),charts=61,graphics_checks=183,master_unchanged=master,performance=performance),indent=2))
 print('PASS: published adaptive-audio cartridges and verified ZIPs',flush=True)
if __name__=='__main__':main()
