"""Update every release in place, preserving compressed media ZIP entries."""
import copy
import hashlib
import json
import re
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT/'dist'
NOTE = '2026-11-02 R tile rotation and AR-X motion optimization update\nR opening tiles now follow their authored rotation, with individual separation lines.\nAR-X uses faster animation dispatch, WRAM coordinate transfers, wider prefetch,\nand half-resolution track textures during dense motion bursts.\nAR-X near 13%, MesenCE: 45.73 -> 54.23 delivered fps; longest hold 9 -> 4 frames.\nHeavy scenes still stutter; this is not a locked-60-fps release.\nHit sounds follow scheduled chart beats. Planets scale with camera zoom.\nMSU installations MUST replace BOTH adofai.sfc and adofai.msu (dataset 23).\nExisting PCM files are unchanged. Standalone cartridges need only their ROM.\n'

def sha(path):
    with path.open('rb') as f: return hashlib.file_digest(f, 'sha256').hexdigest()

def atomic_copy(source, target):
    temp = target.with_name(target.name+'.new')
    shutil.copyfile(source, temp); temp.replace(target)

def main():
    inputs = json.loads((ROOT/'build/optimized-release-inputs.json').read_text())
    replacements = {}; builds = []; masters = {}
    for row in inputs:
        pack = Path(row['pack']); rom = pack/'adofai.sfc'
        replacements[row['old_rom']] = rom
        for intermediate in row.get('intermediate_roms',[]):replacements[intermediate]=rom
        if row['old_msu']:
            replacements[row['old_msu']] = pack/'adofai.msu'
            masters[sha(rom)] = pack/'adofai.msu'
        builds.append(dict(pack=pack.name, rom_sha256=sha(rom),
                           msu_sha256=sha(pack/'adofai.msu') if row['old_msu'] else None))
    mapping = {old:sha(p) for old,p in replacements.items()}
    valid_roms = {r['rom_sha256'] for r in builds}
    valid_msu = {r['msu_sha256'] for r in builds if r['msu_sha256']}
    evidence = {}
    for name in ('optimized-all-graphics.json', 'optimized-fast-graphics.json', 'optimized-standalone-checks.json',
                 'optimized-layout.json', 'optimized-standalone-ar-graphics.json',
                 'optimized-standalone-ce-graphics.json', 'optimized-standalone-r-graphics.json'):
        r = json.loads((ROOT/'build'/name).read_text()); assert r['passed'], name
        evidence[name] = r
    base = ROOT/'build/packs/sa1-scheduled-hits'
    for name in ('scheduled-hits.json', 'planet-zoom/result.json', 'checkpoint-countdown.json'):
        r = json.loads((base/'verification'/name).read_text()); assert r['passed'], name
        evidence[name] = r
    evidence['pcm-scheduled-hits'] = json.loads((ROOT/'build/pcm-scheduled-check/result.json').read_text())
    assert evidence['pcm-scheduled-hits']['passed']
    for folder in ('mesen-23-autoplay','mesen-31-autoplay','mesen-checkpoints-23','mesen-checkpoints-45'):
        r=json.loads((base/'verification'/folder/'ppu-verification.json').read_text())
        assert r['passed'] and r['rom_sha256']==sha(base/'adofai.sfc') and r['msu_sha256']==sha(base/'adofai.msu')
        evidence[folder]=r
    evidence['standalone_ar_checkpoints']=json.loads((ROOT/'build/all-audio-fix/sa1-renderer-extra-03/verification/mesen-checkpoints-1/ppu-verification.json').read_text())
    assert evidence['standalone_ar_checkpoints']['passed']
    expected_data={r['rom_sha256']:r['msu_sha256'] for r in builds}
    def bound(value):
        if isinstance(value,dict):
            if 'rom_sha256' in value:
                assert value['rom_sha256'] in expected_data,('Stale ROM evidence',value['rom_sha256'])
                if 'msu_sha256' in value:assert value['msu_sha256']==expected_data[value['rom_sha256']], 'Stale data evidence'
            for child in value.values():bound(child)
        elif isinstance(value,list):
            for child in value:bound(child)
    bound(evidence)
    evidence['ar13_before']=json.loads((ROOT/'build/ar13-previous-release.json').read_text())
    evidence['ar13_after']=json.loads((ROOT/'build/ar13-mesen-after/result.json').read_text())
    assert evidence['ar13_after']['rom_sha256']==sha(base/'adofai.sfc')
    assert evidence['ar13_after']['msu_sha256']==sha(base/'adofai.msu')
    report = dict(passed=True, release='2026-11-02 R rotation and AR-X motion optimization', builds=builds,
                  checks=evidence, performance_limit='AR-X remains below 60 fps; MesenCE measured 54.23 fps around 13%, 4-frame worst hold.')

    def update_text(name, data):
        encoding='utf-8'
        try: text=data.decode(encoding)
        except UnicodeDecodeError: encoding='cp1252';text=data.decode(encoding)
        if Path(name).name=='RELEASE-NOTES.txt':return NOTE.encode()
        if 'ADOFAI - autoplay audio timing fix' in text:
            return (NOTE+'\nClose the emulator and replace both game files in your master folder.\n'
                    'Keep existing PCM files. Start fresh rather than loading an old save state.\n'
                    'All current distribution ZIPs include this release.\n'
                    'Required adofai.msu SHA256: '+sha(base/'adofai.msu')+'\n').encode()
        if Path(name).name == 'verification.json':
            return json.dumps(report,indent=2).encode()
        for old,new in mapping.items(): text=text.replace(old,new)
        if Path(name).name=='SHA256SUMS.txt' and sha(base/'adofai.sfc') in text and 'adofai.msu' not in text:
            text=text.rstrip()+'\n'+sha(base/'adofai.msu')+'  adofai.msu\n'
        text=text.replace('dataset version 20','dataset version 23').replace('dataset 20','dataset 23')
        text=text.replace('dataset version 21','dataset version 23').replace('dataset 21','dataset 23')
        text=text.replace('dataset version 22','dataset version 23').replace('dataset 22','dataset 23')
        text=text.replace('Full-catalog checks for the final startup-clear fix are still running.\n','')
        if Path(name).name.lower().startswith('readme'):
            if text.startswith('2026-11-02 ') and 'update' in text.split('\n',1)[0]:
                text=text.partition('\n\n')[2]
            # Superseded percussion semantics must not remain as current instructions.
            paragraphs=text.split('\n\n')
            paragraphs=[p for p in paragraphs if not any(s in p for s in (
                'Manual percussion is dispatched', 'Manual tap feedback now',
                'Autoplay timing fix included:', 'ROM-only autoplay', 'ROM-only update'))]
            text=NOTE+'\n'+'\n\n'.join(paragraphs)
            if 'COMPRESSED MASTER' in text:
                size=(base/'adofai.sfc').stat().st_size+(base/'adofai.msu').stat().st_size
                text=re.sub(r'Installed game files: [^\n]+',f'Installed game files: {size:,} bytes ({size/1048576:.2f} MiB).',text)
            elif 'HYBRID MASTER' in text:
                size=(base/'adofai.sfc').stat().st_size+(base/'adofai.msu').stat().st_size+sum(p.stat().st_size for p in (DIST/'adofai-msu-hybrid').glob('*.pcm'))
                text=re.sub(r'Installed game files: [^\n]+',f'Installed game files: {size:,} bytes ({size/1048576:.2f} MiB).',text)
        return text.encode(encoding)

    metadata={'catalog.json','verification.json','SHA256SUMS.txt','README.txt','README.md','RELEASE-NOTES.txt'}
    for path in DIST.rglob('*'):
        if path.suffix in ('.sfc','.msu'):
            old=sha(path)
            if old in replacements: atomic_copy(replacements[old],path)
            assert sha(path) in valid_roms|valid_msu, path
        elif path.is_file() and path.name in metadata:
            path.write_bytes(update_text(path.name,path.read_bytes()))
    # The old small hotfix now needs the matching animation dataset too.
    hotfix=DIST/'adofai-autoplay-audio-fix'
    atomic_copy(base/'adofai.msu',hotfix/'adofai.msu')
    (DIST/'RELEASE-NOTES.txt').write_text(NOTE)
    archives=[]
    for path in sorted(DIST.rglob('*.zip')):
        temporary=path.with_suffix('.zip.partial');expected={};needed={}
        with zipfile.ZipFile(path) as source, zipfile.ZipFile(temporary,'w',zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True) as output:
            entries=source.infolist();ordered=sorted(entries,key=lambda e:e.header_offset)
            ends={e.header_offset:(ordered[i+1].header_offset if i+1<len(ordered) else source.start_dir) for i,e in enumerate(ordered)}
            names={e.filename for e in entries}
            for entry in entries:
                name=entry.filename;ext=Path(name).suffix
                if ext in ('.sfc','.msu'):
                    old=hashlib.sha256(source.read(entry)).hexdigest()
                    if old in replacements: data=replacements[old].read_bytes()
                    else: data=source.read(entry)
                    digest=hashlib.sha256(data).hexdigest()
                    assert digest in (valid_roms if ext=='.sfc' else valid_msu),(path,name,old)
                    expected[name]=digest;output.writestr(entry,data)
                    if ext=='.sfc' and digest in masters:
                        msuname=str(Path(name).with_suffix('.msu')).replace('\\','/')
                        if msuname not in names:needed[msuname]=masters[digest]
                elif Path(name).name in metadata:
                    output.writestr(entry,update_text(name,source.read(entry)))
                else:
                    # Copy the local header, compressed bytes and optional descriptor
                    # verbatim. ZipFile writes a new central directory on close.
                    output.fp.seek(output.start_dir);source.fp.seek(entry.header_offset)
                    copied=copy.copy(entry);copied.header_offset=output.start_dir
                    remaining=ends[entry.header_offset]-entry.header_offset
                    while remaining:
                        block=source.fp.read(min(1024*1024,remaining));assert block
                        output.fp.write(block);remaining-=len(block)
                    output.start_dir=output.fp.tell();output.filelist.append(copied)
                    output.NameToInfo[copied.filename]=copied;output._didModify=True
            for name,media in needed.items():
                output.write(media,name);expected[name]=sha(media)
            if 'RELEASE-NOTES.txt' not in names:output.writestr('RELEASE-NOTES.txt',NOTE)
        with zipfile.ZipFile(temporary) as check:
            assert check.testzip() is None,path
            for name,digest in expected.items(): assert hashlib.sha256(check.read(name)).hexdigest()==digest,(path,name)
        temporary.replace(path)
        archives.append(dict(file=str(path.relative_to(DIST)),files=expected))
        (ROOT/'build/optimized-package-progress.json').write_text(json.dumps(archives,indent=2))
        print('Verified ZIP',path.name,flush=True)
    assert len(archives)==49,len(archives)
    report['archives']=archives
    (ROOT/'build/optimized-release.json').write_text(json.dumps(report,indent=2))
    print('PASS all 49 ZIPs and loose releases updated',flush=True)

if __name__=='__main__':main()
