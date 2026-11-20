"""Require early release, missing release and replacement press to fail in MesenCE."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from verification_data import identity

ROOT=Path(__file__).resolve().parents[1]


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--pack',type=Path,required=True)
    ap.add_argument('--mesen',type=Path,default=Path(r'C:\mesen2\Mesen.exe'))
    ap.add_argument('--level-id',type=int,help='Select a chart inside a master instead of its first entry')
    args=ap.parse_args();pack=args.pack.resolve()
    ids=json.loads((pack/'pack.json').read_text())['levels']
    level=args.level_id or ids[0];local=ids.index(level)+1
    frozen=identity(pack/'adofai.sfc',fresh=True)
    chart=json.loads((pack/f'level{level}.json').read_text())
    template=(pack/f'verification/mesen-{local}/config.lua').read_text()
    assert 'neo_events=' in template
    first=next(n['step'] for n in chart['notes'] if n.get('hold_length',-1)>=0)
    events=[];key=2
    for note in chart['notes'][1:first+1]:
        if note['flags']&8:continue
        key=3-key;events.append([note['frame'],key])
    rows=[]
    for mode in ('early-release','missing-release','press-without-release'):
        out=pack/'verification'/('neo-hold-'+(str(level)+'-' if args.level_id else '')+mode);out.mkdir(parents=True,exist_ok=True)
        inputs=list(events)
        if mode=='early-release':inputs.append([chart['notes'][first]['frame']+3,0])
        if mode=='press-without-release':inputs.append([chart['notes'][first+1]['frame'],3])
        config=re.sub(r'neo_events=\{.*?\}(?=,\w+=|\}\s*$)',
                      'neo_events={'+','.join('{'+','.join(map(str,e))+'}' for e in inputs)+'}',template)
        config=re.sub(r'out="[^"]+"','out='+json.dumps(out.as_posix()),config)
        config=re.sub(r'frames=\d+','frames='+str(chart['notes'][first+1]['frame']+600),config)
        config=config.rstrip()[:-1]+f',neo_failure_step={first},neo_exact_masks=true'+'}\n'
        path=out/'config.lua';path.write_text(config)
        env=dict(os.environ,ADOFAI_TEST_CONFIG=str(path))
        result=subprocess.run([str(args.mesen),'--testrunner','--timeout=90',str(pack/'adofai.sfc'),str(ROOT/'tools/verify_campaign_mesen.lua')],
                              env=env,timeout=100,capture_output=True,text=True,creationflags=subprocess.CREATE_NO_WINDOW)
        (out/'emulator.log').write_text(result.stdout+result.stderr)
        report=(out/'result.txt').read_text()
        assert result.returncode==0 and report.endswith('PASS\n'),(mode,report)
        rows.append(dict(case=mode,result=report));print(mode,'PASS',flush=True)
    assert identity(pack/'adofai.sfc',fresh=True)==frozen
    name='neo-hold-failures'+('-'+str(level) if args.level_id else '')+'.json'
    (pack/'verification'/name).write_text(json.dumps(dict(passed=True,**frozen,level_id=level,cases=rows),indent=2))


if __name__=='__main__':main()
