"""Profile real input motion, also rejecting detached midspin planet pivots.

Accepts the same arguments as profile_ar_section_mesen.py. With --manual,
requires the replay to exercise at least one waiting midspin transition.
"""
import json
from pathlib import Path
import re
import subprocess
import sys

import profile_ar_section_mesen as profile


def main():
    args=sys.argv[1:]
    def option(name):return args[args.index(name)+1]
    rom=Path(option('--rom'));labels=Path(option('--labels'));out=Path(option('--out'));level=int(option('--level'))
    metadata=Path(option('--metadata')) if '--metadata' in args else rom.parent
    chart=json.loads((metadata/f'level{level}.json').read_text());levels=json.loads((metadata/'pack.json').read_text())['levels']
    symbols={n:int(v,16) for v,n in re.findall(r'al ([0-9a-fA-F]+) \.([\w]+)',labels.read_text())}
    symbols.setdefault('m7_visual_step',symbols['cell_hash_dirty']);symbols.setdefault('m7_logical_step',symbols['cell_hash_bucket'])
    root=Path(__file__).resolve().parents[1];original=subprocess.run
    def instrument(command,*pos,**kw):
        if Path(command[0]).name.lower()=='mesen.exe':
            path=Path(command[-1]);code=path.read_text();folder=out.resolve().as_posix()
            pre='dofile('+json.dumps((root/'tools/mesen_failfast.lua').as_posix())+')({out='+json.dumps(folder)+'})\n'
            oracle='dofile('+json.dumps((root/'tools/verify_midspin_pose_mesen.lua').as_posix())+')({out='+json.dumps(folder)+',level='+str(levels.index(level)+1)+',addr={'+','.join(n+'='+str(symbols[n]) for n in ('state','step','selected_level'))+'},midspin={entry='+str(symbols['neo_far_prepare_hold'])+',addr={'+','.join(n+'='+str(symbols[n]) for n in ('m7_visual_step','m7_logical_step','chart_time'))+'},flags={'+','.join(str(n['flags']) for n in chart['notes'])+'},times={'+','.join(str(n['frame']) for n in chart['notes'])+'}}})\n'
            path.write_text(pre+code+'\n'+oracle)
        return original(command,*pos,**kw)
    subprocess.run=instrument
    try:profile.main()
    finally:subprocess.run=original
    text=(out/'midspin-poses.txt').read_text();samples,virtual=map(int,re.findall(r'\d+',text))
    assert samples>100,text
    if '--manual' in args:assert virtual>0,'Replay did not exercise a waiting midspin'
    result=json.loads((out/'result.json').read_text());result.update(midspin_pose_samples=samples,waiting_midspin_samples=virtual)
    (out/'result.json').write_text(json.dumps(result,indent=2));print(text)


if __name__=='__main__':main()
