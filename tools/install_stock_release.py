"""Install a verified catalog and all four master archives."""
import argparse,copy,hashlib,json,os,re,shutil,struct,zipfile,sys
from pathlib import Path
from verification_data import identity,file_sha256
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'build/packs/stock-refresh-master'
DIST=ROOT/'dist'
V=BASE/'verification'
def read(p):return json.loads(p.read_text())
def copy_file(src,dst):
    tmp=dst.with_name(dst.name+'.new');shutil.copyfile(src,tmp);os.replace(tmp,dst)
def raw_entry(source,output,name):
    old=source.getinfo(name);entry=copy.copy(old);entry.header_offset=output.start_dir;entry.flag_bits &= ~8
    output.fp.seek(output.start_dir)
    output.fp.write(entry.FileHeader(zip64=max(entry.file_size,entry.compress_size)>=zipfile.ZIP64_LIMIT))
    source.fp.seek(old.header_offset)
    h=struct.unpack('<4s5H3I2H',source.fp.read(30));assert h[0]==b'PK\x03\x04'
    source.fp.seek(h[-2]+h[-1],1);left=old.compress_size
    while left:
        block=source.fp.read(min(left,4*1024*1024));assert block;output.fp.write(block);left-=len(block)
    output.start_dir=output.fp.tell();output.filelist.append(entry);output.NameToInfo[name]=entry;output._didModify=True
