-- Cosmetic work must finish before the existing controller wait ends.
return function(C)
 local count=0
 emu.addMemoryCallback(function()
  local p=emu.getState()
  assert(emu.read(0x4212,emu.memType.snesMemory)&1~=0,
         'Main scenery extended past the auto-joypad idle window at line '..p['ppu.scanline']..' cycle '..tostring(p['ppu.cycle']))
  count=count+1
  if count==1 or count%100==0 then
   local f=assert(io.open(C.out..'/main-vfx-budget.txt','w'))
   f:write('PASS idle_windows='..count);f:close()
  end
 end,emu.callbackType.exec,C.main_vfx_budget.complete,C.main_vfx_budget.complete,emu.cpuType.snes)
end
