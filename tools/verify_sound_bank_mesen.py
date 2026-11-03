"""Check actual SPC RAM sample banks, including the bank above the BRR ring."""
import argparse,json,os,re,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--pack',required=True);ap.add_argument('--levels',type=int,nargs='+',default=[1,43,51]);a=ap.parse_args()
    base=ROOT/'build/packs'/a.pack;levels=json.loads((base/'pack.json').read_text())['levels']
    from hit_sound_assets import compile_bank
    sources=json.loads((ROOT/'assets/private/hitsound-levels.json').read_text());rows=[]
    labels={n:int(v,16) for v,n in re.findall(r'al ([\dA-Fa-f]+) \.([\w]+)',(base/'adofai.lbl').read_text())}
    for n in a.levels:
        out=base/f'verification/sound-bank-{n}';out.mkdir(parents=True,exist_ok=True)
        chart=json.loads((base/f'level{n}.json').read_text());_,bank,meta=compile_bank(chart,sources[str(n)])
        (out/'expected.bin').write_bytes(bank);first,second=meta['packet_counts'];index=levels.index(n)
        config=dict(out=out.as_posix(),state=labels['state'],menu_count=index,first=first*3,second=second*3)
        (out/'config.lua').write_text('return {'+','.join(k+'='+ (json.dumps(v) if isinstance(v,str) else str(v)) for k,v in config.items())+'}')
        env=os.environ.copy();env['ADOFAI_SOUND_CONFIG']=str(out/'config.lua')
        result=subprocess.run(['C:/mesen2/Mesen.exe','--testrunner','--timeout=40',str(base/'adofai.sfc'),str(ROOT/'tools/verify_sound_bank_mesen.lua')],cwd=ROOT,env=env,creationflags=subprocess.CREATE_NO_WINDOW,capture_output=True,text=True,timeout=50)
        report=(out/'result.txt').read_text() if (out/'result.txt').exists() else result.stdout+result.stderr
        assert result.returncode==0 and report.startswith('PASS'),(n,result.returncode,report)
        rows.append(dict(level=n,bank_bytes=len(bank),**meta));print(n,report.strip(),flush=True)
    from verification_data import identity
    (base/'verification/sound-banks.json').write_text(json.dumps(dict(passed=True,cases=rows,**identity(base/'adofai.sfc')),indent=2))
if __name__=='__main__':main()

