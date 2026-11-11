"""Require early release, missing release and replacement press to fail in MesenCE."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

ROOT=Path(__file__).resolve().parents[1]


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--pack',type=Path,required=True)
    ap.add_argument('--mesen',type=Path,default=Path(r'C:\mesen2\Mesen.exe'))
    args=ap.parse_args();pack=args.pack.resolve()
    level=json.loads((pack/'pack.json').read_text())['levels'][0]
    chart=json.loads((pack/f'level{level}.json').read_text())
    template=(pack/'verification/mesen-1/config.lua').read_text()
    assert 'neo_events=' in template
    first=next(n['step'] for n in chart['notes'] if n.get('hold_length',-1)>=0)
    events=[];key=2
    for note in chart['notes'][1:first+1]:
        if note['flags']&8:continue
        key=3-key;events.append([note['frame'],key])
    rows=[]
    for mode in ('early-release','missing-release','press-without-release'):
        out=pack/'verification'/('neo-hold-'+mode);out.mkdir(parents=True,exist_ok=True)
        inputs=list(events)
        if mode=='early-release':inputs.append([chart['notes'][first]['frame']+3,0])
        if mode=='press-without-release':inputs.append([chart['notes'][first+1]['frame'],3])
        config=re.sub(r'neo_events=\{.*?\}(?=,\w+=|\}\s*$)',
                      'neo_events={'+','.join('{'+','.join(map(str,e))+'}' for e in inputs)+'}',template)
        config=re.sub(r'out="[^"]+"','out='+json.dumps(out.as_posix()),config)
        config=re.sub(r'frames=\d+','frames='+str(chart['notes'][first+1]['frame']+600),config)
        config=config.rstrip()[:-1]+f',neo_failure_step={first}'+'}\n'
        path=out/'config.lua';path.write_text(config)
        env=dict(os.environ,ADOFAI_TEST_CONFIG=str(path))
        result=subprocess.run([str(args.mesen),'--testrunner','--timeout=90',str(pack/'adofai.sfc'),str(ROOT/'tools/verify_campaign_mesen.lua')],
                              env=env,timeout=100,capture_output=True,text=True,creationflags=subprocess.CREATE_NO_WINDOW)
        (out/'emulator.log').write_text(result.stdout+result.stderr)
        report=(out/'result.txt').read_text()
        assert result.returncode==0 and report.endswith('PASS\n'),(mode,report)
        rows.append(dict(case=mode,result=report));print(mode,'PASS',flush=True)
    (pack/'verification/neo-hold-failures.json').write_text(json.dumps(dict(passed=True,
        rom_sha256=hashlib.sha256((pack/'adofai.sfc').read_bytes()).hexdigest(),cases=rows),indent=2))


if __name__=='__main__':main()
