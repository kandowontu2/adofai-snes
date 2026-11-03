"""Publish independently verified hybrid and compressed installed-size editions."""
import json,hashlib,zipfile
from pathlib import Path
from package_graphics_update import bound,graphics,copy,sha
from package_standalone import archive
from verification_data import identity
ROOT=Path(__file__).resolve().parents[1]

def main():
    ledger=[]
    for mode in ('compressed','hybrid'):
        base=ROOT/f'build/packs/sa1-renderer-{mode}';current=identity(base/'adofai.sfc')
        pixels=graphics(base.name,[1]);assert len(pixels)==65
        routes=bound(base/'verification/audio-routing.json',current)
        feedback=bound(base/'verification/manual-feedback-25-10.json',current)
        assert feedback['max_delay_frames']<=1
        audio=bound(ROOT/f'build/renderer-{mode}-cetx31-audio/audio-check.json',current)
        assert abs(audio['drift_ms'])<20 and min(r['correlation'] for r in audio['windows'])>.9
        checks=[]
        for folder in ['mesen-61',*[f'mesen-checkpoints-{n}' for n in (25,31,45,63)]]:
            path=base/'verification'/folder
            assert (path/'result.txt').read_text().endswith('PASS\n')
            checks.append(bound(path/'ppu-verification.json',current))
        names=['adofai.sfc','adofai.msu']+([f'adofai-{n}.pcm' for n in range(1,66)] if mode=='hybrid' else [])
        assert {p.name for p in base.glob('*.pcm')}==set(names[2:])
        files=[dict(file=n,bytes=(base/n).stat().st_size,sha256=sha(base/n)) for n in names]
        size=sum(r['bytes'] for r in files)
        destination=ROOT/f'dist/adofai-msu-{mode}';destination.mkdir(exist_ok=True)
        assert not [p for p in destination.glob('*.pcm') if p.name not in names], 'Unexpected PCM files would change audio routing'
        for n in names:copy(base/n,destination/n)
        description=('Full-quality 44.1 kHz stereo PCM at 1.0x from the start of a song.\nCheckpoint retries and other speeds use 12 kHz mono SNES BRR audio.' if mode=='hybrid' else 'All music uses 12 kHz mono SNES BRR audio at every speed.\nNo PCM files are required. This deliberately reduces fidelity.')
        note=f'''ADOFAI SNES - {mode.upper()} MASTER

65 charts, including Mad Piano Party II, Feral Easy/Medium and OOPARTS Nerfed.
{description}
Installed game files: {size:,} bytes ({size/2**20:.2f} MiB).

Extract into a NEW, SEPARATE folder and open adofai.sfc in an emulator
supporting SA-1 and MSU-1 together (tested with MesenCE and Snes9x).
Keep adofai.msu beside the ROM. Do not add checkpoint PCM files from the
full edition: their presence would switch checkpoint audio back to PCM.
The compressed edition must have no PCM files beside the ROM.
This edition does not require a converter or a full master download.

The same levels, checkpoints, controls and renderer are retained.
Original Mad Piano Party is FT11-X / Tech 08. OOPARTS is Lupel_2's version.
Authored zoom is enabled only in XN-X, XS-X, AR-X and Turkish March.
Mad Piano Party II uses fixed zoom and reduced texture resolution;
its densest transitions still stutter. Dense levels are not locked to 60 FPS.
Hardware has not been tested. See verification.json for exact test scope.
'''
        report=dict(passed=True,**current,edition=mode,world_count=65,installed_game_bytes=size,files=files,ppu_replays=pixels,audio_routing=routes,cetx_audio=audio,manual_feedback=feedback,mesen_checks=checks,hardware_tested=False)
        (destination/'README.txt').write_text(note)
        (destination/'verification.json').write_text(json.dumps(report,indent=2))
        (destination/'SHA256SUMS.txt').write_text(''.join(r['sha256']+'  '+r['file']+'\n' for r in files))
        target=destination.with_suffix('.zip')
        archive(target,[(destination/n,n) for n in [*names,'README.txt','verification.json','SHA256SUMS.txt']])
        with zipfile.ZipFile(target) as z:
            assert len(z.namelist())==len(set(z.namelist()))
            for r in files:
                with z.open(r['file']) as f:assert hashlib.file_digest(f,'sha256').hexdigest()==r['sha256']
        ledger.append(dict(edition=mode,installed_bytes=size,archive_bytes=target.stat().st_size,archive_sha256=sha(target),**current))
        print('PASS',mode,ledger[-1],flush=True)
    (ROOT/'build/small-master-release.json').write_text(json.dumps(dict(passed=True,editions=ledger),indent=2))

if __name__=='__main__':main()
