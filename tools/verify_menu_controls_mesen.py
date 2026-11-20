"""Verify Select/Options, submenu Back, and the calibration return path."""
import argparse
import json
import os
import re
import subprocess
from pathlib import Path
from menu_sets import groups_for_pack
from verification_data import identity


def verify(pack):
    out=pack/'verification/menu-controls';out.mkdir(parents=True,exist_ok=True)
    (out/'result.txt').unlink(missing_ok=True)
    (out/'manifest.json').write_text(json.dumps(dict(passed=False)))
    frozen=identity(pack/'adofai.sfc')
    labels={n:int(v,16) for v,n in re.findall(r'al ([0-9A-Fa-f]+) \.([\w]+)',(pack/'adofai.lbl').read_text())}
    assert labels.get('MENU_OPTIONS_SELECT')==1
    groups=groups_for_pack(pack)
    actions={};checks={};at=90
    if len(groups)>1:
        actions[at]='b';checks[at+6]=(0,0)
        actions[at+10]='select';checks[at+16]=(7,0)
        actions[at+20]='start';checks[at+26]=(0,0)
        actions[at+30]='start';at+=44
    for group in range(len(groups)):
        actions[at]='select';checks[at+6]=(7,1)
        if group==0:
            for i in range(5):actions[at+10+i*4]='down'
            actions[at+34]='a';checks[at+40]=(5,1)
            actions[at+48]='select';checks[at+54]=(7,1)
            actions[at+62]='select';checks[at+68]=(0,1)
            at+=80
        else:
            actions[at+12]='start';checks[at+18]=(0,1);at+=30
        if group+1<len(groups):
            actions[at]='b';checks[at+6]=(0,0)
            actions[at+10]='down';actions[at+20]='start';at+=34
    names=('state','menu_depth','selected_level','settings_row','cal_return','pattern_vblank_overruns')
    lua='local A={'+','.join(k+'='+str(labels[k]) for k in names)+'}\n'
    lua+='local out='+json.dumps(out.as_posix())+'\n'
    lua+='dofile('+json.dumps((Path(__file__).resolve().parent/'mesen_failfast.lua').as_posix())+')({out=out})\n'
    lua+='local actions={'+','.join('['+str(t)+']='+json.dumps(k) for t,k in actions.items())+'}\n'
    lua+='local checks={'+','.join('['+str(t)+']={'+','.join(map(str,row))+'}' for t,row in checks.items())+'}\n'
    lua+='local finish='+str(at+8)+'\n'
    lua+=r'''
local W,V=emu.memType.snesWorkRam,emu.memType.snesVideoRam
local frame=0;local checked=0
local function w(n)return emu.read(A[n],W)+256*emu.read(A[n]+1,W)end
emu.addEventCallback(function()
 frame=frame+1
 local expected=checks[frame]
 if expected then
  assert(w('pattern_vblank_overruns')==0,'Menu/calibration publication exceeded VBlank')
  assert(w('state')==expected[1] and w('menu_depth')==expected[2],
   'Wrong menu/calibration destination at frame '..frame..': state '..w('state')..' depth '..w('menu_depth'))
  if expected[1]==0 then
   local text=''
   for y=16,27 do for x=0,31 do
    local c=emu.read(0xf000+y*64+x*2,V)
    text=text..(c>=32 and c<127 and string.char(c) or ' ')
   end end
   assert(not text:find('CALIBRATE') and not text:find('B OPTIONS'),'Obsolete menu shortcut')
  elseif expected[1]==5 then
   assert(w('settings_row')==5 and w('cal_return')==7,'Calibration did not originate in Options')
  end
  checked=checked+1
 end
 if frame==finish then
  local f=assert(io.open(out..'/result.txt','w'));f:write('PASS routes='..checked..'\n');f:close();emu.stop(0)
 end
end,emu.eventType.startFrame)
emu.addEventCallback(function()
 local keys={};if actions[frame] then keys[actions[frame]]=true end;emu.setInput(keys,0)
end,emu.eventType.inputPolled)
'''
    script=out/'verify.lua';script.write_text(lua)
    result=subprocess.run(['C:/mesen2/Mesen.exe','--testrunner',str(pack/'adofai.sfc'),str(script)],
                          capture_output=True,text=True,timeout=120,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
    (out/'emulator.log').write_text(result.stdout+result.stderr)
    outcome=(out/'result.txt').read_text() if (out/'result.txt').exists() else 'No result'
    assert result.returncode==0 and outcome.startswith('PASS '),result.stdout+result.stderr+outcome
    assert identity(pack/'adofai.sfc')==frozen
    report=dict(passed=True,sets=len(groups),routes=len(checks),**frozen)
    (out/'manifest.json').write_text(json.dumps(report,indent=2));print(report)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--pack',type=Path,required=True)
    verify(parser.parse_args().pack.resolve())
