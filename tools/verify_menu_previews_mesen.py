"""Browse songs with real controller input and compare their hardware art."""
import argparse
import json
import os
import re
import subprocess
from pathlib import Path
from menu_sets import groups_for_pack
from menu_preview_assets import compile_preview
from verification_data import identity
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]


def verify(pack):
    out=pack/'verification/menu-previews';out.mkdir(parents=True,exist_ok=True)
    (out/'result.txt').unlink(missing_ok=True)
    (out/'manifest.json').write_text(json.dumps(dict(passed=False)))
    frozen=identity(pack/'adofai.sfc')
    labels={n:int(v,16) for v,n in re.findall(r'al ([0-9A-Fa-f]+) \.([\w]+)',(pack/'adofai.lbl').read_text())}
    rows=json.loads((pack/'menu-previews.json').read_text())
    for i,row in enumerate(rows):(out/f'expected-{i}.bin').write_bytes(compile_preview(row))
    groups=groups_for_pack(pack);actions={};checks={};frame=100
    if len(groups)>1:actions[frame]='start';frame+=12
    for group,(_,indices) in enumerate(groups):
        for at,index in enumerate(indices):
            if at:actions[frame]='down';frame+=12
            checks[frame]=index;frame+=4
        if group+1<len(groups):
            actions[frame]='b';actions[frame+8]='down';actions[frame+16]='start';frame+=28
    # Return to the first song, then test the actual exit paths without a
    # reset. VRAM bytes alone miss stale BG1 scroll/base registers.
    if len(groups)>1:
        actions[frame]='b';actions[frame+8]='down';actions[frame+16]='start';frame+=28
    elif len(groups[0][1])>1:
        actions[frame]='down';frame+=12
    checks[frame]=groups[0][1][0]
    fields=('state','display_state','frame_ready','commits','menu_depth','selected_level',
            'pattern_vblank_overruns','vblank_first_time','vblank_first_state','vblank_first_music',
            'vblank_first_queue','autoplay','practice')
    lua='local A={'+','.join(k+'='+str(labels[k]) for k in fields)+'}\n'
    lua+='local out='+json.dumps(out.as_posix())+'\n'
    lua+='dofile('+json.dumps((ROOT/'tools/mesen_failfast.lua').as_posix())+')({out=out})\n'
    lua+='local actions={'+','.join('['+str(t)+']='+json.dumps(k) for t,k in actions.items())+'}\n'
    lua+='local checks={'+','.join('['+str(t)+']='+str(i) for t,i in checks.items())+'}\n'
    lua+='local beginReturns='+str(frame+8)+'\n'
    lua+='local returnIndex='+str(groups[0][1][0])+'\n'
    first_id=json.loads((pack/'pack.json').read_text())['levels'][groups[0][1][0]]
    first_chart=json.loads((pack/f'level{first_id}.json').read_text())
    pause_age=max(1,min(48,first_chart['notes'][1]['frame']//2))
    lua+='local pauseAfter='+str(pause_age)+'\n'
    lua+=r'''
local W,V,G,M=emu.memType.snesWorkRam,emu.memType.snesVideoRam,emu.memType.snesCgRam,emu.memType.snesMemory
local function word(a,t)t=t or W;return emu.read(a,t)+256*emu.read(a+1,t)end
local frame=0;local checked=0;local graphicsWrites=0
local cases={{0,0,'pause'},{0,0,'fail'},{0,1,'pause'},{1,0,'pause'},{1,0,'finish'}}
local stage=1;local started=false;local exiting=false;local age=0;local returned=nil
local function w(n)return word(A[n])end
local function verifyArt(index,name)
  local p=emu.getState()
  local diagnostic=' state='..w('state')..' display='..w('display_state')..' ready='..w('frame_ready')..' commits='..w('commits')
  for _,c in ipairs({{'tilemapAddress',0x7000},{'chrAddress',0},{'doubleWidth',false},
                    {'doubleHeight',false},{'hscroll',0},{'vscroll',1023}}) do
   assert(p['ppu.layers[0].'..c[1]]==c[2],
    'Preview hardware '..c[1]..'='..tostring(p['ppu.layers[0].'..c[1]])..' expected '..tostring(c[2])..' '..name..diagnostic)
  end
  assert(w('pattern_vblank_overruns')==0,'Publication exceeded VBlank '..name..' time='..w('vblank_first_time')..' state='..w('vblank_first_state')..' music='..w('vblank_first_music')..' queue='..w('vblank_first_queue'))
  local f=assert(io.open(out..'/expected-'..index..'.bin','rb'));local blob=f:read('*a');f:close()
  for i=1,32 do assert(emu.read(64+i-1,G)==blob:byte(i),'Preview palette differs at '..i..' '..name)end
  for i=33,#blob do assert(emu.read(0x6000+i-33,V)==blob:byte(i),'Preview/credit CHR differs at '..i..' '..name)end
  for y=0,7 do for x=0,11 do
   assert(word(0xe000+((6+y)*32+19+x)*2,V)==0x2b00+y*12+x,'Preview map differs '..name)
  end end
  for i=0,63 do assert(word(0xe000+26*64+i*2,V)==0x2b60+i,'Credit map differs '..name)end
  for i=0,31 do assert(emu.read(0x7400+i,V)==0,'Menu blank glyph is not blank '..name)end
  for y=0,31 do for x=0,31 do
   if not (y>=6 and y<14 and x>=19 and x<31) and not (y>=26 and y<28) then
    assert(word(0xe000+(y*32+x)*2,V)==0x2ba0,'Stray preview tile obscures menu '..name)
   end
  end end
  f=assert(io.open(out..'/'..name..'.png','wb'));f:write(emu.takeScreenshot());f:close()
end
local function legal(p)return p['ppu.scanline']>=225 or p['ppu.forcedBlank']==true end
emu.addMemoryCallback(function(a,v)
 local port=emu.read(0x4301,M)
 if v%2==1 and (port==0x18 or port==0x22) then
  assert(legal(emu.getState()),'Menu DMA started outside VBlank')
  graphicsWrites=graphicsWrites+1
 end
end,emu.callbackType.write,0x420B,0x420B,emu.cpuType.snes)
emu.addEventCallback(function()
 frame=frame+1
 local index=checks[frame]
 if index~=nil then
  assert(word(A.state)==0 and word(A.menu_depth)==1,'Song browser did not open')
  assert(word(A.selected_level)==index,'Wrong selected song')
  verifyArt(index,'browse-'..checked)
  checked=checked+1
  if checked==1 then
   local f=assert(io.open(out..'/hud.txt','w'))
   for y=16,27 do
    local text=''
    for x=0,31 do local c=emu.read(0xf000+y*64+x*2,V);text=text..(c>=32 and c<127 and string.char(c) or ' ')end
    f:write(y..' '..text..'\n')
   end
   f:close()
  end
  if frame==beginReturns-8 then verifyArt(index,'return-baseline')end
 end
 if frame>=beginReturns then
  assert(frame<120000,'Timeout testing menu return case '..stage..' state='..w('state'))
  if started and w('state')==1 then age=age+1 end
  assert(not (started and cases[stage][3]=='pause' and w('state')==2),
    'Pause-route fixture missed its first note before pausing')
  if started and exiting and w('state')==0 then returned=returned or frame end
  if returned and frame-returned>=20 then
   assert(w('selected_level')==returnIndex,'Return changed song selection')
   assert(w('autoplay')==cases[stage][1] and w('practice')==cases[stage][2],'Return changed mode')
   verifyArt(returnIndex,'return-'..stage)
   stage=stage+1;started=false;exiting=false;age=0;returned=nil
   if stage>#cases then
    local f=assert(io.open(out..'/result.txt','w'));f:write('PASS songs='..checked..' returns=5 graphics_writes='..graphicsWrites..'\n');f:close();emu.stop(0)
   end
  end
 end
end,emu.eventType.startFrame)
emu.addEventCallback(function()
 local keys={}
 if actions[frame] then keys[actions[frame]]=true end
 if frame>=beginReturns and frame%8==0 and not returned and cases[stage] then
  local c=cases[stage];local s=w('state')
  if s==0 and not started then
   if w('autoplay')~=c[1] then keys.y=true
   elseif w('practice')~=c[2] then keys.x=true
   else keys.start=true;started=true end
  elseif c[3]=='pause' and s==1 and age>=pauseAfter then keys.start=true
  elseif c[3]=='pause' and s==4 then keys.select=true;exiting=true
  elseif c[3]=='fail' and s==2 then keys.select=true;exiting=true
  elseif c[3]=='finish' and s==3 then keys.select=true;exiting=true end
 end
 emu.setInput(keys,0)
end,emu.eventType.inputPolled)
'''
    script=out/'verify.lua';script.write_text(lua)
    result=subprocess.run(['C:/mesen2/Mesen.exe','--testrunner','--timeout=450',str(pack/'adofai.sfc'),str(script)],
                          capture_output=True,text=True,timeout=480,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
    (out/'emulator.log').write_text(result.stdout+result.stderr)
    outcome=(out/'result.txt').read_text() if (out/'result.txt').exists() else 'No result'
    assert result.returncode==0 and outcome.startswith('PASS '),result.stdout+result.stderr+outcome
    assert identity(pack/'adofai.sfc')==frozen
    baseline=Image.open(out/'return-baseline.png').convert('RGB')
    sx,sy=baseline.width/256,baseline.height/224
    for name,box in [('art',(152,48,248,112)),('credits',(0,208,256,224))]:
        crop=tuple(round(v*(sx if i%2==0 else sy)) for i,v in enumerate(box))
        expected=baseline.crop(crop).tobytes()
        for case in range(1,6):
            actual=Image.open(out/f'return-{case}.png').convert('RGB')
            assert actual.crop(crop).tobytes()==expected,(case,name,'Returned menu pixels changed')
    report=dict(passed=True,songs=len(rows),return_paths=5,hardware_registers=True,pixels=True,**frozen)
    (out/'manifest.json').write_text(json.dumps(report,indent=2));print(report)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--pack',type=Path,required=True)
    verify(parser.parse_args().pack.resolve())
