"""Measure renderer stages using Mesen's emulated master clock."""
import argparse,json,os,re,subprocess
from pathlib import Path
from verification_data import identity
ROOT=Path(__file__).resolve().parents[1]
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--pack',default='feedback-perf');ap.add_argument('--level',type=int,default=31);ap.add_argument('--speed',type=int,default=10);ap.add_argument('--frames',type=int,default=2200);args=ap.parse_args()
    base=ROOT/'build/packs'/args.pack;out=base/f'verification/cpu-profile-{args.level}';out.mkdir(parents=True,exist_ok=True)
    labels={n:int(a,16) for a,n in re.findall(r'al ([0-9a-fA-F]+) \.([\w]+)',(base/'adofai.lbl').read_text())}
    a={k:labels[k]&0x1ffff for k in ('profile_phase','frame_ready','state','music_active','speed_tenths','commits','step')}
    entries={k:labels[k]+(0 if (base/'sa1.cfg').exists() else 0xc00000) for k in ('clear_oam','mode7_cache_identity','mode7_cache_future','update_pattern_cache')}
    script='local A={'+','.join(k+'='+str(v) for k,v in a.items())+'}\n'
    script+='local out='+json.dumps(out.as_posix())+'\nlocal level='+str(args.level)+'\nlocal speed='+str(args.speed)+'\nlocal stop_frame='+str(args.frames)+'\n'
    script+='''local W=emu.memType.snesWorkRam
local frame=0;local last=nil;local phase=0;local totals={};local counts={}
local measured=0;local delivered=0;local lastCommit=nil;local gap=0;local maxGap=0
local function word(a)return emu.read(a,W)+256*emu.read(a+1,W)end
local function mark(p)
 if frame<500 or word(A.state)~=1 or word(A.music_active)==0 then return end
 local s=emu.getState();local now=s.masterClock
 if now==nil then
  local f=io.open(out..'/state.txt','w');for k,v in pairs(s) do f:write(k..'='..tostring(v)..'\\n') end;f:close();emu.stop(1);return
 end
 if last then totals[phase]=(totals[phase] or 0)+now-last;counts[phase]=(counts[phase] or 0)+1 end
 phase=p;last=now
end
emu.addMemoryCallback(function(a,v)mark(v)end,emu.callbackType.write,A.profile_phase,A.profile_phase,emu.cpuType.snes)
emu.addMemoryCallback(function(a,v)if v==1 then mark(0) end end,emu.callbackType.write,A.frame_ready,A.frame_ready,emu.cpuType.snes)
'''
    for name,phase in [('clear_oam',15),('mode7_cache_identity',12),('mode7_cache_future',13),('update_pattern_cache',14)]:
        script+=f'emu.addMemoryCallback(function()mark({phase})end,emu.callbackType.exec,{entries[name]},{entries[name]},emu.cpuType.snes)\n'
    script+='''emu.addEventCallback(function()
 local b={}
 if frame>=60 and frame<60+(speed-10)*2 and frame%2==0 then b.r=true end
 if frame==90 then b.y=true end
 if frame>=100 and frame<100+(level-1)*2 and frame%2==0 then b.down=true end
 if frame==180 then b.start=true end
 emu.setInput(b,0)
end,emu.eventType.inputPolled)
emu.addEventCallback(function()
 frame=frame+1
 if word(A.state)==1 and word(A.music_active)==1 then
  measured=measured+1;gap=gap+1
  local commit=word(A.commits)
  if lastCommit and commit~=lastCommit then delivered=delivered+1;maxGap=math.max(maxGap,gap);gap=0 end
  lastCommit=commit
 end
 if frame==500 and word(A.speed_tenths)~=speed then emu.stop(2) end
 if frame==stop_frame then
  mark(0);local f=io.open(out..'/cycles.csv','w');f:write('phase,clocks,calls\\n')
  for k,v in pairs(totals) do f:write(k..','..v..','..counts[k]..'\\n') end
  f:close();f=io.open(out..'/presentation.txt','w');f:write('frames='..measured..' delivered='..delivered..' fps='..(60.0988*delivered/measured)..' maxGap='..maxGap);f:close();emu.stop(0)
 end
end,emu.eventType.startFrame)
'''
    path=out/'profile.lua';path.write_text(script)
    r=subprocess.run([r'C:\mesen2\Mesen.exe','--testrunner',str(base/'adofai.sfc'),str(path)],cwd=ROOT,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0,capture_output=True,text=True,timeout=180)
    assert r.returncode==0,(r.stdout[-1000:],r.stderr[-1000:]);print((out/'cycles.csv').read_text())
    (out/'identity.json').write_text(json.dumps(identity(base/'adofai.sfc')))
if __name__=='__main__':main()
