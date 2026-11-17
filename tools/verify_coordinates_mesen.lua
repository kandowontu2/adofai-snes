-- Verify completed SA-1 poses reach the CPU before future-packet prefetch.
return function(C)
 local A=C.coordinates
 local M=emu.memType.snesMemory
 local function word(a)return emu.read(a,M)+256*emu.read(a+1,M)end
 local count=0
 emu.addMemoryCallback(function()
  local first=word(A.first);local last=word(A.last)
  if last==0 then return end
  assert(first<last and last<=A.limit,'Invalid published coordinate span')
  for offset=first,last-1,2 do
   assert(word(A.x+offset)==word(A.source_x+offset),'CPU floor X differs from completed SA-1 pose')
   assert(word(A.y+offset)==word(A.source_y+offset),'CPU floor Y differs from completed SA-1 pose')
   count=count+1
  end
  local f=assert(io.open(C.out..'/published-coordinates.txt','w'));f:write('PASS coordinates='..count..'\n');f:close()
 end,emu.callbackType.exec,A.done,A.done,emu.cpuType.snes)
end
