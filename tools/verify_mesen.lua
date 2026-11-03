-- Real-controller replay in a second, independent emulator core.
local C = dofile(os.getenv('ADOFAI_TEST_CONFIG'))
local W=emu.memType.snesWorkRam
local function word(address) return emu.read(address,W)+emu.read(address+1,W)*256 end
local frame=0
local lastStep=-1
local hits={}
local lastInput=-1
emu.addEventCallback(function()
  local state=word(C.addr.state)
  local buttons={}
  if frame==120 then buttons.start=true end
  if state==1 then
    local step=word(C.addr.step)
    local elapsed=word(C.addr.elapsed)
    local target=C.times[step+2]
    if target and elapsed+1>=target and elapsed+1<=target+2 and lastInput~=step then
      buttons.a=true
      lastInput=step
    end
  end
  emu.setInput(buttons,0)
end,emu.eventType.inputPolled)
emu.addEventCallback(function()
  frame=frame+1
  local step=word(C.addr.step)
  if step~=lastStep then
    hits[#hits+1]=string.format('%d,%d,%d,%d',frame,step,word(C.addr.elapsed),word(C.addr.perfects))
    lastStep=step
  end
  if frame==90 or frame==1200 or frame==4700 then
    local png=emu.takeScreenshot()
    if png then local f=io.open(C.out..'/frame-'..frame..'.png','wb'); f:write(png);f:close() end
  end
  if frame==5100 then
    local state=word(C.addr.state)
    local good=state==3 and step==167 and word(C.addr.combo)==167 and word(C.addr.misses)==0
    local f=io.open(C.out..'/result.txt','w')
    f:write(string.format('state=%d steps=%d combo=%d perfects=%d misses=%d\n',state,step,word(C.addr.combo),word(C.addr.perfects),word(C.addr.misses)))
    f:write(table.concat(hits,'\n'))
    f:write(good and '\nPASS\n' or '\nFAIL\n');f:close()
    emu.stop(good and 0 or 1)
  end
end,emu.eventType.startFrame)
