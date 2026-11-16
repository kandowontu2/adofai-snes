"""Exercise the VFX option and neighboring settings with controller input."""
import argparse,json,os,re,subprocess
from pathlib import Path
from verification_data import identity
ROOT=Path(__file__).resolve().parents[1]

def verify(pack):
    out=pack/'verification/vfx-options';out.mkdir(parents=True,exist_ok=True)
    labels={n:int(v,16)&0x1ffff for v,n in re.findall(r'al ([0-9A-Fa-f]+) \.([\w]+)',(pack/'adofai.lbl').read_text())}
    names=('state','settings_row','time_attack','vfx_enabled','ice_color')
    lua='local A={'+','.join(n+'='+str(labels[n]) for n in names)+'}\n'
    lua+='local out='+json.dumps(out.as_posix())+'\n'
    lua+=r'''
local W=emu.memType.snesWorkRam
local function w(n)return emu.read(A[n],W)+256*emu.read(A[n]+1,W)end
local frame=0
local presses={[90]='b',[110]='right',[130]='up',[150]='right',[170]='start',[190]='b',[210]='right'}
emu.addEventCallback(function()
 frame=frame+1
 if frame==105 then assert(w('state')==7 and w('vfx_enabled')==0,'VFX default/options entry') end
 if frame==125 then assert(w('time_attack')==1 and w('ice_color')==1,'Time attack toggled wrong setting') end
 if frame==145 then assert(w('settings_row')==6,'Options wrap omitted VFX row') end
 if frame==165 then assert(w('vfx_enabled')==1,'VFX ON did not toggle') end
 if frame==205 then assert(w('state')==7 and w('vfx_enabled')==1,'VFX ON lost when returning to options') end
 if frame==230 then
  assert(w('vfx_enabled')==0 and w('time_attack')==1,'VFX OFF changed another setting')
  local f=assert(io.open(out..'/options.png','wb'));f:write(emu.takeScreenshot());f:close()
  f=assert(io.open(out..'/result.txt','w'));f:write('PASS default, toggle, wrap, retention, neighboring setting\n');f:close()
  emu.stop(0)
 end
end,emu.eventType.startFrame)
emu.addEventCallback(function()
 local keys={};if presses[frame] then keys[presses[frame]]=true end;emu.setInput(keys,0)
end,emu.eventType.inputPolled)
'''
    script=out/'verify.lua';script.write_text(lua)
    result=subprocess.run([r'C:\mesen2\Mesen.exe','--testrunner',str(pack/'adofai.sfc'),str(script)],
        capture_output=True,text=True,timeout=90,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
    (out/'emulator.log').write_text(result.stdout+result.stderr)
    assert result.returncode==0 and (out/'result.txt').exists(),result.stdout+result.stderr
    (out/'manifest.json').write_text(json.dumps(dict(passed=True,**identity(pack/'adofai.sfc')),indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--pack',type=Path,required=True)
    verify(p.parse_args().pack.resolve())
