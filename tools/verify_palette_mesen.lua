-- Compare actual PPU CGRAM with the compiled musical timeline after commits.
return function(C)
  if not C.palette then return end
  local W=emu.memType.snesWorkRam
  local G=emu.memType.snesCgRam
  local function word(a,m) return emu.read(a,m)+256*emu.read(a+1,m) end
  local expected={};local cursor=1;local last=-1;local stable=0
  C.palette_samples=0
  emu.addEventCallback(function()
    local state=word(C.addr.display_state,W)
    -- Results retain the last route; their chart counter is no longer a
    -- published playing-frame timestamp.
    if state~=1 and state~=2 then return end
    local time=word(C.addr.display_chart_time,W)
    if time==last then return end
    local changed=time<last
    if changed then cursor=1;expected={} end
    while C.palette[cursor] and C.palette[cursor][1]<=time do
      local e=C.palette[cursor];expected[e[2]]=e[3];cursor=cursor+1
      changed=true
    end
    last=time;stable=stable+1
    -- Check every color change and checkpoint rewind. Stable materials
    -- receive periodic hardware checks without repeating 192 API reads
    -- on every otherwise identical palette.
    if not changed and stable%8~=0 then return end
    for i=0,95 do
      local actual=word((32+i)*2,G)
      if actual~=(expected[i] or 0) then
        local f=io.open(C.out..'/result.txt','w')
        f:write(string.format('CGRAM mismatch time=%d index=%d actual=%d expected=%d\nFAIL\n',time,i,actual,expected[i] or 0));f:close()
        emu.stop(1);return
      end
    end
    C.palette_samples=C.palette_samples+1
  end,emu.eventType.startFrame)
end
