"""Capture every T3 stage heading in MesenCE, including the track-copy exit."""
import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from make_assets import FPS
from neo_visuals import chapter_time
from run_mesen_campaign import suite_digest
from verification_data import identity

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pack',required=True)
    args=parser.parse_args()
    base=ROOT/'build/packs'/args.pack
    # VFX verification also replays T3 with VFX off. Give these explicit
    # heading captures their own pack/output directory so parallel runs
    # cannot clear one another's screenshots or overwrite config.lua.
    isolated=base.with_name(base.name+'-heading-check')
    isolated.mkdir(exist_ok=True)
    for source in base.iterdir():
        if not source.is_file() or source.suffix in ('.tmp','.new','.pcm'):continue
        destination=isolated/source.name
        if destination.exists():
            if os.path.samefile(source,destination):continue
            destination.unlink()
        os.link(source,destination)
    levels=json.loads((base/'pack.json').read_text())['levels']
    frozen=identity(base/'adofai.sfc');suite=suite_digest();rows=[]
    for level in (68,73):
        if level not in levels:continue
        chart=json.loads((base/f'level{level}.json').read_text())
        commands=chart['mawaru_headings'];assert len(commands)==19
        assert commands[1]['text']=='Holds & midspins!!'
        assert not chart.get('vfx_off'),'T3 gameplay headings must not be optional'
        local=levels.index(level)+1
        times=[round(chapter_time(chart,c['beat']+.75)*FPS) for c in commands]
        times.append(round(chapter_time(chart,853)*FPS))
        subprocess.run([sys.executable,str(ROOT/'tools/run_mesen_campaign.py'),
                        '--pack',isolated.name,'--levels',str(local),'--autoplay','--vfx-off',
                        '--sampled-graphics','--capture-times',*map(str,times)],cwd=ROOT,check=True)
        folder=isolated/f'verification/mesen-{local}-autoplay-vfx-off'
        subprocess.run([sys.executable,str(ROOT/'tools/verify_mesen_ppu.py'),
                        '--pack',isolated.name,'--level',str(local),'--folder',str(folder)],cwd=ROOT,check=True)
        captures=[folder/f'screen-{t}.png' for t in times]
        assert all(p.is_file() for p in captures),'Missing stage heading captures'
        retained=base/f'verification/neo-heading-{level}'
        retained.mkdir(exist_ok=True)
        for source in captures:shutil.copyfile(source,retained/source.name)
        captures=[retained/p.name for p in captures]
        rows.append(dict(id=level,headings=19,captures=20,vfx_off=True,
                         ampersand_capture=str(captures[1].relative_to(base)),
                         copy_section_capture=str(captures[-1].relative_to(base))))
    assert identity(base/'adofai.sfc')==frozen and suite_digest()==suite
    (base/'verification/neo-headings.json').write_text(json.dumps(
        dict(passed=True,**frozen,suite_digest=suite,cases=rows),indent=2))
    print('T3/T3-EX: all native headings captured with VFX off',flush=True)


if __name__=='__main__':main()
