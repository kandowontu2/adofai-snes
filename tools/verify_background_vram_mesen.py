"""Check shared background/font VRAM on menus, gameplay, and return to menu."""
import argparse
import json
import os
import re
import subprocess
from pathlib import Path
from menu_sets import groups_for_pack
from verification_data import identity

ROOT = Path(__file__).resolve().parents[1]


def verify(pack, level, tag, boot_only=False):
    base = ROOT / 'build/packs' / pack
    out = base / 'verification' / f'background-{tag}-{level}'
    out.mkdir(parents=True, exist_ok=True)
    levels = json.loads((base / 'pack.json').read_text())['levels']
    index = levels.index(level)
    groups = groups_for_pack(base)
    group = next(i for i, (_, members) in enumerate(groups) if index in members)
    actions = {}; at = 100
    for _ in range(group):
        actions[at] = 'down'; at += 4
    actions[at] = 'start'; at += 8
    for _ in range(groups[group][1].index(index)):
        actions[at] = 'down'; at += 4
    actions[at] = 'y'; actions[at+8] = 'start'
    actions[at+700] = 'start'; actions[at+708] = 'select'
    captures = {90: 'boot', at+250: 'gameplay', at+650: 'gameplay-later', at+770: 'return'}
    config = dict(out=out.as_posix(), base=base.as_posix(), finish=at+780)
    wide='WIDE_SNAPSHOT_SUPPORT = 1' in (base/'addresses.inc').read_text()
    config.update(bg_chr=0xaa00 if wide else 0x8000,bg_map=0xb800 if wide else 0x9000,
                  bg_tile=80 if wide else 0,bg_base=0x5000 if wide else 0x4000,
                  bg_map_base=0x5c00 if wide else 0x4800)
    if boot_only:
        captures = {90: 'boot'}
        actions = {}
        config['finish'] = 100
    labels = {name: int(address,16) & 0x1ffff for address,name in
              re.findall(r'al ([0-9A-Fa-f]+) \.([\w]+)', (base/'adofai.lbl').read_text())}
    config.update(state=labels['state'], selected=labels['selected_level'], index=index)
    script = 'local C=' + '{' + ','.join(k+'='+json.dumps(v) for k,v in config.items()) + '}\n'
    script+='dofile('+json.dumps((ROOT/'tools/mesen_failfast.lua').as_posix())+')(C)\n'
    script += 'local actions={' + ','.join(f'[{k}]="{v}"' for k,v in actions.items()) + '}\n'
    script += 'local captures={' + ','.join(f'[{k}]="{v}"' for k,v in captures.items()) + '}\n'
    script += r'''
local function readfile(name)
 local f=assert(io.open(C.base..'/'..name,'rb'));local b=f:read('*a');f:close();return b
end
local chr=readfile('background.chr');local map=readfile('background.map')
local font=readfile('font.chr');local frame=0;local errors=0
local log=assert(io.open(C.out..'/result.txt','w'))
emu.addEventCallback(function()
 local b={};if actions[frame] then b[actions[frame]]=true end;emu.setInput(b,0)
end,emu.eventType.inputPolled)
emu.addEventCallback(function()
 frame=frame+1
 local name=captures[frame]
 if name then
  local f=assert(io.open(C.out..'/'..name..'.png','wb'));f:write(emu.takeScreenshot());f:close()
  local V=emu.memType.snesVideoRam;local p=emu.getState();local wrong=0
  local W=emu.memType.snesWorkRam
  local state=emu.read(C.state,W)+256*emu.read(C.state+1,W)
  local selected=emu.read(C.selected,W)+256*emu.read(C.selected+1,W)
  if name:find('gameplay') and (state~=1 or selected~=C.index) then wrong=wrong+1 end
  if (name=='boot' or name=='return') and state~=0 then wrong=wrong+1 end
  for i=1,#chr do if emu.read(C.bg_chr+i-1,V)~=chr:byte(i) then wrong=wrong+1 end end
  for i=1,#map,2 do
   local expected=map:byte(i)+256*map:byte(i+1)+C.bg_tile
   local a=C.bg_map+i-1
   if emu.read(a,V)+256*emu.read(a+1,V)~=expected then wrong=wrong+1 end
  end
  for i=1,#font,2 do
   local ink=font:byte(i)|font:byte(i+1)
   if emu.read(0xa000+i-1,V)~=ink or emu.read(0xa000+i,V)~=ink then wrong=wrong+1 end
  end
  if p['ppu.layers[1].chrAddress']~=C.bg_base or p['ppu.layers[1].tilemapAddress']~=C.bg_map_base then wrong=wrong+1 end
  log:write(name..' mismatches='..wrong..'\n');errors=errors+wrong
 end
 if frame>=C.finish then log:write(errors==0 and 'PASS\n' or 'FAIL\n');log:close();emu.stop(errors==0 and 0 or 1) end
end,emu.eventType.startFrame)
'''
    lua = out / 'verify.lua'; lua.write_text(script)
    result = subprocess.run([r'C:\mesen2\Mesen.exe', '--testrunner', str(base/'adofai.sfc'), str(lua)],
                            capture_output=True, text=True, timeout=120,
                            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    report = dict(passed=result.returncode == 0 and (out/'result.txt').exists()
                  and (out/'result.txt').read_text().endswith('PASS\n'), level=level, **identity(base/'adofai.sfc'))
    (out/'manifest.json').write_text(json.dumps(report, indent=2))
    print(report)
    assert report['passed'], result.stdout + result.stderr + ((out/'result.txt').read_text() if (out/'result.txt').exists() else '')


if __name__ == '__main__':
    p=argparse.ArgumentParser();p.add_argument('--pack',required=True)
    p.add_argument('--levels',type=int,nargs='+',default=[1,96,146]);p.add_argument('--tag',default='fixed')
    p.add_argument('--boot-only',action='store_true')
    a=p.parse_args()
    for level in a.levels:verify(a.pack,level,a.tag,a.boot_only)
