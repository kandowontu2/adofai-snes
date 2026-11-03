"""Publish a ROM-only autoplay-clock correction for dataset-20 masters."""
import json,hashlib,zipfile
from pathlib import Path
from package_graphics_update import copy,bound,sha
from package_standalone import archive
from verification_data import identity
ROOT=Path(__file__).resolve().parents[1]
def main():
    base=ROOT/'build/packs/sa1-autoplay-audio-fix';current=identity(base/'adofai.sfc')
    phase=json.loads((base/'verification/autoplay-alignment.json').read_text());assert phase['passed']
    for case in phase['cases']:assert all(case[k]==v for k,v in current.items())
    pixels=[]
    for n in (25,31):
        for suffix in ('','-speed-20'):
            row=bound(base/f'verification/render-{n}{suffix}.json',current)
            assert row['completed_song'] and row['ppu_chr_match'] and row['cache_capacity_errors']==row['vblank_overruns']==0
            pixels.append(row)
    mesen=bound(base/'verification/mesen-25-autoplay/ppu-verification.json',current)
    assert (base/'verification/mesen-25-autoplay/result.txt').read_text().endswith('PASS\n')
    manual=bound(base/'verification/manual-feedback-25-10.json',current)
    assert manual['max_delay_frames']<=1
    assert '[(-8, 167), (0, 167), (8, 167)]' in (ROOT/'build/autoplay-fix-manual-calibration.log').read_text()
    out=ROOT/'dist/adofai-autoplay-audio-fix';out.mkdir(exist_ok=True)
    copy(base/'adofai.sfc',out/'adofai.sfc')
    note='''ADOFAI - autoplay audio timing fix

Close the running game, replace adofai.sfc in your current 65-chart master
folder with this ROM, then reopen it. Keep your existing adofai.msu and
any PCM files. Compatible with compressed, hybrid and full dataset-20
masters using the MSU SHA256 listed below. Do not apply to standalone ROMs
or the single-song OOPARTS package. Start fresh rather than loading a state.

Autoplay now uses the raw music clock. Previously the manual calibration
baseline delayed autoplay by 8 frames (about 133 ms) at displayed zero.
Manual calibration values and manual tap feedback are unchanged.
This corrects the demonstrated autoplay phase error; it does not establish
that every remaining manual-play or device-output latency issue is resolved.
Restore your previous emulator audio buffer if lowering it caused pops.

The large distribution ZIPs retain the previous release; apply this small
update after extracting one of those packages.
Required adofai.msu SHA256: '''+current['msu_sha256']+'\n'
    (out/'README.txt').write_text(note)
    report=dict(passed=True,**current,autoplay_phase=phase,graphics=pixels,mesen=mesen,manual_feedback=manual,manual_calibration_checks=[-8,0,8])
    (out/'verification.json').write_text(json.dumps(report,indent=2))
    (out/'SHA256SUMS.txt').write_text(current['rom_sha256']+'  adofai.sfc\n')
    target=ROOT/'dist/adofai-autoplay-audio-fix.zip'
    archive(target,[(out/n,n) for n in ('adofai.sfc','README.txt','verification.json','SHA256SUMS.txt')])
    with zipfile.ZipFile(target) as z:assert hashlib.sha256(z.read('adofai.sfc')).hexdigest()==current['rom_sha256']
    (ROOT/'build/autoplay-audio-release.json').write_text(json.dumps(dict(passed=True,**current,archive_bytes=target.stat().st_size,archive_sha256=sha(target)),indent=2))
    print('PASS',target,target.stat().st_size)
if __name__=='__main__':main()
