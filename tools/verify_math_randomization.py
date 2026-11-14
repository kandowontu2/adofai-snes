"""Use real controller retries to verify all four math problems randomize."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys

from verification_data import identity

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--pack',required=True)
    parser.add_argument('--levels',type=int,nargs='+',default=[68,73]);parser.add_argument('--attempts',type=int,default=16)
    a=parser.parse_args();assert 8<=a.attempts<=64
    pack=ROOT/'build/packs'/a.pack
    labels={n:int(v,16) for v,n in re.findall(r'al ([0-9A-Fa-f]+) \.([\w]+)',(pack/'adofai.lbl').read_text())}
    for level in a.levels:
        subprocess.run([sys.executable,str(ROOT/'tools/run_mesen_campaign.py'),'--pack',a.pack,'--levels',str(level),'--autoplay','--prepare-only'],check=True)
        out=pack/f'verification/math-randomization-{level}';out.mkdir(exist_ok=True)
        config=pack/f'verification/mesen-{level}-autoplay-prepared/config.lua'
        script='local C=dofile('+json.dumps(config.as_posix())+');C.out='+json.dumps(out.as_posix())+'\n'
        script+='dofile(C.failfast_script)(C)\nlocal choice='+str(labels['neo_math_choices'])+';local wanted='+str(a.attempts)+'\n'
        script+='''local W=emu.memType.snesWorkRam;local frame=0;local rows={};local armed=false;local last=-100;local finished=false
local function w(a)return emu.read(a,W)+256*emu.read(a+1,W)end
emu.addMemoryCallback(function()armed=true end,emu.callbackType.exec,'''+str(labels['neo_math_randomize'])+','+str(labels['neo_math_randomize'])+''',emu.cpuType.snes)
emu.addMemoryCallback(function()
 if not armed or finished then return end;armed=false;last=frame
 local row={};for i=0,3 do local value=w(choice+i*2);assert(value<4,'Invalid randomized choice');row[#row+1]=value end
 rows[#rows+1]=table.concat(row,',')
 if #rows==wanted then
  finished=true;local f=assert(io.open(C.out..'/choices.csv','w'));f:write(table.concat(rows,'\\n'));f:close();emu.stop(0)
 end
end,emu.callbackType.write,choice+7,choice+7,emu.cpuType.snes)
emu.addEventCallback(function()
 local b={};if C.menu_actions[frame] then b[C.menu_actions[frame]]=true end
 if frame==C.autoplay_frame then b.y=true end
 if #rows>0 and w(C.addr.state)==1 and frame>last+20 and frame%6==0 then b.select=true end
 emu.setInput(b,0)
end,emu.eventType.inputPolled)
emu.addEventCallback(function()frame=frame+1;assert(frame<6000,'Randomization retries timed out')end,emu.eventType.startFrame)
'''
        path=out/'retry.lua';path.write_text(script);(out/'choices.csv').unlink(missing_ok=True)
        pair=identity(pack/'adofai.sfc')
        result=subprocess.run([r'C:\mesen2\Mesen.exe','--testrunner','--timeout=90',str(pack/'adofai.sfc'),str(path)],capture_output=True,text=True,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0,timeout=110)
        (out/'emulator.log').write_text(result.stdout+result.stderr);assert result.returncode==0,result.stdout+result.stderr
        rows=[list(map(int,line.split(','))) for line in (out/'choices.csv').read_text().splitlines()]
        assert len(rows)==a.attempts and all(len(set(row[i] for row in rows))>1 for i in range(4)),rows
        assert identity(pack/'adofai.sfc')==pair
        report=dict(passed=True,level=level,attempts=len(rows),choices=rows,**pair)
        (out/'result.json').write_text(json.dumps(report,indent=2));print(report,flush=True)


if __name__=='__main__':main()
