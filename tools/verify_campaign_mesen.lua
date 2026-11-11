-- Real-controller replay in a second, independent emulator core.
local C = dofile(os.getenv('ADOFAI_TEST_CONFIG'))
if C.palette_script then dofile(C.palette_script)(C) end
if C.arc then dofile(C.arc.script)(C) end
if C.objects then dofile(C.objects.script)(C) end
if C.holds then dofile(C.holds.script)(C) end
local W=emu.memType.snesWorkRam
local function word(address) return emu.read(address,W)+emu.read(address+1,W)*256 end
local frame=0
local lastStep=-1
local hits={}
local lastInput=-1
local nextInput=1
local neoInput=1
local neoHeld=0
local captureCounts={}
local freeSeen={}
if C.neo_grid then
  -- Capture the landing transaction, not an arbitrary frame boundary:
  -- a frame may interrupt between the X/Y writes and the hop increment.
  emu.addMemoryCallback(function(address,value)
    local g=C.neo_grid
    if word(C.addr.step)==g.step and value>0 then
      local x=word(g.x);if x>=32768 then x=x-65536 end
      local y=word(g.y);if y>=32768 then y=y-65536 end
      freeSeen[value]={x,y}
    end
  end,emu.callbackType.write,C.neo_grid.hops,C.neo_grid.hops)
end
local pcProfile=os.getenv('ADOFAI_PC_PROFILE')
local pcCounts={}
if pcProfile then
  emu.addEventCallback(function()
    if word(C.addr.state)==1 then
      local s=emu.getState()
      local pc=s['cpu.k']*65536+s['cpu.pc']
      pcCounts[pc]=(pcCounts[pc] or 0)+1
      if frame%120==0 then
        local h=io.open(pcProfile,'w')
        for p,n in pairs(pcCounts) do h:write(p..','..n..'\n') end
        h:close()
      end
    end
  end,emu.eventType.endFrame)
