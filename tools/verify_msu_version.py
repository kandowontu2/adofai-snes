"""An incompatible MSU dataset must not start a chart with the new ROM."""
import json,shutil,tempfile
from pathlib import Path
from emulate import Emulator,ROOT
from input_helpers import press
BASE=ROOT/'build/packs/master'

def main():
    global BASE
    import argparse
    ap=argparse.ArgumentParser();ap.add_argument('--pack',default='master');args=ap.parse_args()
    BASE=ROOT/'build/packs'/args.pack
    with (BASE/'adofai.msu').open('rb') as f:
        f.seek(12);expected=int.from_bytes(f.read(2),'little')
    rows=[]
    for version in (None,0,*range(7,expected+1)):
        with tempfile.TemporaryDirectory() as folder:
            out=Path(folder)
            for name in ('adofai.sfc','adofai.lbl'):shutil.copyfile(BASE/name,out/name)
            if version==expected:shutil.copyfile(BASE/'adofai.msu',out/'adofai.msu')
            elif version is not None:(out/'adofai.msu').write_bytes(b'ADOFAI-MSU1\0'+version.to_bytes(2,'little')+bytes(18))
            em=Emulator(rom=out/'adofai.sfc')
            try:
                for _ in range(120):em.run()
                press(em,3)
                for _ in range(20):em.run()
                present=em.read('msu_present');assert present==int(version==expected),(version,present)
                if version!=expected:
                    assert em.read('state')==0,'An incompatible dataset started playback'
                rows.append(dict(version=version,accepted=bool(present)))
            finally:em.close()
    from verification_data import identity
    report=dict(**identity(BASE/'adofai.sfc'),passed=True,cases=rows)
    (BASE/'verification/msu-version.json').write_text(json.dumps(report,indent=2));print(report)

if __name__=='__main__':main()
