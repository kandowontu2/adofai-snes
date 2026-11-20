"""Install a verified menu update while retaining identical external game data."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import zipfile

from install_stock_release import copy_file, raw_entry
from verification_data import file_sha256, identity

ROOT = Path(__file__).resolve().parents[1]
META = ('README.txt', 'RELEASE-NOTES.txt', 'verification.json', 'SHA256SUMS.txt')


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def install(pack, previous, folders_only=False):
    frozen = identity(pack/'adofai.sfc', fresh=True)
    original = identity(previous/'adofai.sfc', fresh=True)
    ids = read(pack/'pack.json')['levels']
    assert ids == read(previous/'pack.json')['levels'], 'Menu update changed catalog'
    assert frozen['msu_sha256'] == original['msu_sha256'], 'External data changed'
    proof = read(pack/'menu-data-preservation.json')
    assert proof['passed'] and proof['levels'] == len(ids)
    assert proof['msu_sha256'] == frozen['msu_sha256']
    reports = {}
    checks = ['menu-previews/manifest.json', 'menu-controls/manifest.json',
              'calibration-mesen.json', 'sa1-layout.json', 'snapshot-storage.json',
              'background-final-1/manifest.json']
    for level in (1, 74):
        ordinal = ids.index(level)+1
        checks.extend((f'mesen-{ordinal}/manifest.json',
                       f'mesen-{ordinal}-autoplay/manifest.json',
                       f'mesen-{ordinal}-autoplay/ppu-verification.json'))
    for name in checks:
        report = read(pack/'verification'/name)
        assert report.get('passed') and all(report.get(k) == v for k, v in frozen.items()), name
        reports[name] = report
    preview = reports['menu-previews/manifest.json']
    assert preview['songs'] == len(ids) and preview['return_paths'] == 5
    assert preview['pixels'] and preview['hardware_registers']
    note = (f'ADOFAI SNES - {len(ids)}-chart menu update\n\n'
            'Preview artwork, mapper credits and difficulty remain visible after\n'
            'leaving a song, including retries, Practice and Watch.\n'
            'SELECT opens Options in both set and song menus. B returns from\n'
            'a song list; calibration is under Options > AUDIO OFFSET (press A).\n\n'
            'This update replaces adofai.sfc. The MSU file, music, charts and\n'
            'hybrid PCM tracks are identical to the previous 247-chart release.\n'
            'Full ZIPs include the unchanged MSU file for new installations.\n'
            'The tester update ZIP is ROM-only: keep your existing MSU and PCM.\n\n'
            'Verified in MesenCE: every browser entry, five level-exit paths,\n'
            'actual preview pixels and PPU registers, menu/calibration controls,\n'
            'ROM layout, complete snapshot storage, and targeted manual/Watch\n'
            'gameplay checks. Full catalog replay testing remains in progress.\n'
            'The larger re-import/new-level batch is not part of this package.\n'
            'The previously reported 4.0x audio stress underrun remains unresolved.\n')
    folders = {}
    # Check both installations before changing either one. Never rewrite a
    # multi-gigabyte MSU file when this engine-only update does not need it.
    for edition in ('compressed', 'hybrid'):
        folder = ROOT/'dist'/f'adofai-msu-{edition}'
        assert file_sha256(folder/'adofai.msu') == frozen['msu_sha256'], edition
        assert file_sha256(folder/'adofai.sfc') in (original['rom_sha256'], frozen['rom_sha256']), edition
        assert [r['id'] for r in read(folder/'catalog.json')['levels']] == ids
        folders[edition] = folder
    evidence = dict(passed=True, scope='menu update; external game data preserved',
                    **frozen, world_count=len(ids), reports=reports, hardware_tested=False)
    for edition, folder in folders.items():
        sums = {name: digest for digest, name in
                (line.split('  ', 1) for line in (folder/'SHA256SUMS.txt').read_text().splitlines())}
        sums['adofai.sfc'] = frozen['rom_sha256']
        assert sums['adofai.msu'] == frozen['msu_sha256']
        if file_sha256(folder/'adofai.sfc') != frozen['rom_sha256']:
            copy_file(pack/'adofai.sfc', folder/'adofai.sfc')
        audio = ('Compressed: BRR music throughout; no PCM files.' if edition == 'compressed'
                 else 'Hybrid: PCM music at 1.0x song starts; BRR at checkpoints/other speeds.')
        for name in ('README.txt', 'RELEASE-NOTES.txt'):
            (folder/name).write_text(note+'\n'+audio+'\n')
        (folder/'verification.json').write_text(json.dumps(dict(evidence, edition=edition), indent=2))
        (folder/'SHA256SUMS.txt').write_text(''.join(f'{d}  {n}\n' for n, d in sorted(sums.items())))
        assert file_sha256(folder/'adofai.sfc') == frozen['rom_sha256']
        print('FOLDER UPDATED', edition, frozen['rom_sha256'], flush=True)
    release = ROOT/'dist/RELEASE-NOTES.txt'
    release.write_text(note)
    ledger = dict(passed=True, **frozen, folders={k: str(v) for k, v in folders.items()})
    (pack/'verification/installed-folders.json').write_text(json.dumps(ledger, indent=2))
    if folders_only:
        return
    archives = []
    for edition, folder in folders.items():
        path = folder.with_suffix('.zip')
        temp = path.with_suffix('.zip.new')
        with zipfile.ZipFile(path) as source, zipfile.ZipFile(
                temp, 'w', zipfile.ZIP_DEFLATED, compresslevel=1, allowZip64=True) as dest:
            sums = dict(line.split('  ', 1)[::-1] for line in source.read('SHA256SUMS.txt').decode().splitlines())
            assert sums['adofai.msu'] == frozen['msu_sha256']
            for entry in source.infolist():
                if entry.filename in ('adofai.sfc', *META):
                    dest.write(folder/entry.filename, entry.filename)
                else:
                    raw_entry(source, dest, entry.filename)
        with zipfile.ZipFile(temp) as result:
            assert result.testzip() is None
            for name, key in (('adofai.sfc', 'rom_sha256'), ('adofai.msu', 'msu_sha256')):
                with result.open(name) as data:
                    assert hashlib.file_digest(data, 'sha256').hexdigest() == frozen[key]
            assert len([n for n in result.namelist() if n.endswith('.pcm')]) == (len(ids) if edition == 'hybrid' else 0)
        os.replace(temp, path)
        archives.append(dict(path=str(path), bytes=path.stat().st_size, sha256=file_sha256(path)))
        print('ZIP VERIFIED', edition, flush=True)
    path = ROOT/'dist/adofai-master-tester-update.zip'
    temp = path.with_suffix('.zip.new')
    with zipfile.ZipFile(temp, 'w', zipfile.ZIP_DEFLATED, compresslevel=1) as result:
        result.write(pack/'adofai.sfc', 'adofai.sfc')
        result.writestr('README.txt', note)
        result.writestr('RELEASE-NOTES.txt', note)
        result.writestr('verification.json', json.dumps(evidence, indent=2))
        result.writestr('SHA256SUMS.txt', frozen['rom_sha256']+'  adofai.sfc\n')
    with zipfile.ZipFile(temp) as result:
        assert result.testzip() is None
        assert hashlib.sha256(result.read('adofai.sfc')).hexdigest() == frozen['rom_sha256']
    os.replace(temp, path)
    archives.append(dict(path=str(path), bytes=path.stat().st_size, sha256=file_sha256(path)))
    assert identity(pack/'adofai.sfc', fresh=True) == frozen
    (pack/'verification/installed-release.json').write_text(json.dumps(dict(ledger, archives=archives), indent=2))
    print('BOTH FOLDERS AND THREE ZIPS UPDATED', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pack', default='menu-navigation-master')
    parser.add_argument('--previous-pack', default='phantigma-master')
    parser.add_argument('--folders-only', action='store_true')
    args = parser.parse_args()
    install(ROOT/'build/packs'/args.pack, ROOT/'build/packs'/args.previous_pack, args.folders_only)
