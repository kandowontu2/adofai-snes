"""Verify retained mode through pause, death, and completion using real inputs."""
import argparse,json,os,re,subprocess
from pathlib import Path
from verification_data import identity
ROOT=Path(__file__).resolve().parents[1]

def verify(pack):
    base=ROOT/'build/packs'/pack;out=base/'verification/menu-mode'
    out.mkdir(parents=True,exist_ok=True)
    labels={n:int(v,16)&0x1ffff for v,n in re.findall(r'al ([0-9A-Fa-f]+) \.([\w]+)',(base/'adofai.lbl').read_text())}
    names=('state','autoplay','practice','menu_depth','menu_group','menu_selection','speed_tenths')
    script='local A={'+','.join(n+'='+str(labels[n]) for n in names)+'}\nlocal out='+json.dumps(out.as_posix())+'\n'
    script+=r'''
local W=emu.memType.snesWorkRam
local function w(n)return emu.read(A[n],W)+256*emu.read(A[n]+1,W)end
local cases={{0,0,'pause'},{0,1,'pause'},{1,0,'pause'},{0,0,'fail'},{1,0,'finish'}}
local frame=0;local stage=1;local started=false;local exiting=false;local age=0
local log=assert(io.open(out..'/result.txt','w'))
emu.addEventCallback(function()
 frame=frame+1
 if frame>12000 then log:write('FAIL timeout state='..w('state')..' auto='..w('autoplay')..' practice='..w('practice')..' stage='..stage..'\n');log:close();emu.stop(1);return end
 if started and w('state')==1 then age=age+1 end
 if started and exiting and w('state')==0 then
  local c=cases[stage]
  assert(w('autoplay')==c[1] and w('practice')==c[2],'Mode reset on return to menu')
  log:write('PASS case '..stage..' '..c[3]..'\n');log:flush()
  local f=assert(io.open(out..'/return-'..stage..'.png','wb'));f:write(emu.takeScreenshot());f:close()
  stage=stage+1;started=false;exiting=false;age=0
  if stage>#cases then log:write('PASS\n');log:close();emu.stop(0)end
 end
end,emu.eventType.startFrame)
emu.addEventCallback(function()
 local b={};local c=cases[stage]
 if frame>90 and frame%8==0 and c then
  local s=w('state')
  if s==0 and not started then
   if w('menu_depth')==0 then b.start=true
   elseif w('autoplay')~=c[1] then b.y=true
   elseif w('practice')~=c[2] then b.x=true
   elseif c[3]=='finish' and w('speed_tenths')<40 then b.r=true
   else b.start=true;started=true end
  elseif s==6 then b.start=true
  elseif c[3]=='pause' and s==1 and age>=40 then b.start=true
  elseif c[3]=='pause' and s==4 then b.select=true;exiting=true
  elseif c[3]=='fail' and s==2 then b.select=true;exiting=true
  elseif c[3]=='finish' and s==3 then b.select=true;exiting=true end
 end
 emu.setInput(b,0)
end,emu.eventType.inputPolled)
'''
    lua=out/'verify.lua';lua.write_text(script)
    result=subprocess.run([r'C:\mesen2\Mesen.exe','--testrunner',str(base/'adofai.sfc'),str(lua)],
        capture_output=True,text=True,timeout=180,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
    text=(out/'result.txt').read_text() if (out/'result.txt').exists() else ''
    report=dict(passed=result.returncode==0 and text.endswith('PASS\n'),cases=5,**identity(base/'adofai.sfc'))
    (out/'manifest.json').write_text(json.dumps(report,indent=2))
    print(text);assert report['passed'],result.stdout+result.stderr

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--pack',required=True);verify(p.parse_args().pack)
