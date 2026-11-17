-- Rendering an orbit must not modify the independent stream transaction.
return function(C)
 local T=C.twirl_stream;local W=emu.memType.snesWorkRam
 local saved=nil;local checks=0
 local function word(a)return emu.read(a,W)+256*emu.read(a+1,W)end
 emu.addMemoryCallback(function()
  if word(C.addr.state)~=1 then return end
  saved={}
  for i=0x05A2,0x05FF do saved[#saved+1]=emu.read(i,W)end
 end,emu.callbackType.exec,T.entry,T.entry,emu.cpuType.snes)
 emu.addMemoryCallback(function()
  if not saved then return end
  for i,value in ipairs(saved)do
   assert(emu.read(0x05A1+i,W)==value,'Twirl overwrote animation stream state at '..string.format('%04X',0x05A1+i))
  end
  saved=nil;checks=checks+1
  if checks==1 or checks%100==0 then
   local f=assert(io.open(C.out..'/twirl-stream-memory.txt','w'));f:write('PASS checks='..checks);f:close()
  end
 end,emu.callbackType.exec,T.complete,T.complete,emu.cpuType.snes)
end
