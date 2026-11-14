-- Check the live hold translation and angle against the rendered curve.
return function(C)
  local H=C.holds
  local W=emu.memType.snesWorkRam
  local M=emu.memType.snesMemory
  local S=emu.memType.snesSaveRam
  local function word(a,t)return emu.read(a,t)+256*emu.read(a+1,t)end
  local function signed(v)return (v+32768)%65536-32768 end
  local function value(n)return word(H.addr[n],W)end
  local samples=0
  local planet_samples=0
  local function check(ok,message)
    if ok then return true end
    local f=io.open(C.out..'/result.txt','w');f:write(message..'\nFAIL\n');f:close()
    emu.stop(1)
    return false
  end
  emu.addMemoryCallback(function()
    if value('state')~=1 or value('palette_dirty')~=0 then return end
    for i=0,15 do
      local a=word((192+i)*2,emu.memType.snesCgRam)
      local b=word((208+i)*2,emu.memType.snesCgRam)
      local expected=0
      for _,shift in ipairs({0,5,10}) do
        local unit=2^shift
        expected=expected+math.floor((math.floor(a/unit)%32+math.floor(b/unit)%32)/2)*unit
      end
      if not check(word((224+i)*2,emu.memType.snesCgRam)==expected,'Third planet palette is not the primary-color blend') then return end
    end
  end,emu.callbackType.write,C.addr.commits,C.addr.commits)
  -- Check committed planet OAM as well as the arithmetic workspace.
  -- Unit projection covers the native-scale T1 stretching regression.
  emu.addMemoryCallback(function()
    if value('state')~=1 or word(0x1fccc,S)~=256 or word(0x1fcce,S)~=0 then return end
    local step=value('step');local h=H.notes[step]
    if not h then return end
    local time=value('chart_time');local radius=value('m7_radius')
    if time<h.start or time>=h.finish or radius<5 or radius>8 then return end
    local position={}
    for _,axis in ipairs({'x','y'}) do
      local base=H.addr['NOTE_'..string.upper(axis)];local mem=M
      if C.stream_runtime and word(0x3ef00,S)==1 and word(0x2b200,S)~=0 then
        base=axis=='x' and 0x10000 or 0x12200;mem=S
      end
      local start=word(base+step*2,mem)
      local delta=signed((word(base+(step+1)*2,mem)-start+h[axis])%65536)
      local offset=math.floor(math.abs(delta)*value('neo_hold_phase')/256)*(delta<0 and -1 or 1)
      -- floor_position subtracts the shared raster origin before projection.
      -- SYMBOL/NOTE coordinates themselves stay in authored world space.
      local origin=word(axis=='x' and 0x1fcda or 0x1fcdc,S)
      position[axis]=signed((start+offset-origin-value('cam_'..axis)-8)%65536)
    end
    local O=emu.memType.snesSpriteRam
    for orb=0,1 do
      local x=position.x+(orb==1 and signed(value('orbit_x')) or 0)
      local y=position.y+(orb==1 and signed(value('orbit_y')) or 0)
      if x>=0 and x<=240 and y>=32 and y<=160 then
        if not check(emu.read(orb*16,O)==x and emu.read(orb*16+1,O)==y,
          'Hold planet missing/displaced at floor '..step..' orb '..orb..' time '..time..' actual='..emu.read(orb*16,O)..','..emu.read(orb*16+1,O)..' expected='..x..','..y..' phase='..value('neo_hold_phase')) then return end
        planet_samples=planet_samples+1
      end
    end
    if planet_samples==1 or planet_samples%100<2 then
      local f=io.open(C.out..'/hold-planets.txt','w');f:write('PASS samples='..planet_samples..'\n');f:close()
    end
  end,emu.callbackType.write,C.addr.commits,C.addr.commits)
  emu.addMemoryCallback(function()
    if value('state')~=1 then return end
    local step=value('step');local h=H.notes[step]
    if not h then return end
    local time=value('chart_time')
    if time<h.start or time>=h.finish then return end
    local phase=value('neo_hold_phase')
    local expected=math.floor(h.angle+h.sweep*phase/256+0.5)%256
    local diff=(value('angle')-expected+128)%256-128
    if not check(math.abs(diff)<=1,'Hold planet is off the drawn orbit at floor '..step) then return end
    for _,axis in ipairs({'x','y'}) do
      local base=H.addr['NOTE_'..string.upper(axis)]
      local mem=M
      if C.stream_runtime and word(0x3ef00,S)==1 and word(0x2b200,S)~=0 then
        base=axis=='x' and 0x10000 or 0x12200;mem=S
      end
      local delta=signed((word(base+(step+1)*2,mem)-word(base+step*2,mem)+h[axis])%65536)
      local offset=math.floor(math.abs(delta)*phase/256)*(delta<0 and -1 or 1)
      if not check(signed(value('neo_hold_'..axis))==offset,'Hold pivot drift at floor '..step..' axis '..axis..' actual='..signed(value('neo_hold_'..axis))..' expected='..offset..' phase='..phase..' time='..time) then return end
    end
    samples=samples+1
    if samples==1 or samples%100==0 then
      local f=io.open(C.out..'/hold-orbits.txt','w');f:write('PASS samples='..samples..'\n');f:close()
    end
  end,emu.callbackType.exec,H.complete,H.complete,emu.cpuType.snes)
end
