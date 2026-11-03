local C=dofile(os.getenv('ADOFAI_SOUND_CONFIG'))
local frame=0
local function result(text,code)
 local f=io.open(C.out..'/result.txt','w');f:write(text);f:close();emu.stop(code)
end
emu.addEventCallback(function()
 local buttons={}
 if frame>=90 and frame<90+C.menu_count*4 and (frame-90)%4==0 then buttons.down=true end
 if frame==110+C.menu_count*4 then buttons.start=true end
 emu.setInput(buttons,0)
end,emu.eventType.inputPolled)
emu.addEventCallback(function()
 frame=frame+1
 if emu.read(C.state,emu.memType.snesWorkRam)==1 then
  local f=io.open(C.out..'/expected.bin','rb');local bytes=f:read('*a');f:close()
  local cursor=1
  for _,part in ipairs({{0x710,114},{0x1200,C.first},{0xC000,C.second}}) do
   for i=0,part[2]-1 do
    local actual=emu.read(part[1]+i,emu.memType.spcRam)
    if actual~=string.byte(bytes,cursor) then result('FAIL address='..(part[1]+i)..' expected='..string.byte(bytes,cursor)..' actual='..actual,1);return end
    cursor=cursor+1
   end
  end
  result('PASS '..(#bytes)..' original sample bytes match SPC RAM\n',0)
 elseif frame>3000 then result('FAIL loading timeout',1) end
end,emu.eventType.endFrame)
