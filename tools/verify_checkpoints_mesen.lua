-- Exercise every original checkpoint in Mesen without writing game RAM.
local C=dofile(os.getenv('ADOFAI_TEST_CONFIG'))
if C.palette_script then dofile(C.palette_script)(C) end
local W=emu.memType.snesWorkRam
local function word(name) local a=C.addr[name];return emu.read(a,W)+256*emu.read(a+1,W) end
local frame,index,lastInput=0,1,-1
local nextInput,tapSerial=1,0
local neoInput,neoHeld=1,0
local stage,deathAt='reach',0
local frozen={}
local rows={}
local pendingRetryCapture=false
local function capture_ppu()
  local step=word("step")
  if C.graphics_dumps and (pendingRetryCapture or word("commits")%30==0) and word("display_state")==1 then
    pendingRetryCapture=false
    local S=emu.memType.snesSaveRam
    local V=emu.memType.snesVideoRam
    local function sw(a) return emu.read(a,S)+256*emu.read(a+1,S) end
    local bytes={}
    for _,value in ipairs({word("display_chart_time"),word("display_cam_x"),word("display_cam_y"),sw(0x1fcb4),sw(0x1fcb6),sw(0x1fcc8),sw(0x1fcca),step}) do
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

local function finish(good,reason)
  local f=io.open(C.out..'/result.txt','w')
  f:write(string.format('state=%d step=%d checkpoint retries=%d/%d %s\n',word('state'),word('step'),index-1,#C.checkpoints,reason or ''))
  if C.palette_samples then f:write('palette_samples='..C.palette_samples..'\n') end
  if C.addr.pattern_vblank_overruns then f:write('vblank_overruns='..word('pattern_vblank_overruns')..'\n') end
  f:write(table.concat(rows,'\n'));f:write(good and '\nPASS\n' or '\nFAIL\n');f:close()
  emu.stop(good and 0 or 1)
end
emu.addEventCallback(function()
  local state=word('state');local step=word('step');local buttons={};local cp=C.checkpoints[index]
  if C.menu_actions then
    if C.menu_actions[frame] then buttons[C.menu_actions[frame]]=true end
  else
    if frame>=90 and frame<90+(C.level-1)*2 and frame%2==0 then buttons.down=true end
    if frame==math.max(120,108+(C.level-1)*2) then buttons.start=true end
  end
  if state==1 then
    if stage=='retry' then
      pendingRetryCapture=true
      if step~=cp.floor or word('music_origin')~=cp.origin or word('checkpoint_preroll')~=1 then finish(false,'wrong restart');return end
      rows[#rows+1]=string.format('checkpoint %d trigger=%d restart=%d origin=%d',index,cp.trigger,step,word('music_origin'))
      if C.manual_steps then
        nextInput=1
        while C.manual_steps[nextInput] and C.manual_steps[nextInput]<=cp.floor do nextInput=nextInput+1 end
      end
      if C.neo_events then
        neoInput=1;neoHeld=0
        while C.neo_events[neoInput] and C.neo_events[neoInput][3]<=cp.floor do neoInput=neoInput+1 end
      end
      index=index+1;stage='reach';lastInput=-1;cp=C.checkpoints[index]
    end
    if stage=='reach' and cp and word('checkpoint_floor')==cp.floor and step>=cp.trigger then stage='die' end
    if C.neo_events then
      local delta=(word('nmi_audio_ticks')-word('audio_ticks')+32768)%65536-32768
      local offset=word('speed_offset');if offset>=32768 then offset=offset-65536 end
      local current=word('elapsed')+delta*.004*60.0988118623*C.pitch/1536-offset
      while stage~='die' and word('checkpoint_preroll')==0 and C.neo_events[neoInput] and current+1>=C.neo_events[neoInput][1] do
        neoHeld=C.neo_events[neoInput][2];neoInput=neoInput+1
      end
      if stage~='die' and word('checkpoint_preroll')==0 then
        if neoHeld%2==1 then buttons.a=true end
        if math.floor(neoHeld/2)%2==1 then buttons.b=true end
      end
    elseif C.manual_times then
      local delta=(word('nmi_audio_ticks')-word('audio_ticks')+32768)%65536-32768
      local offset=word('speed_offset');if offset>=32768 then offset=offset-65536 end
      local current=word('elapsed')+delta*.004*60.0988118623*C.pitch/1536-offset
      local target=C.manual_times[nextInput]
      local pool=frame%2==0 and {'a','x','l','up','left'} or {'b','y','r','down','right'}
      local used=0
      while stage~='die' and word('checkpoint_preroll')==0 and target and current+1>=target and used<#pool do
        used=used+1;buttons[pool[used]]=true
        nextInput=nextInput+1;tapSerial=tapSerial+1
        target=C.manual_times[nextInput]
      end
    else
      local target=C.times[step+2];local elapsed=word('elapsed')
      if stage~='die' and word('checkpoint_preroll')==0 and target and elapsed+1>=target and lastInput~=step then
        if step%2==0 then buttons.a=true else buttons.b=true end
        lastInput=step
      end
    end
  elseif state==2 then
    if stage=='die' and word('display_state')==2 then
      deathAt=frame;stage='frozen'
      for _,k in ipairs({'cam_x','cam_y','angle','chart_time'}) do frozen[k]=word(k) end
    elseif stage=='frozen' and frame-deathAt>=8 then
      for k,v in pairs(frozen) do if word(k)~=v then finish(false,'death scene moved');return end end
      buttons.start=true;stage='retry'
    elseif stage~='frozen' and stage~='retry' and stage~='die' then finish(false,'unexpected death');return end
  elseif state==3 then
    finish(index==#C.checkpoints+1 and word('checkpoints_used')==#C.checkpoints and word('step')==C.steps,'complete');return
  end
  emu.setInput(buttons,0)
end,emu.eventType.inputPolled)
emu.addEventCallback(function()
  frame=frame+1
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
  if frame>=C.frames then finish(false,'timeout') end
end,emu.eventType.startFrame)
