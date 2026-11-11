-- Check the live hold translation and angle against the rendered curve.
return function(C)
  local H=C.holds
  local W=emu.memType.snesWorkRam
  local M=emu.memType.snesMemory
  local function word(a,t)return emu.read(a,t)+256*emu.read(a+1,t)end
  local function signed(v)return (v+32768)%65536-32768 end
  local function value(n)return word(H.addr[n],W)end
  local samples=0
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
      assert(word((224+i)*2,emu.memType.snesCgRam)==expected,'Third planet palette is not the primary-color blend')
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
    assert(math.abs(diff)<=1,'Hold planet is off the drawn orbit at floor '..step)
    for _,axis in ipairs({'x','y'}) do
      local base=H.addr['NOTE_'..string.upper(axis)]
      local delta=signed((word(base+(step+1)*2,M)-word(base+step*2,M)+h[axis])%65536)
      local offset=math.floor(math.abs(delta)*phase/256)*(delta<0 and -1 or 1)
      assert(signed(value('neo_hold_'..axis))==offset,'Hold pivot drift at floor '..step..' axis '..axis)
    end
    samples=samples+1
    if samples==1 or samples%100==0 then
      local f=io.open(C.out..'/hold-orbits.txt','w');f:write('PASS samples='..samples..'\n');f:close()
    end
  end,emu.callbackType.exec,H.complete,H.complete,emu.cpuType.snes)
end
