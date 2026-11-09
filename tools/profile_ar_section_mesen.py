"""Compare delivered frames around AR-X's 13% transition in MesenCE."""
import argparse,json,os,re,subprocess
from pathlib import Path
from verification_data import identity

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--rom',type=Path,required=True);ap.add_argument('--labels',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    a.out.mkdir(parents=True,exist_ok=True)
    labels={n:int(v,16) for v,n in re.findall(r'al ([0-9a-fA-F]+) \.([\w]+)',a.labels.read_text())}
    fields={n:labels[n]&0x1ffff for n in ('state','step','music_active','commits','chart_time','display_chart_time','profile_phase','animation_time','animation_kind','pattern_vblank_overruns')}
    script='local A={'+','.join(n+'='+str(v) for n,v in fields.items())+'}\n'
    script+='local output='+json.dumps((a.out/'presentation.json').resolve().as_posix())+'\n'
    levels=json.loads((a.rom.parent/'pack.json').read_text())['levels']
    script+='local menu_index='+str(levels.index(23))+'\n'
    script+='''local W=emu.memType.snesWorkRam
local frame=0;local measured=0;local delivered=0;local last=nil;local gap=0;local maximum=0
local trace=io.open(output..'.csv','w');trace:write('frame,step,clock,display,commit,phase,event_time,event_kind,worker,remaining,atomic,deferrals,done,pending,dma_request,dma_active\\n')
local function bw(a)return emu.read(a,emu.memType.snesSaveRam)+256*emu.read(a+1,emu.memType.snesSaveRam)end
local function word(a)return emu.read(a,W)+256*emu.read(a+1,W)end
emu.addEventCallback(function()
 local b={}
 if frame==90 then b.y=true end
 if frame>=100 and frame<100+menu_index*2 and frame%2==0 then b.down=true end
 if frame==180 then b.start=true end
 emu.setInput(b,0)
end,emu.eventType.inputPolled)
emu.addEventCallback(function()
 frame=frame+1
 local step=word(A.step)
 if word(A.state)==1 and word(A.music_active)==1 and step>=75 and step<=110 then
  measured=measured+1;gap=gap+1
  local commit=word(A.commits)
  trace:write(string.format('%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d\\n',frame,step,word(A.chart_time),word(A.display_chart_time),commit,word(A.profile_phase),word(A.animation_time),word(A.animation_kind),bw(0x30),bw(0x1fc4c),bw(0x1fc5a),bw(0x1fc90),bw(2),bw(10),bw(4),bw(6)))
  if last and commit~=last then delivered=delivered+1;maximum=math.max(maximum,gap);gap=0 end
  last=commit
 end
 if frame==2500 then
  local f=io.open(output,'w')
  f:write(string.format('{"frames":%d,"delivered":%d,"fps":%.6f,"max_gap":%d,"vblank_overruns":%d}',measured,delivered,60.0988*delivered/measured,maximum,word(A.pattern_vblank_overruns)))
  f:close();trace:close();emu.stop(0)
 end
end,emu.eventType.startFrame)
'''
    path=a.out/'profile.lua';path.write_text(script)
    r=subprocess.run([r'C:\mesen2\Mesen.exe','--testrunner',str(a.rom.resolve()),str(path.resolve())],creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0,capture_output=True,text=True,timeout=180)
    assert r.returncode==0,(r.stdout,r.stderr)
    result=json.loads((a.out/'presentation.json').read_text());assert result['frames']>300
    result.update(identity(a.rom));result['step_range']=[75,110]
    (a.out/'result.json').write_text(json.dumps(result,indent=2));print(result)

if __name__=='__main__':main()
