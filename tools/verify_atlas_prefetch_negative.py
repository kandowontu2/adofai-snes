"""Accept the reserved zero glyph and reject actual prefetch corruption."""
import argparse,json,os,subprocess,sys
from pathlib import Path
from verification_data import identity
from run_mesen_campaign import suite_digest

ROOT=Path(__file__).resolve().parents[1]

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--pack',required=True)
    args=ap.parse_args();base=ROOT/'build/packs'/args.pack
    frozen=identity(base/'adofai.sfc');digest=suite_digest()
    ids=json.loads((base/'pack.json').read_text())['levels'];local=ids.index(286)+1
    subprocess.run([sys.executable,str(ROOT/'tools/run_mesen_campaign.py'),'--pack',args.pack,
                    '--levels',str(local),'--autoplay','--vfx-off','--graphics-dumps','--prepare-only'],check=True)
    prepared=base/f'verification/mesen-{local}-autoplay-vfx-off-prepared/config.lua'
    cases=[]
    for case,reason in [('baseline',None),('blank-pixels','Reserved transparent glyph contains nonzero pixels'),
                        ('foreign-atlas','Wide front map points outside its atlas')]:
        out=base/'verification/atlas-prefetch-controls'/case;out.mkdir(parents=True,exist_ok=True)
        for name in ('result.txt','control.txt'):(out/name).unlink(missing_ok=True)
        config=out/'config.lua'
        config.write_text('local C=dofile('+json.dumps(prepared.as_posix())+');C.out='+json.dumps(out.as_posix())+
                          ';C.prefetch_test='+json.dumps(case)+';C.prefetch_campaign_script='+
                          json.dumps((ROOT/'tools/verify_campaign_mesen.lua').as_posix())+';return C\n')
        env=os.environ.copy();env['ADOFAI_TEST_CONFIG']=str(config)
        r=subprocess.run([r'C:\mesen2\Mesen.exe','--testrunner','--timeout=240',str(base/'adofai.sfc'),
                          str(ROOT/'tools/verify_atlas_prefetch_mesen.lua')],cwd=ROOT,env=env,
                         creationflags=subprocess.CREATE_NO_WINDOW,capture_output=True,text=True,timeout=270)
        (out/'emulator.log').write_text(r.stdout+r.stderr)
        result=(out/'result.txt').read_text();control=(out/'control.txt').read_text()
        assert case+' observed reserved glyph' in control,control
        if reason:assert r.returncode!=0 and reason in result and result.endswith('FAIL\n'),result
        else:assert r.returncode==0 and result.endswith('PASS\n'),result
        cases.append(dict(case=case,passed=True,expected_rejection=reason,observed=control))
        print('ATLAS PREFETCH CONTROL PASS',case,flush=True)
    assert identity(base/'adofai.sfc')==frozen and suite_digest()==digest
    (base/'verification/atlas-prefetch-negative.json').write_text(json.dumps(
        dict(passed=True,**frozen,suite_digest=digest,cases=cases),indent=2))

if __name__=='__main__':main()
