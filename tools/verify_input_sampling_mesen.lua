-- Compare the ROM's complete joypad sample with the controller replay.
-- In particular, a shifting auto-read result must never become extra taps.
return function(C)
 local expected=nil;local samples=0;local set=emu.setInput;local atRead=nil;local readInfo='';local stop=emu.stop
 -- stop() is deferred until the current emulation slice returns. Once the
 -- replay ends it no longer supplies controller overrides for that slice.
 emu.stop=function(...)expected=nil;atRead=nil;return stop(...)end
 local bits={b=0x8000,y=0x4000,select=0x2000,start=0x1000,up=0x0800,down=0x0400,left=0x0200,right=0x0100,a=0x0080,x=0x0040,l=0x0020,r=0x0010}
 emu.setInput=function(buttons,port)
  if port==0 then
   expected=0
   for name,bit in pairs(bits)do if buttons[name]then expected=expected+bit end end
  end
  return set(buttons,port)
 end
 emu.addMemoryCallback(function()
  atRead=expected;local p=emu.getState()
  readInfo=string.format(' frame=%d scan=%d state=%d',p['ppu.frameCount'],p['ppu.scanline'],emu.read(C.addr.state,emu.memType.snesWorkRam))
 end,emu.callbackType.read,0x4218,0x4218,emu.cpuType.snes)
 emu.addMemoryCallback(function(a,v)
  if atRead==nil then return end
  local actual=emu.read(C.addr.joy,emu.memType.snesWorkRam)+v*256
  assert(actual==atRead,string.format('Joypad sample differs from replay: actual=%04X expected=%04X',actual,atRead)..readInfo)
  samples=samples+1
  if samples%100==0 then local f=io.open(C.out..'/input-sampling.txt','w');f:write('PASS samples='..samples);f:close()end
 end,emu.callbackType.write,C.addr.joy+1,C.addr.joy+1,emu.cpuType.snes)
end