end
local function capture_ppu()
  local step=word(C.addr.step)
  if C.graphics_dumps and word(C.addr.commits)%30==0 and word(C.addr.display_state)==1 then
    local S=emu.memType.snesSaveRam
    local V=emu.memType.snesVideoRam
    if C.addr.oam_pos then
      local count=word(C.addr.oam_pos)
      assert(count<=512 and count%4==0,'Invalid OAM length')
      for a=0,count-1 do
        assert(emu.read(a,emu.memType.snesSpriteRam)==emu.read(0x200+a,W),'Published OAM differs from sprite buffer')
      end
      for a=512,543 do
        assert(emu.read(a,emu.memType.snesSpriteRam)==emu.read(0x200+a,W),'Published OAM high table differs')
      end
    end
    local function sw(a) return emu.read(a,S)+256*emu.read(a+1,S) end
    local bytes={}
    for _,value in ipairs({word(C.addr.display_chart_time),word(C.addr.display_cam_x),word(C.addr.display_cam_y),sw(0x1fcb4),sw(0x1fcb6),sw(0x1fcc8),sw(0x1fcca),step}) do
      bytes[#bytes+1]=string.char(value%256,math.floor(value/256))
    end
    for a=0x1f100,0x1f1ff do bytes[#bytes+1]=string.char(emu.read(a,S)) end
    for a=0,65535 do bytes[#bytes+1]=string.char(emu.read(a,V)) end
    for a=0,511 do bytes[#bytes+1]=string.char(emu.read(a,emu.memType.snesCgRam)) end
    for a=0,543 do bytes[#bytes+1]=string.char(emu.read(a,emu.memType.snesSpriteRam)) end
    local h=io.open(C.out..'/ppu-'..frame..'.bin','wb');h:write(table.concat(bytes));h:close()
  end
end
if C.graphics_dumps then
  -- This write occurs after map, pattern, residency and camera publication.
  -- endFrame can interrupt NMI before the camera metadata has caught up.
  emu.addMemoryCallback(capture_ppu,emu.callbackType.write,C.addr.commits,C.addr.commits)
end
emu.addEventCallback(function()
  local state=word(C.addr.state)
  local buttons={}
  if C.menu_actions then
    if C.menu_actions[frame] then buttons[C.menu_actions[frame]]=true end
    if C.autoplay and frame==C.autoplay_frame then buttons.y=true end
  else
    if frame>=90 and frame<90+(C.level-1)*2 and frame%2==0 then buttons.down=true end
    if frame==math.max(120,108+(C.level-1)*2) then buttons.start=true end
  end
  if state==1 and not C.autoplay then
    local step=word(C.addr.step)
    local elapsed=word(C.addr.elapsed)
    if C.neo_events then
      local delta=(word(C.addr.nmi_audio_ticks)-word(C.addr.audio_ticks)+32768)%65536-32768
      local offset=word(C.addr.speed_offset);if offset>=32768 then offset=offset-65536 end
      local current=elapsed+delta*.004*60.0988118623*C.pitch/1536-offset
      while C.neo_events[neoInput] and current+1>=C.neo_events[neoInput][1] do
        neoHeld=C.neo_events[neoInput][2];neoInput=neoInput+1
      end
      if neoHeld%2==1 then buttons.a=true end
      if math.floor(neoHeld/2)%2==1 then buttons.b=true end
    elseif C.manual_times then
      local delta=(word(C.addr.nmi_audio_ticks)-word(C.addr.audio_ticks)+32768)%65536-32768
      local offset=word(C.addr.speed_offset);if offset>=32768 then offset=offset-65536 end
      local current=elapsed+delta*.004*60.0988118623*C.pitch/1536-offset
      local target=C.manual_times[nextInput]
      local pool=frame%2==0 and {'a','x','l','up','left'} or {'b','y','r','down','right'}
      local used=0
      while target and current+1>=target and used<#pool do
        used=used+1;buttons[pool[used]]=true
        nextInput=nextInput+1
        target=C.manual_times[nextInput]
      end
    else
      local target=C.times[step+2]
      if target and elapsed+1>=target and lastInput~=step then
        if step%2==0 then buttons.a=true else buttons.b=true end
        lastInput=step
      end
    end
  end
  emu.setInput(buttons,0)
end,emu.eventType.inputPolled)
emu.addEventCallback(function()
  frame=frame+1
  local step=word(C.addr.step)
  if C.neo_grid then
    local g=C.neo_grid
    if step>g.step or word(C.addr.state)==2 or frame==C.frames then
      local good=step>g.step and word(C.addr.state)==1
      for i,p in ipairs(g.path) do
        local q=freeSeen[i]
        good=good and q~=nil and q[1]==p[1] and q[2]==p[2]
      end
      local h=io.open(C.out..'/result.txt','w')
      h:write('state='..word(C.addr.state)..' step='..step..'\n')
      for i,p in pairs(freeSeen) do h:write(i..','..p[1]..','..p[2]..'\n') end
      h:write(good and 'PASS\n' or 'FAIL\n');h:close()
      emu.stop(good and 0 or 1)
      return
    end
  end
  if C.neo_failure_step and (word(C.addr.state)==2 or frame==C.frames) then
    local good=word(C.addr.state)==2 and step==C.neo_failure_step and word(C.addr.misses)==1
    local f=io.open(C.out..'/result.txt','w')
    f:write(string.format('state=%d step=%d misses=%d\n',word(C.addr.state),step,word(C.addr.misses)))
    f:write(good and 'PASS\n' or 'FAIL\n');f:close()
    emu.stop(good and 0 or 1)
    return
  end
  if C.trace_frame==frame then
    for _,part in ipairs({{'wram',emu.memType.snesWorkRam,131072},{'bwram',emu.memType.snesSaveRam,131072},{'iram',emu.memType.sa1InternalRam,2048},{'vram',emu.memType.snesVideoRam,32768}}) do
      local bytes={}
      for a=0,part[3]-1 do bytes[#bytes+1]=string.char(emu.read(a,part[2])) end
      local h=io.open(C.out..'/trace-'..part[1]..'.bin','wb');h:write(table.concat(bytes));h:close()
    end
    local h=io.open(C.out..'/trace-state.txt','w')
    for k,v in pairs(emu.getState()) do if type(v)~='table' then h:write(k..'='..tostring(v)..'\n') end end
    h:close()
    local h=io.open(C.out..'/trace.png','wb');h:write(emu.takeScreenshot());h:close()
  end
  if C.capture_steps and frame%2==0 then
    for _,target in ipairs(C.capture_steps) do
      local count=captureCounts[target] or 0
      if step==target and count<6 then
        local png=emu.takeScreenshot()
        if png then local h=io.open(C.out..'/step-'..step..'-frame-'..frame..'.png','wb');h:write(png);h:close() end
        captureCounts[target]=count+1
      end
    end
  end
  if step~=lastStep then
    hits[#hits+1]=string.format('%d,%d,%d,%d',frame,step,word(C.addr.elapsed),word(C.addr.perfects))
    lastStep=step
  end
  if frame==90 or frame==1200 or frame==C.frames-30 then
    local png=emu.takeScreenshot()
    if png then local f=io.open(C.out..'/frame-'..frame..'.png','wb'); f:write(png);f:close() end
  end
  if frame==C.frames then
    local state=word(C.addr.state)
    local good=state==3 and step==C.steps and word(C.addr.combo)==C.hits and word(C.addr.misses)==0
    local stats=''
    if C.speed then
      local count,score=0,0
      local weights={20,40,75,100,100,100,75,40,20,0,0}
      for i=0,10 do
        local n=word(C.addr.judgment_counts+i*2)
        count=count+n;score=score+n*weights[i+1]
      end
      good=good and word(C.addr.speed_tenths)==C.speed and word(C.addr.time_attack)==C.attack
        and count==C.hits and score==word(C.addr.score_lo)+word(C.addr.score_hi)*65536
        and math.abs(word(C.addr.finish_cs)-C.finish_centis)<20
      stats=string.format('speed=%d attack=%d judgment_count=%d score=%d finish_centis=%d\n',word(C.addr.speed_tenths),word(C.addr.time_attack),count,score,word(C.addr.finish_cs))
    end
    local f=io.open(C.out..'/result.txt','w')
    f:write(string.format('state=%d steps=%d combo=%d perfects=%d misses=%d\n',state,step,word(C.addr.combo),word(C.addr.perfects),word(C.addr.misses)))
    f:write(stats)
    if C.palette_samples then f:write('palette_samples='..C.palette_samples..'\n') end
    if C.addr.pattern_vblank_overruns then f:write('vblank_overruns='..word(C.addr.pattern_vblank_overruns)..'\n') end
    f:write(table.concat(hits,'\n'))
    f:write(good and '\nPASS\n' or '\nFAIL\n');f:close()
    emu.stop(good and 0 or 1)
  end
end,emu.eventType.startFrame)
