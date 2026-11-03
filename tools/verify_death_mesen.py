"""Check the reported Heracles death scene with Mesen's rendered pixels."""
import argparse,json,os,re,subprocess
from pathlib import Path
from PIL import Image,ImageChops
from verification_data import identity
ROOT=Path(__file__).resolve().parents[1]

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--base',type=Path,default=ROOT/'build/packs/master');args=ap.parse_args()
    base=args.base.resolve();out=base/'verification/death-mesen-11';out.mkdir(parents=True,exist_ok=True)
    loaded=identity(base/'adofai.sfc')
    labels={m[1]:int(m[0],16)&0x1ffff for m in re.findall(r'al ([0-9A-Fa-f]+) \.([\w]+)',(base/'adofai.lbl').read_text())}
    chart=json.loads((base/'level11.json').read_text());notes=[n['frame'] for n in chart['notes'][1:] if not(n['flags']&8) and n['step']<=152]
    script='local A={'+','.join(k+'='+str(labels[k]) for k in ['state','step','elapsed','nmi_audio_ticks','audio_ticks','display_state','speed_offset'])+'}\n'
    script+='local times={'+','.join(map(str,notes))+'}\nlocal out='+json.dumps(out.as_posix())+'\n'
    script+='''local W=emu.memType.snesWorkRam
local frame,nextInput,death=0,1,0
local function word(a)return emu.read(a,W)+256*emu.read(a+1,W)end
local function save(name,png)local h=io.open(out..'/'..name..'.png','wb');h:write(png);h:close()end
emu.addEventCallback(function()
 local b={}
 if frame>=90 and frame<110 and frame%2==0 then b.down=true end
 if frame==150 then b.start=true end
 if word(A.state)==1 then
  local delta=(word(A.nmi_audio_ticks)-word(A.audio_ticks)+32768)%65536-32768
  local offset=word(A.speed_offset);if offset>=32768 then offset=offset-65536 end
  local current=word(A.elapsed)+delta*.004*60.0988118623-offset
  local pool=frame%2==0 and {'a','x','l','up','left'} or {'b','y','r','down','right'}
  local used=0
  while times[nextInput] and current+1>=times[nextInput] and used<#pool do
   used=used+1;b[pool[used]]=true;nextInput=nextInput+1
  end
 end
 emu.setInput(b,0)
end,emu.eventType.inputPolled)
emu.addEventCallback(function()
 frame=frame+1
 if word(A.display_state)==2 then
  death=death+1
  -- Check the settled failure screen. The screenshot API can still
  -- contain a preceding video buffer during the transition.
  if death==6 then save('first',emu.takeScreenshot()) end
  if death==96 then save('frozen',emu.takeScreenshot());emu.stop(0) end
 end
 if frame>8000 then emu.stop(1) end
end,emu.eventType.startFrame)
'''
    path=out/'capture.lua';path.write_text(script)
    result=subprocess.run([r'C:\mesen2\Mesen.exe','--testrunner',str(base/'adofai.sfc'),str(path)],cwd=ROOT,
                          creationflags=subprocess.CREATE_NO_WINDOW,timeout=180,capture_output=True,text=True)
    assert result.returncode==0,result.stderr[-2000:]
    def field(path):
        im=Image.open(path).convert('RGB');return im.crop((0,im.height*32//224,im.width,im.height*160//224))
    first=field(out/'first.png');frozen=field(out/'frozen.png')
    assert ImageChops.difference(first,frozen).getbbox() is None,'Mesen death playfield changed'
    assert identity(base/'adofai.sfc')==loaded,'Dataset changed during Mesen capture'
    report=dict(**loaded,level=11,speed=1.,frozen_frames=90,death_scene_stable=True)
    (out/'result.json').write_text(json.dumps(report,indent=2));print(report,flush=True)

if __name__=='__main__':main()
