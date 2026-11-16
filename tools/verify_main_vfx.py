"""Paired main-world scenery measurements, real controller input and PPU checks."""
import argparse,concurrent.futures,json,re,struct,subprocess,sys
from pathlib import Path
from verification_data import identity,file_sha256
from main_vfx_assets import STATIC_LEVELS
ROOT=Path(__file__).resolve().parents[1]

def verify(name,workers=4,levels=tuple(range(1,13)),pcm_report_for=None):
    base=ROOT/'build/packs'/name;frozen=identity(base/'adofai.sfc')
    if pcm_report_for:
        target=ROOT/'build/packs'/pcm_report_for
        assert identity(target/'adofai.sfc')==frozen,'PCM and compressed test ROMs differ'
        for n in levels:
            with (base/f'adofai-{n}.pcm').open('rb') as f:assert f.read(4)==b'MSU1'
    out=base/'verification/main-vfx';out.mkdir(parents=True,exist_ok=True)
    def run(level,off,watch):
        suffix=('-autoplay' if watch else '')+('-vfx-off' if off else '')+'-paired-vfx'
        with (out/f'{level}{suffix}.log').open('w') as log:
            def tool(script,*args):
                subprocess.run([sys.executable,str(ROOT/'tools'/script),*map(str,args)],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True)
            args=['--pack',name,'--levels',level,'--sampled-graphics','--resume','--paired-vfx']
            if off:args+=['--vfx-off']
            if watch:args+=['--autoplay']
            tool('run_mesen_campaign.py',*args)
            folder=base/f'verification/mesen-{level}{suffix}'
            tool('verify_mesen_ppu.py','--pack',name,'--level',level,'--folder',folder)
            manifest=json.loads((folder/'manifest.json').read_text())
            assert manifest['passed'] and all(manifest[k]==v for k,v in frozen.items())
            chr=(base/('background.chr' if off else f'main_vfx_chr{level}.bin')).read_bytes()
            tilemap=(base/('background.map' if off else f'main_vfx_map{level}.bin')).read_bytes()
            if off:tilemap=b''.join(struct.pack('<H',v+80) for (v,) in struct.iter_unpack('<H',tilemap))
            dumps=list(folder.glob('ppu-*.bin'));assert dumps
            for dump in dumps:
                vram=dump.read_bytes()[272:272+65536]
                assert vram[0xAA00:0xAA00+len(chr)]==chr,(dump,'scenery CHR changed')
                assert vram[0xB800:0xC000]==tilemap,(dump,'scenery map changed')
            screen=(folder/'screen-registers.txt').read_text()
            windows=0
            if not off and level not in STATIC_LEVELS:
                budget=(folder/'main-vfx-budget.txt').read_text()
                assert budget.startswith('PASS idle_windows='),budget
                windows=int(budget.split('=')[1]);assert windows>100
            return dict(level=level,vfx=not off,watch=watch,
                        verified_idle_windows=windows,
                        samples=int(re.search(r'samples=(\d+)',screen)[1]),
                        missed_presentations=int(re.search(r'missed_presentations=(\d+)',screen)[1]),
                        settled_missed=int(re.search(r'settled_missed=(\d+)',screen)[1]),
                        max_frame_gap=int(re.search(r'max_frame_gap=(\d+)',screen)[1]))
    rows=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        jobs=[pool.submit(run,n,off,watch) for n in levels for off in (False,True) for watch in (False,True)]
        for job in concurrent.futures.as_completed(jobs):
            row=job.result();rows.append(row);print(row,flush=True)
    for n in levels:
        subprocess.run([sys.executable,'tools/verify_background_vram_mesen.py','--pack',name,'--levels',str(n),'--tag','main-vfx'],cwd=ROOT,check=True)
    regressions=[]
    for n in levels:
        for watch in (False,True):
            pair={r['vfx']:r for r in rows if r['level']==n and r['watch']==watch}
            if any(pair[True][k]>pair[False][k] for k in ('max_frame_gap','missed_presentations','settled_missed')):
                regressions.append(dict(level=n,watch=watch,on=pair[True],off=pair[False]))
    assert identity(base/'adofai.sfc')==frozen
    report=dict(passed=not regressions,**frozen,levels=list(levels),cases=rows,regressions=regressions,
                note='No increase in maximum gap or missed presentations, including startup; this does not prove every frame on hardware.')
    filename='main-vfx-performance.json' if list(levels)==list(range(1,13)) else 'main-vfx-probe.json'
    (base/'verification'/filename).write_text(json.dumps(report,indent=2))
    if pcm_report_for:
        report.update(audio='PCM',pcm_sha256={str(n):file_sha256(base/f'adofai-{n}.pcm') for n in levels})
        assert identity(target/'adofai.sfc')==frozen
        (target/'verification/main-vfx-pcm-performance.json').write_text(json.dumps(report,indent=2))
    assert not regressions,regressions

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--pack',required=True);p.add_argument('--workers',type=int,default=4);p.add_argument('--levels',type=int,nargs='+',default=list(range(1,13)));p.add_argument('--pcm-report-for',help='Attach PCM evidence to an identical compressed test pack');a=p.parse_args();verify(a.pack,a.workers,a.levels,a.pcm_report_for)
