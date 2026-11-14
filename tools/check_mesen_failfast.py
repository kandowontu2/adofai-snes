"""Negative acceptance tests: disabled/broken oracles must fail the emulator run."""
import argparse,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--rom',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--mesen',type=Path,default=Path(r'C:\mesen2\Mesen.exe'));a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=True)
 for name,callback,body in [('event_error','event',"error('injected event failure')"),('memory_error','memory',"error('injected memory failure')"),('assertion','event',"assert(false,'injected assertion failure')")]:
  folder=(a.out/name).resolve();folder.mkdir(exist_ok=True);result=folder/'result.txt';result.unlink(missing_ok=True)
  script='dofile('+json.dumps((ROOT/'tools/mesen_failfast.lua').as_posix())+')({out='+json.dumps(folder.as_posix())+'})\n'
  script+='emu.addEventCallback(function() '+body+' end,emu.eventType.startFrame)\n' if callback=='event' else 'emu.addMemoryCallback(function() '+body+' end,emu.callbackType.write,0,65535,emu.cpuType.snes)\n'
  path=folder/'negative.lua';path.write_text(script)
  r=subprocess.run([str(a.mesen),'--testrunner','--timeout=10',str(a.rom.resolve()),str(path)],cwd=ROOT,creationflags=subprocess.CREATE_NO_WINDOW,capture_output=True,text=True,timeout=20)
  assert r.returncode!=0 and result.exists() and result.read_text().endswith('FAIL\n'),(name,r.returncode,r.stdout,r.stderr)
  print(name+': rejected as expected',flush=True)
if __name__=='__main__':main()
