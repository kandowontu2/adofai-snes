"""Measure symbol work with MesenCE's emulated clock, not wall time."""
import argparse, json, os, re, subprocess, sys
from pathlib import Path
from verification_data import identity

ROOT=Path(__file__).resolve().parents[1]

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--pack',required=True)
    ap.add_argument('--level',type=int,required=True,help='Global chart ID')
    ap.add_argument('--first',type=int,required=True)
    ap.add_argument('--last',type=int,required=True)
    ap.add_argument('--tag',required=True)
    ap.add_argument('--vfx-off',action='store_true')
    args=ap.parse_args()
    base=ROOT/'build/packs'/args.pack
    ids=json.loads((base/'pack.json').read_text())['levels']
    local=ids.index(args.level)+1
    subprocess.run([sys.executable,str(ROOT/'tools/run_mesen_campaign.py'),'--pack',args.pack,
                    '--levels',str(local),'--autoplay','--prepare-only','--sampled-graphics',
                    *(['--vfx-off'] if args.vfx_off else [])],check=True)
    suffix='-vfx-off' if args.vfx_off else ''
    config=base/f'verification/mesen-{local}-autoplay{suffix}-prepared/config.lua'
    out=base/f'verification/symbols-{args.level}-{args.tag}'
    out.mkdir(parents=True,exist_ok=True)
    labels={n:int(a,16) for a,n in re.findall(r'al ([0-9A-Fa-f]+) \.([\w]+)',(base/'adofai.lbl').read_text())}
    script=f'''local C=dofile({json.dumps(config.as_posix())})
C.out={json.dumps(out.as_posix())};C.graphics_dumps=false;C.profile_ranges=nil
local W=emu.memType.snesWorkRam
local function word(a)return emu.read(a,W)+256*emu.read(a+1,W)end
local first,last={args.first},{args.last}
local f=assert(io.open(C.out..'/samples.csv','w'));f:write('time,step,clocks,oam_bytes,visible_bytes,gap\\n')
local dump=assert(io.open(C.out..'/oam.bin','wb'))
local entered=0;local ready=0;local start=nil;local frame=0;local previous=nil;local gap=0;local maxGap=0
local samples=0;local clocks=0;local maxClocks=0;local maxObjects=0
emu.addMemoryCallback(function()
 entered=entered+1
 local step=word(C.addr.step)
 if word(C.addr.state)==1 and step>=first and step<=last then start=emu.getState().masterClock else start=nil end
end,emu.callbackType.exec,{labels['render_symbols']|0x800000},{labels['render_symbols']|0x800000},emu.cpuType.snes)
emu.addMemoryCallback(function(a,v)
 ready=ready+1
 if v~=1 or not start then return end
 local duration=emu.getState().masterClock-start;start=nil
 local n=word(C.addr.oam_pos);samples=samples+1;clocks=clocks+duration;maxClocks=math.max(maxClocks,duration);maxObjects=math.max(maxObjects,n/4)
 local t=word(C.addr.chart_time)
 f:write(t..','..word(C.addr.step)..','..duration..','..n..','..(emu.read({0x416c08},emu.memType.snesMemory)+256*emu.read({0x416c09},emu.memType.snesMemory))..','..gap..'\\n')
 dump:write(string.char(t%256,math.floor(t/256),n%256,math.floor(n/256)))
 for i=0,543 do dump:write(string.char(emu.read(512+i,W))) end
end,emu.callbackType.write,C.addr.frame_ready,C.addr.frame_ready,emu.cpuType.snes)
emu.addEventCallback(function()
 frame=frame+1
 local step=word(C.addr.step)
 if word(C.addr.state)==1 and step>=first and step<=last then
  local commit=word(C.addr.commits)
  gap=gap+1
  if previous and commit~=previous then maxGap=math.max(maxGap,gap);gap=0 end
  previous=commit
 end
 if step>last then
  print("callbacks",entered,ready,samples)
  assert(samples>0,"No symbol samples: "..entered..","..ready)
  f:close();dump:close()
  local r=assert(io.open(C.out..'/timing.json','w'))
  r:write(string.format('{{"samples":%d,"mean_clocks":%.1f,"max_clocks":%d,"max_objects":%d,"max_gap":%d}}',samples,clocks/samples,maxClocks,maxObjects,maxGap));r:close();emu.stop(0)
 end
end,emu.eventType.endFrame)
local original=os.getenv
os.getenv=function(k)if k=='ADOFAI_TEST_CONFIG' then return C end;return original(k)end
'''
    probes=[]
    for name in ('render_symbols','sa1_symbols','mode1_icons_ready','mode1_icons_complete','draw_trails','sa1_draw_arc','sa1_arc_complete','neo_camera_copies'):
        if name not in labels:continue
        address=labels[name]
        if 0x8000<=address<0x10000:address|=0x800000
        probes.append(f"emu.addMemoryCallback(function()phase_mark('{name}')end,emu.callbackType.exec,{address},{address},emu.cpuType.snes)")
    profile="""local phases={};local phase=nil;local at=nil
local function phase_mark(p)
 local step=word(C.addr.step)
 if word(C.addr.state)~=1 or step<first or step>last then at=nil;return end
 local now=emu.getState().masterClock
 if at then phases[phase]=(phases[phase]or 0)+now-at end
 phase=p;at=now
 local h=io.open(C.out..'/phases.txt','w');for k,v in pairs(phases)do h:write(k..'='..v..'\\n')end;h:close()
end
"""+'\n'.join(probes)+'\n'
    where=script.index('emu.addMemoryCallback(function()')
    script=script[:where]+profile+script[where:]
    # Keep the ordinary menu/input and game assertions; provide the
    # modified table without writing a second huge chart configuration.
    script=script[:script.index('local original=os.getenv')]+f'''local load=dofile
dofile=function(p)if p=={json.dumps(config.as_posix())} then return C end;return load(p)end
load({json.dumps((ROOT/'tools/verify_campaign_mesen.lua').as_posix())})
'''
    path=out/'profile.lua';path.write_text(script)
    env=os.environ.copy();env['ADOFAI_TEST_CONFIG']=config.as_posix()
    frozen=identity(base/'adofai.sfc')
    r=subprocess.run([r'C:\mesen2\Mesen.exe','--testrunner','--timeout=600',str(base/'adofai.sfc'),str(path)],
                     cwd=ROOT,env=env,capture_output=True,text=True,timeout=630,
                     creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
    (out/'emulator.log').write_text(r.stdout+r.stderr)
    assert r.returncode==0 and (out/'timing.json').exists(),r.stdout[-2000:]+r.stderr[-2000:]
    assert identity(base/'adofai.sfc')==frozen
    (out/'identity.json').write_text(json.dumps(frozen,indent=2))
    print(args.level,args.tag,(out/'timing.json').read_text(),flush=True)

if __name__=='__main__':main()
