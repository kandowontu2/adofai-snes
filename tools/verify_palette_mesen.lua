-- Compare actual PPU CGRAM with the compiled musical timeline after commits.
return function(C)
  if not C.palette then return end
  local W=emu.memType.snesWorkRam
  local G=emu.memType.snesCgRam
  local function word(a,m) return emu.read(a,m)+256*emu.read(a+1,m) end
  local expected={};local cursor=1;local last=-1;local stable=0
  C.palette_samples=0
  emu.addMemoryCallback(function()
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
        local d=io.open(C.out..'/palette-failure.txt','w')
        d:write(string.format('time=%d index=%d cgram=%d staging=%d dirty=%d\n',time,i,actual,word(0x1fa20+i*2,W),word(0x1fa04,W)))
        for _,e in ipairs({{'rows',0x1fcde},{'span',0x1fce0},{'slots',0x1fce2},{'limit',0x1fce4}})do d:write(e[1]..'='..word(e[2],emu.memType.snesSaveRam)..'\n')end
        for _,name in ipairs({'animation_time','animation_kind','animation_header','animation_value','animation_index','chart_time','pattern_vblank_overruns','vblank_first_time','vblank_first_state','vblank_first_music','vblank_first_queue'})do
          if C.addr[name] then d:write(name..'='..word(C.addr[name],W)..'\n')end
        end
        d:close()
        emu.stop(1);return
      end
    end
    C.palette_samples=C.palette_samples+1
  end,emu.callbackType.write,C.addr.commits,C.addr.commits,emu.cpuType.snes)
end
