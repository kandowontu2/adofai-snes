import argparse
import json
import os
import re
import subprocess
from pathlib import Path

root=Path(__file__).resolve().parents[1]
ap=argparse.ArgumentParser();ap.add_argument('--mesen',type=Path,default=Path(r'C:\mesen2\Mesen.exe'));args=ap.parse_args()
out=root/'build/verification/mesen';out.mkdir(parents=True,exist_ok=True)
labels={m[1]:int(m[0],16) for m in re.findall(r'al ([0-9A-Fa-f]+) \.([\w]+)',(root/'build/adofai.lbl').read_text())}
notes=json.loads((root/'build/level.json').read_text())['notes']
config='return {addr={'+','.join(k+'='+str(labels[k]) for k in ('state','step','elapsed','combo','perfects','misses'))+'},times={'+','.join(str(n['frame']) for n in notes)+'},out='+json.dumps(out.as_posix())+'}\n'
path=out/'config.lua';path.write_text(config)
env=os.environ.copy();env['ADOFAI_TEST_CONFIG']=str(path)
result=subprocess.run([str(args.mesen),'--testrunner',str(root/'build/adofai.sfc'),str(root/'tools/verify_mesen.lua')],env=env,cwd=root,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0,timeout=120,capture_output=True,text=True)
print(result.stdout[-2000:]);print(result.stderr[-2000:])
report=(out/'result.txt').read_text();print(report.splitlines()[0]);print(report.splitlines()[-1]);assert report.endswith('PASS\n')
