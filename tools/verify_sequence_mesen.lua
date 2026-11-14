local Q=dofile(os.getenv('ADOFAI_SEQUENCE_CONFIG'))
dofile(Q.guard)(Q)
local W=emu.memType.snesWorkRam
local function word(a) return emu.read(a,W)+256*emu.read(a+1,W) end
local active=1
local frame=0
local configs={}
for i,stage in ipairs(Q.stages) do
 local C=dofile(stage.config);C.out=stage.out;configs[i]=C
 local memory,event=emu.addMemoryCallback,emu.addEventCallback
 emu.addMemoryCallback=function(fn,...) return memory(function(...) if active==i then return fn(...) end end,...) end
 emu.addEventCallback=function(fn,...) return event(function(...) if active==i then return fn(...) end end,...) end
 if C.dma_script then dofile(C.dma_script)(C) end
 if C.input_script then dofile(C.input_script)(C) end
 if C.screen_script then dofile(C.screen_script)(C) end
 if C.palette_script then dofile(C.palette_script)(C) end
 for _,key in ipairs({'icons','arc','objects','holds','copies','math','midspin'}) do if C[key] then dofile(C[key].script)(C) end end
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
    if C.mode1_runtime and sw(0x3ef0c)~=0 then
      bytes[#bytes+1]=string.char(sw(0x3ef0c))
      for a=0x29400,0x2945f do bytes[#bytes+1]=string.char(emu.read(a,S)) end
      for a=0x2a000,0x2a0bf do bytes[#bytes+1]=string.char(emu.read(a,S)) end
    end
    local h=io.open(C.out..'/ppu-'..frame..'.bin','wb');h:write(table.concat(bytes));h:close()
  end
end

 emu.addMemoryCallback(capture_ppu,emu.callbackType.write,C.addr.commits,C.addr.commits)
 emu.addMemoryCallback=memory;emu.addEventCallback=event
end
local finished=false
local started=false
local nextMenuFrame=90
emu.addEventCallback(function()
 frame=frame+1
 assert(frame<Q.frames,'Sequence timed out')
 local state=word(Q.addr.state)
 if frame%300==0 then local f=io.open(Q.out..'/progress.txt','w');f:write(frame..','..state..','..word(Q.addr.step)..','..active);f:close() end
 if state==1 then started=true;assert(word(Q.addr.selected_level)==Q.stages[active].level,'Wrong song') end
 if state==2 then error('Autoplay died in stage '..active) end
 if state==3 and started and not finished then
  local C=configs[active]
  assert(word(Q.addr.step)==C.steps,'Incomplete song')
  assert(word(Q.addr.misses)==0,'Misses')
  assert(word(Q.addr.pattern_vblank_overruns)==0,'VBlank overrun')
  local f=assert(io.open(C.out..'/result.txt','w'));f:write('PASS\n');f:close()
  finished=true
  if active==#Q.stages then
   local f=assert(io.open(Q.out..'/result.txt','w'));f:write('PASS\n');f:close();emu.stop(0)
  end
 end
 if state==0 and finished then active=active+1;finished=false;started=false end
end,emu.eventType.startFrame)
emu.addEventCallback(function()
 local buttons={}
 if frame>=nextMenuFrame and frame%8==0 then
  local state=word(Q.addr.state);local stage=Q.stages[active]
  if state==3 and finished then buttons.select=true
  elseif state==0 then
   if word(Q.addr.menu_depth)==0 then
    local g=word(Q.addr.menu_selection)
    if g~=stage.group then buttons[g<stage.group and 'down' or 'up']=true else buttons.start=true end
   elseif word(Q.addr.menu_group)~=stage.group then
    -- Returning from a song retains its set submenu. Back out before
    -- selecting a song from a different set, exactly as a player would.
    buttons.b=true
   else
    local s=word(Q.addr.menu_selection)
    if s~=stage.selection then buttons[s<stage.selection and 'down' or 'up']=true
    elseif word(Q.addr.autoplay)==0 then buttons.y=true else buttons.start=true;nextMenuFrame=frame+180 end
   end
  end
 end
 emu.setInput(buttons,0)
end,emu.eventType.inputPolled)
