"""Install verified hybrid/compressed catalogs and their three archives."""
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
    parser.add_argument('--audio-source',type=Path,help='Separately verified refreshed song-start PCM, without another full PCM master')
    args=parser.parse_args();BASE=ROOT/'build/packs'/args.pack;V=BASE/'verification'
    frozen=identity(BASE/'adofai.sfc',fresh=True);pack=read(BASE/'pack.json');ids=pack['levels']
    assert ids and len(set(ids))==len(ids)
    reports={};folders_only=args.folders_only
    names=('sa1-layout.json','chaos-performance.json') if folders_only else ('catalog/results.json','release-gates.json','sa1-layout.json','chaos-performance.json')
    for name in names:
        d=read(V/name);assert d.get('passed') and all(d.get(k)==v for k,v in frozen.items()),name;reports[name]=d
    if folders_only:
        for local in range(1,len(ids)+1):
            p=V/f'mesen-{local}-autoplay/manifest.json';d=read(p)
            assert d.get('passed') and all(d.get(k)==v for k,v in frozen.items()),str(p)
        reports['catalog_replays']={'passed':True,'count':len(ids),'final_release_regressions':'in progress'}
    else:
        assert reports['release-gates.json']['catalog']==len(ids)
        assert [r['id'] for r in reports['catalog/results.json']['results']]==ids
    hybrid=DIST/'adofai-msu-hybrid';hybrid.mkdir(exist_ok=True)
    pcm_path=BASE/'pcm-manifest.json'
    pcm=read(pcm_path if pcm_path.exists() else hybrid/'pcm-manifest.json')
    assert [r['id'] for r in pcm]==ids
    main_tracks={f'adofai-{n}.pcm' for n in ids}
    update_tracks={f'adofai-{n}.pcm' for n in pack.get('updated_audio_levels',[]) if n in ids}
    # Check both destinations before replacing either ROM/data pair or
    # refreshing audio. A live emulator can otherwise leave a mixed build.
    for edition in ('compressed','hybrid'):
        for name,key in (('adofai.msu','msu_sha256'),('adofai.sfc','rom_sha256')):
            current=DIST/f'adofai-msu-{edition}'/name
            if current.exists() and file_sha256(current)!=frozen[key]:
                try:
                    with current.open('r+b'):pass
                except PermissionError as error:
                    raise PermissionError(f'Close the emulator using {current} before installing this build') from error
    for name in sorted(main_tracks):
        source=BASE/name;target=hybrid/name
        if args.audio_source and (args.audio_source/name).exists():source=args.audio_source/name
        if source.exists() and (not target.exists() or file_sha256(source)!=file_sha256(target)):
            copy_file(source,target)
        assert target.is_file(),('Missing hybrid song-start audio',name)
    # Checkpoint PCM is no longer distributed. Hybrid retries use BRR.
    pcm=[dict(row,tracks=[t for t in row['tracks'] if t['track']==row['id']]) for row in pcm]
    assert all(len(row['tracks'])==1 for row in pcm)
    (hybrid/'pcm-manifest.json').write_text(json.dumps(pcm,indent=2))
    catalog={'levels':[{k:c[k] for k in ('id','code','title')} for c in read(BASE/'msu-manifest.json')['levels']]}
    note=(BASE/'release-notes.txt').read_text() if (BASE/'release-notes.txt').exists() else 'ADOFAI SNES - verified hybrid and compressed release.\n'
    evidence=dict(passed=True,**frozen,world_count=len(ids),reports=reports,hardware_tested=False)
    hashes={n:file_sha256(hybrid/n) for n in sorted(main_tracks)};ledger=[]
    meta=['catalog.json','README.txt','RELEASE-NOTES.txt','verification.json','SHA256SUMS.txt']
    for edition,tracks in [('hybrid',main_tracks),('compressed',set())]:
        target=DIST/f'adofai-msu-{edition}';target.mkdir(exist_ok=True)
        for name,key in [('adofai.sfc','rom_sha256'),('adofai.msu','msu_sha256')]:
            current=target/name
            if not (current.exists() and current.stat().st_size==(BASE/name).stat().st_size and file_sha256(current)==frozen[key]):
                copy_file(BASE/name,current)
        print('CORE INSTALLED',edition,flush=True)
        for p in target.glob('adofai-*.pcm'):
            if re.fullmatch(r'adofai-\d+\.pcm',p.name) and p.name not in tracks:p.unlink()
        audio={'hybrid':'PCM music at 1.0x from song start; BRR at checkpoints and other speeds.',
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
        print('HYBRID AND COMPRESSED FOLDERS UPDATED; ARCHIVES PENDING',flush=True);return
    archive=DIST/'adofai-msu-hybrid.zip';temp=archive.with_suffix('.zip.new');previous=None;prior_hashes={}
    if archive.exists():
        try:
            previous=zipfile.ZipFile(archive)
            prior_hashes={name:digest for digest,name in (line.split('  ',1) for line in previous.read('SHA256SUMS.txt').decode().splitlines())}
        except (OSError,KeyError,ValueError,UnicodeError,zipfile.BadZipFile):
            if previous:previous.close()
            previous=None
    try:
        reused=0
        with zipfile.ZipFile(temp,'w',zipfile.ZIP_DEFLATED,compresslevel=1,allowZip64=True) as z:
            for n in ['adofai.sfc','adofai.msu',*meta,*sorted(main_tracks)]:
                if previous and n in hashes and prior_hashes.get(n)==hashes[n] and n in previous.NameToInfo:
                    raw_entry(previous,z,n);reused+=1
                else:z.write(hybrid/n,n)
            print('HYBRID ZIP WRITTEN;',reused,'unchanged song entries reused',flush=True)
    finally:
        if previous:previous.close()
    def verify_zip(path):
        with zipfile.ZipFile(path) as z:
            assert z.testzip() is None
            for n,key in [('adofai.sfc','rom_sha256'),('adofai.msu','msu_sha256')]:
                with z.open(n) as f:assert hashlib.file_digest(f,'sha256').hexdigest()==frozen[key]
    verify_zip(temp);os.replace(temp,archive);archives=[archive]
    with zipfile.ZipFile(archive) as source:
        for edition,tracks,path in [('compressed',set(),DIST/'adofai-msu-compressed.zip'),('tester',update_tracks,DIST/'adofai-master-tester-update.zip')]:
            folder=DIST/'adofai-msu-compressed' if edition=='compressed' else hybrid
            temp=path.with_suffix('.zip.new')
            with zipfile.ZipFile(temp,'w',zipfile.ZIP_DEFLATED,compresslevel=1,allowZip64=True) as z:
                for n in ['adofai.sfc','adofai.msu',*sorted(tracks)]:raw_entry(source,z,n)
                for n in meta:
                    if edition=='tester' and n=='SHA256SUMS.txt':
                        selected={'adofai.sfc','adofai.msu',*tracks}
                        z.writestr(n,''.join(line+'\n' for line in (folder/n).read_text().splitlines() if line.split('  ',1)[1] in selected))
                    else:z.write(folder/n,n)
            verify_zip(temp);os.replace(temp,path);archives.append(path);print('ZIP VERIFIED',edition,flush=True)
    assert identity(BASE/'adofai.sfc',fresh=True)==frozen
    (DIST/'RELEASE-NOTES.txt').write_text(note)
    (V/'installed-release.json').write_text(json.dumps(dict(passed=True,**frozen,folders=ledger,archives=[dict(path=str(p),bytes=p.stat().st_size,sha256=file_sha256(p)) for p in archives]),indent=2))
    print('HYBRID AND COMPRESSED FOLDERS AND THREE ZIPS UPDATED',flush=True)
if __name__=='__main__':main()
