"""Update every release in place, preserving compressed media ZIP entries."""
import copy
import hashlib
import json
import re
import shutil
import struct
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

def main(release_report=None, release_note=None, pcm_archive=None, pcm_files=None, dataset_version=23, inputs_path=None, base=None, media_files=None):
    note = release_note or NOTE
    media_files=media_files or {}
    inputs = json.loads((inputs_path or ROOT/'build/optimized-release-inputs.json').read_text())
    replacements = {}; builds = []; masters = {}; parts = {}; primary = {}
    for row in inputs:
        pack = Path(row['pack']); rom = pack/'adofai.sfc'
        replacements[row['old_rom']] = rom
        for intermediate in row.get('intermediate_roms',[]):replacements[intermediate]=rom
        if row['old_msu']:
            replacements[row['old_msu']] = pack/'adofai.msu'
            masters[sha(rom)] = pack/'adofai.msu'
        builds.append(dict(pack=pack.name, rom_sha256=sha(rom),
                           msu_sha256=sha(pack/'adofai.msu') if row['old_msu'] else None))
        primary[sha(rom)]=pack
        for extra in row.get('extras',[]):
            extra=Path(extra);parts.setdefault(sha(rom),[]).append(extra)
            previous=row.get('extra_old_roms',{}).get(str(extra))
            if previous:replacements[previous]=extra/'adofai.sfc'
            builds.append(dict(pack=extra.name,rom_sha256=sha(extra/'adofai.sfc'),msu_sha256=None))
    mapping = {old:sha(p) for old,p in replacements.items()}
    valid_roms = {r['rom_sha256'] for r in builds}
    valid_msu = {r['msu_sha256'] for r in builds if r['msu_sha256']}
    extra_hashes={sha(part/'adofai.sfc') for group in parts.values() for part in group}
    base = base or ROOT/'build/packs/sa1-scheduled-hits'
    pcm_files = pcm_files or {}
    pcm_hashes = {name:sha(path) for name,path in pcm_files.items()}
    pcm_zip = zipfile.ZipFile(pcm_archive) if pcm_archive else None
    if pcm_files:
        assert pcm_zip is not None and set(pcm_files)==set(pcm_zip.namelist())

    def copy_pcm(name, output):
        original = pcm_zip.getinfo(Path(name).name)
        entry = copy.copy(original)
        entry.filename = entry.orig_filename = name
        entry.header_offset = output.start_dir
        entry.flag_bits &= ~8
        output.fp.seek(output.start_dir)
        output.fp.write(entry.FileHeader(zip64=max(entry.file_size,entry.compress_size)>=zipfile.ZIP64_LIMIT))
        pcm_zip.fp.seek(original.header_offset)
        header = struct.unpack('<4s5H3I2H',pcm_zip.fp.read(30))
        assert header[0]==b'PK\x03\x04'
        pcm_zip.fp.seek(header[-2]+header[-1],1)
        left = entry.compress_size
        while left:
            block = pcm_zip.fp.read(min(left,1024*1024));assert block
            output.fp.write(block);left-=len(block)
        output.start_dir=output.fp.tell()
        output.filelist.append(entry);output.NameToInfo[name]=entry;output._didModify=True
    if release_report is None:
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
    else:
        report = release_report(builds, base)

    def update_text(name, data):
        encoding='utf-8'
        try: text=data.decode(encoding)
        except UnicodeDecodeError: encoding='cp1252';text=data.decode(encoding)
        if Path(name).name=='RELEASE-NOTES.txt':return note.encode()
        if 'ADOFAI - autoplay audio timing fix' in text:
            return (note+'\nClose the emulator and replace both game files in your master folder.\n'
                    'Keep existing PCM files. Start fresh rather than loading an old save state.\n'
                    'All current distribution ZIPs include this release.\n'
                    'Required adofai.msu SHA256: '+sha(base/'adofai.msu')+'\n').encode()
        if Path(name).name == 'verification.json':
            return json.dumps(report,indent=2).encode()
        for old,new in mapping.items(): text=text.replace(old,new)
        if Path(name).name=='catalog.json':
            catalog=json.loads(text)
            if isinstance(catalog,dict) and 'roms' in catalog:
                updated=[]
                for row in catalog['roms']:
                    digest=row.get('rom_sha256');pack=primary.get(digest)
                    if digest in extra_hashes:continue
                    if pack:
                        for number,part in enumerate([pack,*parts.get(digest,[])],1):
                            item=dict(row);meta=json.loads((part/'pack.json').read_text())
                            item.update(levels=meta['levels'],title=meta['title'],rom_sha256=sha(part/'adofai.sfc'),codes=[json.loads((part/f'level{n}.json').read_text())['code'] for n in meta['levels']])
                            if number>1:
                                path=Path(item['file']);item['file']=str(path.with_name(path.stem+f'-part{number}'+path.suffix)).replace('\\','/')
                                item['key']+=f'-part{number}'
                            updated.append(item)
                    else:updated.append(row)
                catalog['roms']=updated;text=json.dumps(catalog,indent=2)
        if Path(name).name=='SHA256SUMS.txt':
            additions=[]
            for line in text.splitlines():
                match=re.match(r'^([0-9a-f]{64})\s+\*?(.+\.sfc)$',line)
                if match:
                    for number,part in enumerate(parts.get(match[1],[]),2):
                        path=Path(match[2]);target=path.with_name(path.stem+f'-part{number}'+path.suffix)
                        line=sha(part/'adofai.sfc')+'  '+str(target).replace('\\','/')
                        if line not in text:additions.append(line)
            if additions:text=text.rstrip()+'\n'+'\n'.join(additions)+'\n'
        if Path(name).name=='SHA256SUMS.txt' and pcm_files:
            def pcm_sum(match):
                filename=Path(match[2]).name
                assert filename in pcm_hashes, filename
                return pcm_hashes[filename]+match[1]+match[2]
            text=re.sub(r'(?m)^[0-9a-fA-F]{64}(\s+\*?)([^\r\n]+\.pcm)$',pcm_sum,text)
        if Path(name).name=='SHA256SUMS.txt' and sha(base/'adofai.sfc') in text and 'adofai.msu' not in text:
            text=text.rstrip()+'\n'+sha(base/'adofai.msu')+'  adofai.msu\n'
        text=re.sub(r'\b(dataset(?: version)? )([0-9]+)\b',
                    lambda m:m[1]+str(dataset_version) if 20<=int(m[2])<dataset_version else m[0],text)
        text=text.replace('Full-catalog checks for the final startup-clear fix are still running.\n','')
        if Path(name).name.lower().startswith('readme'):
            text=text.replace('\r\n','\n')
            # Keep current installation directions clear of obsolete release notes.
            paragraphs=text.split('\n\n')
            paragraphs=[p for p in paragraphs if not re.match(r'^20\d\d-\d\d-\d\d ',p) and not any(s in p for s in (
                'Manual percussion is dispatched', 'Manual tap feedback now',
                'Autoplay timing fix included:', 'ROM-only autoplay', 'ROM-only update'))]
            text=note+'\n'+'\n\n'.join(paragraphs)
            if 'COMPRESSED MASTER' in text:
                size=(base/'adofai.sfc').stat().st_size+(base/'adofai.msu').stat().st_size
                text=re.sub(r'Installed game files: [^\n]+',f'Installed game files: {size:,} bytes ({size/1048576:.2f} MiB).',text)
            elif 'HYBRID MASTER' in text:
                size=(base/'adofai.sfc').stat().st_size+(base/'adofai.msu').stat().st_size+sum(p.stat().st_size for p in (DIST/'adofai-msu-hybrid').glob('*.pcm'))
                text=re.sub(r'Installed game files: [^\n]+',f'Installed game files: {size:,} bytes ({size/1048576:.2f} MiB).',text)
        return text.encode(encoding)

    metadata={'catalog.json','verification.json','SHA256SUMS.txt','README.txt','README.md','RELEASE-NOTES.txt'}
    for path in DIST.rglob('*'):
        if path.is_file() and path.name in media_files:
            atomic_copy(media_files[path.name],path)
        elif path.suffix in ('.sfc','.msu'):
            old=sha(path)
            if old in replacements and mapping[old] != old:
                atomic_copy(replacements[old],path)
            assert sha(path) in valid_roms|valid_msu, path
            for number,part in enumerate(parts.get(sha(path),[]),2):
                atomic_copy(part/'adofai.sfc',path.with_name(path.stem+f'-part{number}'+path.suffix))
        elif path.suffix=='.pcm' and pcm_files:
            assert path.name in pcm_files, path
            atomic_copy(pcm_files[path.name],path)
        elif path.is_file() and path.name in metadata:
            path.write_bytes(update_text(path.name,path.read_bytes()))
    # The old small hotfix now needs the matching animation dataset too.
    hotfix=DIST/'adofai-autoplay-audio-fix'
    if hotfix.is_dir():
        atomic_copy(base/'adofai.msu',hotfix/'adofai.msu')
    (DIST/'RELEASE-NOTES.txt').write_text(note)
    archives=[]
    archive_paths=sorted(DIST.rglob('*.zip'))
    assert archive_paths, 'No release archives found'
    for path in archive_paths:
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
                    for number,part in enumerate(parts.get(digest,[]),2):
                        filename=Path(name);extra_name=str(filename.with_name(filename.stem+f'-part{number}'+filename.suffix)).replace('\\','/')
                        if extra_name not in names:needed[extra_name]=part/'adofai.sfc'
                    if ext=='.sfc' and digest in masters:
                        msuname=str(Path(name).with_suffix('.msu')).replace('\\','/')
                        if msuname not in names:needed[msuname]=masters[digest]
                elif ext=='.pcm' and pcm_files:
                    assert Path(name).name in pcm_files, (path,name)
                    copy_pcm(name,output)
                    expected[name]=pcm_hashes[Path(name).name]
                elif Path(name).name in metadata:
                    output.writestr(entry,update_text(name,source.read(entry)))
                elif Path(name).name in media_files:
                    output.writestr(entry,media_files[Path(name).name].read_bytes())
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
            if 'RELEASE-NOTES.txt' not in names:output.writestr('RELEASE-NOTES.txt',note)
        with zipfile.ZipFile(temporary) as check:
            assert check.testzip() is None,path
            for name,digest in expected.items(): assert hashlib.sha256(check.read(name)).hexdigest()==digest,(path,name)
        temporary.replace(path)
        archives.append(dict(file=str(path.relative_to(DIST)),files=expected))
        (ROOT/'build/optimized-package-progress.json').write_text(json.dumps(archives,indent=2))
        print('Verified ZIP',path.name,flush=True)
    assert len(archives)==len(archive_paths),(len(archives),len(archive_paths))
    report['archives']=archives
    (ROOT/'build/optimized-release.json').write_text(json.dumps(report,indent=2))
    if pcm_zip is not None:pcm_zip.close()
    print(f'PASS all {len(archives)} ZIPs and loose releases updated',flush=True)

if __name__=='__main__':main()
