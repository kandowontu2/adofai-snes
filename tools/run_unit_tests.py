"""Record a full regression run against an immutable master dataset."""
import argparse,json,os,re,subprocess,sys
from pathlib import Path
from verification_data import identity
ROOT=Path(__file__).resolve().parents[1]

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--pack',default='master');args=ap.parse_args()
    rom=ROOT/f'build/packs/{args.pack}/adofai.sfc';before=identity(rom)
    env=os.environ.copy()
    for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):env[name]='1'
    stem='latest' if args.pack=='master' else args.pack
    log=ROOT/f'build/{stem}-unit-tests.log'
    with log.open('w') as output:
        result=subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-v'],cwd=ROOT,env=env,stdout=output,stderr=subprocess.STDOUT)
    assert result.returncode==0,log.read_text()[-3000:]
    assert identity(rom)==before,'Master dataset changed during the regression run'
    count=int(re.search(r'Ran (\d+) tests',log.read_text())[1]);assert count>=59
    (ROOT/f'build/{stem}-unit-tests.json').write_text(json.dumps(dict(**before,passed=True,tests=count),indent=2))
    print(f'PASS: {count} regression tests')

if __name__=='__main__':main()
