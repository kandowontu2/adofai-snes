"""Replay real free-roam entry taps and verify each active planet's trail color.

Accepts profile_ar_section_mesen arguments; use --manual --tap-free-entries.
"""
import json,re,subprocess,sys
from pathlib import Path
import profile_ar_section_mesen as profile

def main():
    args=sys.argv[1:]
    def option(name):return args[args.index(name)+1]
    out=Path(option('--out'));labels=Path(option('--labels'))
    symbols={n:int(v,16) for v,n in re.findall(r'al ([0-9a-fA-F]+) \.([\w]+)',labels.read_text())}
    if 'SA1_FASTROM_MIRROR = 1' in (labels.parent/'addresses.inc').read_text():
        symbols['draw_orbit_arc']+=0x800000
        symbols['neo_free_input']+=0x800000
    original=subprocess.run
    def instrument(command,*pos,**kw):
        if Path(command[0]).name.lower()=='mesen.exe':
            script=Path(command[-1]);root=Path(__file__).resolve().parents[1]
            code='dofile('+json.dumps((root/'tools/mesen_failfast.lua').as_posix())+')({out='+json.dumps(out.resolve().as_posix())+'})\n'
            code+=script.read_text()
            code+='\nlocal F={'+','.join(k+'='+str(symbols[k]) for k in ('state','step','neo_free_mode','neo_free_hops','trail_orb','draw_orbit_arc','neo_free_input','tap_clock','neo_free_time','pressed'))+'}\n'
            code+='local report='+json.dumps((out/'free-trail-colors.json').resolve().as_posix())+'\n'
            code+='''local colors={[0]=0,[1]=0};local early=0
local function word(a)return emu.read(a,emu.memType.snesWorkRam)+256*emu.read(a+1,emu.memType.snesWorkRam)end
emu.addMemoryCallback(function()
 if word(F.neo_free_mode)==1 and word(F.tap_clock)<word(F.neo_free_time) and word(F.pressed)~=0 then
  assert(word(F.state)==1,'Early free-roam entry tap ended the run')
  early=early+1
 end
end,emu.callbackType.exec,F.neo_free_input+4,F.neo_free_input+4,emu.cpuType.snes)
emu.addMemoryCallback(function()
 if word(F.state)~=1 or word(F.neo_free_mode)~=1 then return end
 local hops=word(F.neo_free_hops)
 if hops==0 then return end
 local expected=(word(F.step)~hops~1)&1
 assert(word(F.trail_orb)==expected,'Free-roam trail belongs to the other planet')
 colors[expected]=colors[expected]+1
 local f=assert(io.open(report,'w'));f:write(string.format('{"red":%d,"blue":%d,"early_entries":%d}',colors[0],colors[1],early));f:close()
end,emu.callbackType.exec,F.draw_orbit_arc,F.draw_orbit_arc,emu.cpuType.snes)
'''
            script.write_text(code)
        return original(command,*pos,**kw)
    subprocess.run=instrument
    try:profile.main()
    finally:subprocess.run=original
    colors=json.loads((out/'free-trail-colors.json').read_text())
    assert min(colors['red'],colors['blue'])>20,('Both planet colors must be exercised',colors)
    if '--tap-free-entries' in args:assert colors['early_entries']>0,('Missing early entry coverage',colors)
    print(colors)

if __name__=='__main__':main()
