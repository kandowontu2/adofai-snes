"""Smoke-test scheduled playback in every rebuilt cartridge and chart."""
import concurrent.futures
import json
import os
from pathlib import Path
from verify_scheduled_hits import check
from verification_data import identity

ROOT=Path(__file__).resolve().parents[1]

def verify(row):
    base=Path(row['pack'])
    levels=json.loads((base/'pack.json').read_text())['levels']
    cases=[check(base,n,0,mode='auto',limit=16) for n in levels]
    result=dict(passed=True,pack=base.name,cases=cases,**identity(base/'adofai.sfc'))
    (base/'optimized-smoke.json').write_text(json.dumps(result,indent=2))
    print('PASS',base.name,len(cases),'charts',flush=True)
    return result

if __name__=='__main__':
    for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='1'
    rows=json.loads((ROOT/'build/optimized-release-inputs.json').read_text())[1:]
    with concurrent.futures.ProcessPoolExecutor(max_workers=4) as pool:results=list(pool.map(verify,rows))
    (ROOT/'build/optimized-standalone-checks.json').write_text(json.dumps(dict(passed=True,results=results),indent=2))