def main():
    global BASE,V
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pack',default='stock-refresh-master')
    parser.add_argument('--folders-only',action='store_true')
    args=parser.parse_args();BASE=ROOT/'build/packs'/args.pack;V=BASE/'verification'
    frozen=identity(BASE/'adofai.sfc');pack=read(BASE/'pack.json');ids=pack['levels'];assert ids and len(set(ids))==len(ids)
    reports={}
    folders_only=args.folders_only
    for name in (('sa1-layout.json','chaos-performance.json') if folders_only else ('catalog/results.json','release-gates.json','sa1-layout.json','chaos-performance.json')):
        d=read(V/name);assert d.get('passed') and all(d.get(k)==v for k,v in frozen.items()),name;reports[name]=d
    if folders_only:
        for local in range(1,len(ids)+1):
            p=V/f'mesen-{local}-autoplay/manifest.json';d=read(p)
            assert d.get('passed') and all(d.get(k)==v for k,v in frozen.items()),str(p)
        reports['catalog_replays']={'passed':True,'count':len(ids),'final_release_regressions':'in progress'}
    if not folders_only:
        assert reports['release-gates.json']['catalog']==len(ids)
        assert [r['id'] for r in reports['catalog/results.json']['results']]==ids
    full=DIST/'adofai-msu-master'
    pcm_path=BASE/'pcm-manifest.json'
    pcm=read(pcm_path if pcm_path.exists() else full/'pcm-manifest.json');assert [r['id'] for r in pcm]==ids
    full_tracks={f'adofai-{t["track"]}.pcm' for r in pcm for t in r['tracks']}
    main_tracks={f'adofai-{n}.pcm' for n in ids}
    update_tracks={f'adofai-{t["track"]}.pcm' for r in pcm if r['id'] in pack.get('updated_audio_levels',(53,251,252)) for t in r['tracks']}
    for name in sorted(full_tracks):
        source=BASE/name
        if source.exists() and (not (full/name).exists() or file_sha256(source)!=file_sha256(full/name)):
            copy_file(source,full/name)
    if pcm_path.exists():copy_file(pcm_path,full/'pcm-manifest.json')
    assert all((full/n).is_file() for n in full_tracks)
    catalog={'levels':[{k:c[k] for k in ('id','code','title')} for c in read(BASE/'msu-manifest.json')['levels']]}
    note='''ADOFAI SNES - 2026-11-15, dataset 32, 202 charts
Updated stock camera/event imports, retained Yangsy selection and gem platforms.
Watch/Practice/Normal persists when leaving a level.
Featured endless.reality has no rotating red bar; Community 2022 has its own maze.
Added CC-X CHAOS CONTROL with optional optimized scenery (Options: VFX).
Removed the experimental main-world backgrounds and palette animation.
6-EX's two intentionally hidden late midspins retain their original behavior.
VFX OFF retains gameplay cues and never disables T3-X/EX gameplay effects.
Updated contributor objects, free-roam graphics and red/blue twirl palettes.
Corrected moving-track coordinate publication and missing custom track images.
Restored FC06-1 opening, FC06-6 bridges, FC08-3 frames, 3-EX replacement
U-turn graphics and 10-EX custom platforms. Corrected 9-EX moving-track anchors.
Fixed stale blank graphics when switching between 4-bit and 8-bit atlases.
Mad Piano Party II checkpoint retries verified at both supplemental checkpoints.
MesenCE tested. Dense scenes can still stutter; not a locked-60-fps guarantee.
Replace BOTH adofai.sfc and adofai.msu together. Saves are not removed.
Legacy self-contained standalone cartridges are unchanged by this master release.
'''
    if (BASE/'release-notes.txt').exists():note=(BASE/'release-notes.txt').read_text()
    evidence=dict(passed=True,**frozen,world_count=len(ids),reports=reports,hardware_tested=False)
    installed=V/'installed-folders.json'
    reuse_installed=not folders_only and installed.exists() and all(read(installed).get(k)==v for k,v in frozen.items())
    if reuse_installed:
        reuse_installed=all(identity(DIST/f'adofai-msu-{edition}'/'adofai.sfc')==frozen
                            for edition in ('master','hybrid','compressed'))
    # Install the paired core files first so the requested folders are ready
    # while the much larger audio inventory is being checked.
    for edition in ('master','hybrid','compressed'):
        target=DIST/f'adofai-msu-{edition}';target.mkdir(exist_ok=True)
        if not reuse_installed:
            for name in ('adofai.sfc','adofai.msu'):copy_file(BASE/name,target/name)
        print('CORE INSTALLED',edition,flush=True)
    hashes={n:file_sha256(full/n) for n in sorted(full_tracks)}
    ledger=[]
    meta=['catalog.json','README.txt','RELEASE-NOTES.txt','verification.json','SHA256SUMS.txt']
    for edition,tracks in [('master',full_tracks),('hybrid',main_tracks),('compressed',set())]:
        target=DIST/f'adofai-msu-{edition}';target.mkdir(exist_ok=True)
        for name in sorted(tracks):
            if target!=full and not reuse_installed:copy_file(full/name,target/name)
        # Only numbered audio payloads are removed; saves and user files remain.
        for p in target.glob('adofai-*.pcm'):
            if re.fullmatch(r'adofai-\d+\.pcm',p.name) and p.name not in tracks:p.unlink()
        audio={'master':'PCM music at 1.0x, including checkpoint entries. BRR at other speeds.',
               'hybrid':'PCM music at 1.0x from song start; BRR at checkpoints and other speeds.',
               'compressed':'BRR music throughout. Keep this edition free of PCM files.'}[edition]
        (target/'catalog.json').write_text(json.dumps(catalog,indent=2))
        for name in ('README.txt','RELEASE-NOTES.txt'):(target/name).write_text(note+'\n'+audio+'\n')
        (target/'verification.json').write_text(json.dumps(dict(evidence,edition=edition),indent=2))
        expected={'adofai.sfc':frozen['rom_sha256'],'adofai.msu':frozen['msu_sha256'],**{n:hashes[n] for n in tracks}}
        for n,digest in expected.items():assert file_sha256(target/n)==digest,(edition,n)
        (target/'SHA256SUMS.txt').write_text(''.join(f'{d}  {n}\n' for n,d in sorted(expected.items())))
        ledger.append(dict(edition=edition,folder=str(target),game_files=len(expected)))
        print('INSTALLED',edition,len(expected),'verified files',flush=True)
    if folders_only:
        (V/'installed-folders.json').write_text(json.dumps(dict(passed=True,**frozen,folders=ledger),indent=2))
        print('ALL THREE FOLDERS UPDATED; ARCHIVES PENDING',flush=True)
        return
    fullzip=full/'adofai-msu-master.zip';temp=fullzip.with_suffix('.zip.new')
    previous=None;previous_hashes={}
    if fullzip.exists():
        try:
            previous=zipfile.ZipFile(fullzip)
            previous_hashes={name:digest for digest,name in
                             (line.split('  ',1) for line in previous.read('SHA256SUMS.txt').decode().splitlines())}
        except (OSError,KeyError,ValueError,UnicodeError,zipfile.BadZipFile):
            if previous:previous.close()
            previous=None
    try:
        reused=0
        with zipfile.ZipFile(temp,'w',zipfile.ZIP_DEFLATED,compresslevel=1,allowZip64=True) as z:
            for n in ['adofai.sfc','adofai.msu',*meta,*sorted(full_tracks)]:
                # Reuse only unchanged PCM payloads. The paired engine/data
                # and release metadata are always written from this build.
                if previous and n in hashes and previous_hashes.get(n)==hashes[n] and n in previous.NameToInfo:
                    raw_entry(previous,z,n);reused+=1
                else:z.write(full/n,n)
            print('FULL ZIP WRITTEN;',reused,'unchanged audio entries reused',flush=True)
    finally:
        if previous:previous.close()
    with zipfile.ZipFile(temp) as z:assert z.testzip() is None
    os.replace(temp,fullzip)
    archives=[fullzip]
    with zipfile.ZipFile(fullzip) as source:
        for edition,tracks,path in [('hybrid',main_tracks,DIST/'adofai-msu-hybrid.zip'),('compressed',set(),DIST/'adofai-msu-compressed.zip'),('tester',update_tracks,DIST/'adofai-master-tester-update.zip')]:
            folder=DIST/f'adofai-msu-{edition}' if edition!='tester' else full
            temp=path.with_suffix('.zip.new')
            with zipfile.ZipFile(temp,'w',zipfile.ZIP_DEFLATED,compresslevel=1,allowZip64=True) as z:
                for n in ['adofai.sfc','adofai.msu',*sorted(tracks)]:raw_entry(source,z,n)
                for n in meta:
                    if edition=='tester' and n=='SHA256SUMS.txt':
                        selected={'adofai.sfc','adofai.msu',*tracks}
                        z.writestr(n,''.join(line+'\n' for line in (folder/n).read_text().splitlines() if line.split('  ',1)[1] in selected))
                    else:z.write(folder/n,n)
            with zipfile.ZipFile(temp) as z:
                assert z.testzip() is None
                for n,key in [('adofai.sfc','rom_sha256'),('adofai.msu','msu_sha256')]:
                    with z.open(n) as f:assert hashlib.file_digest(f,'sha256').hexdigest()==frozen[key]
            os.replace(temp,path);archives.append(path);print('ZIP VERIFIED',edition,flush=True)
    (DIST/'RELEASE-NOTES.txt').write_text(note)
    (V/'installed-release.json').write_text(json.dumps(dict(passed=True,**frozen,folders=ledger,archives=[dict(path=str(p),bytes=p.stat().st_size,sha256=file_sha256(p)) for p in archives]),indent=2))
    print('ALL THREE FOLDERS AND FOUR ZIPS UPDATED',flush=True)
if __name__=='__main__':main()
