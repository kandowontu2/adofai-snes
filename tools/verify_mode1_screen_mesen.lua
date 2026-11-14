-- Verify actual PPU configuration against the published world camera.
return function(C)
 if not C.mode1_runtime then return end
 local W,S=emu.memType.snesWorkRam,emu.memType.snesSaveRam
 local function word(a,m)return emu.read(a,m)+256*emu.read(a+1,m)end
 local samples=0
 local saved={}
 emu.addMemoryCallback(function()
  local mode=word(0x3ef0c,S)
  if mode==0 or word(C.addr.display_state,W)~=1 then return end
  local p=emu.getState()
  local x=word(C.addr.display_cam_x,W)%1024
  local y=(word(C.addr.display_cam_y,W)-1)%1024
  if mode>=2 then x=0;y=0 end
  local checks={
   {'ppu.layers[0].hscroll',x},{'ppu.layers[0].vscroll',y},
   {'ppu.layers[0].tilemapAddress',0x7000},{'ppu.layers[0].chrAddress',0},
   {'ppu.layers[0].doubleWidth',true},{'ppu.layers[0].doubleHeight',false},
   {'ppu.layers[0].largeTiles',false}}
  for _,c in ipairs(checks)do
   if p[c[1]]~=c[2]then
    local msg=string.format('Hardware screen mismatch at chart %d: %s actual=%s expected=%s',word(C.addr.display_chart_time,W),c[1],tostring(p[c[1]]),tostring(c[2]))
    local f=io.open(C.out..'/screen-failure.png','wb');f:write(emu.takeScreenshot());f:close()
    assert(false,msg)
   end
  end
  samples=samples+1
  if samples==1 or samples%100==0 then local f=io.open(C.out..'/screen-registers.txt','w');f:write('PASS samples='..samples);f:close() end
 end,emu.callbackType.write,C.addr.commits,C.addr.commits,emu.cpuType.snes)
 emu.addEventCallback(function()
  if word(0x3ef0c,S)==0 or word(C.addr.display_state,W)~=1 then return end
  local time=word(C.addr.display_chart_time,W)
  for _,at in ipairs(C.screen_captures or {})do
   if not saved[at] and time>=at and time<=at+2 then
    saved[at]=true
    local f=io.open(C.out..'/screen-'..at..'.png','wb');f:write(emu.takeScreenshot());f:close()
   end
  end
 end,emu.eventType.endFrame)
end
