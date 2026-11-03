"""Check that sample-locked music has no second percussion voice in MesenCE in the tester's MesenCE."""
import argparse,csv,json,os,re,subprocess
from pathlib import Path
from verification_data import identity
from hit_timing import lead_frames
ROOT=Path(__file__).resolve().parents[1]

def check(base,auto,level=1):
 base=base.resolve();out=base/'verification'/(f'song-hits-mesen-{level}-auto' if auto else f'song-hits-mesen-{level}-manual');out.mkdir(parents=True,exist_ok=True)
 labels={n:int(v,16)&0x1ffff for v,n in re.findall(r'al ([0-9A-Fa-f]+) \.([\w]+)',(base/'adofai.lbl').read_text())}
 levels=json.loads((base/'pack.json').read_text())['levels']
 chart=json.loads((base/f'level{level}.json').read_text())
 from hit_sound_assets import selections
 sounds=selections(chart,json.loads((ROOT/'assets/private/hitsound-levels.json').read_text())[str(level)])
 notes=[n['frame'] for n,(s,v) in zip(chart['notes'][1:],sounds[1:]) if not n['flags']&8 and s!='None' and v]
 actions={90:'y' if auto else 'x',220:'start',**{100+i*4:'down' for i in range(levels.index(level))}}
 script='local actions={'+','.join(f'[{f}]="{b}"' for f,b in actions.items())+'}\n'
 script+='local state='+str(labels['state'])+'\nlocal music='+str(labels['music_active'])+'\n'
 script+='local step='+str(labels['step'])+'\nlocal out='+json.dumps((out/'trace.csv').as_posix())+'\n'
 script+='''local W=emu.memType.snesWorkRam
local function word(a)return emu.read(a,W)+256*emu.read(a+1,W)end
local frame=0
local f=io.open(out,'w');f:write('frame,step,count,out0,out2,out3\\n')
emu.addEventCallback(function()
 local b={};if actions[frame] then b[actions[frame]]=true end;emu.setInput(b,0)
end,emu.eventType.inputPolled)
emu.addEventCallback(function()
 frame=frame+1
 if word(state)==1 and word(music)==1 then
 f:write(string.format('%d,%d,%d,%d,%d,%d\\n',frame,word(step),word(0x1fc36),emu.read(0x09,emu.memType.spcDspRegisters),emu.read(0x29,emu.memType.spcDspRegisters),emu.read(0x39,emu.memType.spcDspRegisters)))
 if word(step)>=32 then f:close();emu.stop(0) end
 end
 if frame>=4000 then f:close();emu.stop(0) end
end,emu.eventType.startFrame)
'''
 path=out/'verify.lua';path.write_text(script)
 result=subprocess.run([r'C:\mesen2\Mesen.exe','--testrunner',str(base/'adofai.sfc'),str(path)],capture_output=True,text=True,timeout=120,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
 assert result.returncode==0,result.stdout+result.stderr
 trace=list(csv.DictReader((out/'trace.csv').open()))
 assert trace and max(int(r['step']) for r in trace)>=32
 assert all(int(r['count'])==0 and int(r['out2'])==0 and int(r['out3'])==0 for r in trace), 'Unexpected second percussion voice'
 assert any(int(r['out0']) for r in trace), 'Music voice silent'
 return dict(passed=True,autoplay=auto,level=level,second_percussion_commands=0,covered_notes=max(int(r['step']) for r in trace),**identity(base/'adofai.sfc'))

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--pack',required=True);a=ap.parse_args();base=ROOT/'build/packs'/a.pack
 rows=[check(base,x) for x in [False,True]]
 (base/'verification/song-hits-mesen.json').write_text(json.dumps(dict(passed=True,cases=rows),indent=2))
 print([(r['autoplay'],r['covered_notes'],r['second_percussion_commands']) for r in rows])
if __name__=='__main__':main()
