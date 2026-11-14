-- Preserve both sides of every live SA-1 camera-copy job for the independent
-- fixed-point and scanline-budget oracle in verify_camera_copies.py.
return function(C)
 local S=emu.memType.snesSaveRam;local W=emu.memType.snesWorkRam
 local function word(a,t)return emu.read(a,t)+256*emu.read(a+1,t)end
 local file=assert(io.open(C.out..'/camera-copies.bin','wb'));file:setvbuf('no')
 emu.addMemoryCallback(function()
  local count=word(0x3ef86,S)
  if word(C.addr.state,W)~=1 or count==0 or word(0x3ef0c,S)~=3 then return end
  -- A shorter replacement must also hide the original input's discarded
  -- tail. Checking just the returned bytes misses live, unbudgeted sprites.
  for a=word(0x3efb2,S),word(0x3efb0,S)-4,4 do
   assert(emu.read(0x201+a,W)==224,'Discarded original sprite survives camera copies')
  end
  local bytes={}
  for _,v in ipairs({word(C.addr.chart_time,W),word(0x3efb0,S),word(0x3efb2,S),count})do bytes[#bytes+1]=string.pack('<I2',v)end
  for a=0x3ef88,0x3efaf do bytes[#bytes+1]=string.char(emu.read(a,S))end
  for _,base in ipairs({0x29620,0x29840})do for a=base,base+543 do bytes[#bytes+1]=string.char(emu.read(a,S))end end
  file:write(table.concat(bytes))
 end,emu.callbackType.exec,C.copies.complete,C.copies.complete,emu.cpuType.snes)
end
