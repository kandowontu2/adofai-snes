"""Autoplay a sequence through the real menus in one uninterrupted Mesen session."""
import argparse,json,subprocess,sys,re,os
from pathlib import Path
from verification_data import identity
from menu_sets import groups
from run_mesen_campaign import suite_digest
ROOT=Path(__file__).resolve().parents[1]
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--pack',required=True);ap.add_argument('--levels',nargs='+',type=int,required=True);ap.add_argument('--mesen',type=Path,default=Path(r'C:\mesen2\Mesen.exe'));a=ap.parse_args()
 base=ROOT/'build/packs'/a.pack;out=base/'verification'/('sequence-'+'-'.join(map(str,a.levels)));out.mkdir(parents=True,exist_ok=True)
 subprocess.run([sys.executable,str(ROOT/'tools/run_mesen_campaign.py'),'--pack',a.pack,'--levels',*map(str,sorted(set(a.levels))),'--graphics-dumps','--prepare-only'],check=True)
 labels={n:int(v,16) for v,n in re.findall(r'al ([0-9a-fA-F]+) \.([\w]+)',(base/'adofai.lbl').read_text())};levels=json.loads((base/'pack.json').read_text())['levels'];sets=groups(levels);stages=[];limit=1200
 for i,n in enumerate(a.levels,1):
  group=next(j for j,(_,members) in enumerate(sets) if n-1 in members);selection=sets[group][1].index(n-1)
  folder=out/f'stage-{i}-{n}';folder.mkdir(exist_ok=True)
  for pattern in ('ppu-*.bin','screen-*.png','result.txt','manifest.json','ppu-verification.json','screen-registers.txt','mode1-icon-jobs.txt'):
   for f in folder.glob(pattern):f.unlink()
  stages.append('{level='+str(n-1)+',group='+str(group)+',selection='+str(selection)+',out='+json.dumps(folder.as_posix())+',config='+json.dumps((base/f'verification/mesen-{n}-prepared/config.lua').as_posix())+'}')
  limit+=round(json.loads((base/f'level{levels[n-1]}.json').read_text())['duration']*60.099)+900
 names=('state','step','selected_level','autoplay','menu_group','menu_depth','menu_selection','misses','pattern_vblank_overruns')
 config='return {out='+json.dumps(out.as_posix())+',guard='+json.dumps((ROOT/'tools/mesen_failfast.lua').as_posix())+',addr={'+','.join(n+'='+str(labels[n]) for n in names)+'},frames='+str(limit)+',stages={'+','.join(stages)+'}}'
 path=out/'config.lua';path.write_text(config);env=os.environ.copy();env['ADOFAI_SEQUENCE_CONFIG']=str(path);(out/'result.txt').unlink(missing_ok=True)
 before=identity(base/'adofai.sfc');code=suite_digest()
 r=subprocess.run([str(a.mesen),'--testrunner','--timeout=900',str(base/'adofai.sfc'),str(ROOT/'tools/verify_sequence_mesen.lua')],cwd=ROOT,env=env,creationflags=subprocess.CREATE_NO_WINDOW,capture_output=True,text=True,timeout=930)
 (out/'emulator.log').write_text(r.stdout+r.stderr);result=(out/'result.txt').read_text() if (out/'result.txt').exists() else '\n'.join(f'{p.parent.name}: {p.read_text()}' for p in out.glob('stage-*/result.txt')) or 'No result';print(result,flush=True)
 assert before==identity(base/'adofai.sfc') and code==suite_digest(),'Build/checks changed during sequence'
 assert r.returncode==0 and result.endswith('PASS\n'),result
 for i,n in enumerate(a.levels,1):
  folder=out/f'stage-{i}-{n}';manifest=dict(**before,suite_version=2,suite_digest=code,graphics_dumps=True,passed=True,vblank_overruns=0,sequence=a.levels,stage=i)
  (folder/'manifest.json').write_text(json.dumps(manifest,indent=2))
  subprocess.run([sys.executable,str(ROOT/'tools/verify_mesen_ppu.py'),'--pack',a.pack,'--level',str(n),'--folder',str(folder)],check=True)
 (out/'manifest.json').write_text(json.dumps(dict(**before,suite_digest=code,passed=True,levels=a.levels),indent=2))
if __name__=='__main__':main()
