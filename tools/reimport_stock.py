"""Refresh stock chart data and all supported camera/track metadata in order."""
import json
import argparse
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
STAGES=('audit_catalog','import_campaign','import_official','import_tech',
        'import_visibility','import_colors','import_camera','import_native_layout',
        'import_stick_to_floors','import_hitsounds','import_neo')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--from-stage',choices=STAGES,default=STAGES[0])
    args=parser.parse_args()
    out=ROOT/'build/stock-refresh';out.mkdir(parents=True,exist_ok=True)
    before=out/'before';before.mkdir(exist_ok=True)
    levels=[*range(1,62),*range(66,75)]
    for n in levels:
        source=ROOT/f'assets/private/level{n}.json'
        if source.exists() and not (before/source.name).exists():
            (before/source.name).write_bytes(source.read_bytes())
    report=[]
    for stage in STAGES[STAGES.index(args.from_stage):]:
        print('IMPORT',stage,flush=True)
        with (out/f'{stage}.log').open('w') as log:
            result=subprocess.run([sys.executable,'-X','utf8',str(ROOT/f'tools/{stage}.py')],
                                  cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
        report.append(dict(stage=stage,passed=result.returncode==0))
        (out/'import-report.json').write_text(json.dumps(report,indent=2))
        if result.returncode:raise SystemExit(f'{stage} failed; see {out/stage}.log')
    audit=[]
    for n in levels:
        d=json.loads((ROOT/f'assets/private/level{n}.json').read_text())
        assert 'camera_initial' in d,(n,'missing camera refresh')
        audit.append(dict(id=n,code=d.get('code'),floors=len(d['floors']),
            camera_events=len(d.get('camera_actions',[]))+len(d.get('native_camera_effects',[])),
            track_events=len(d.get('track_actions',[]))+len(d.get('native_track_effects',[]))))
    (out/'charts.json').write_text(json.dumps(audit,indent=2))
    print('Refreshed',len(audit),'stock charts including Neo Cosmos.',flush=True)


if __name__=='__main__':main()
