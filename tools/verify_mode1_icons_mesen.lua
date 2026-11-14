-- Reconstruct the original icon sprite contract independently of packed descriptors.
return function(C)
  local W,S=emu.memType.snesWorkRam,emu.memType.snesSaveRam
  local function word(a,t)return emu.read(a,t)+256*emu.read(a+1,t)end
  local function signed(v)return (v+32768)%65536-32768 end
  local world=dofile(C.icons.world)
  local positions,alpha,eligible,cursor,last={},{},{},1,-1
  local function world_at(time)
    if time<last or last<0 then
      positions={};alpha={};eligible={};cursor=1
      for i,p in ipairs(world.initial)do positions[i]={p[1],p[2]};alpha[i]=3 end
    end
    while world.events[cursor] and world.events[cursor][1]<=time do
      local e=world.events[cursor]
      if e[2]==28 then eligible={};for i=3,#e do eligible[#eligible+1]=e[i]end
      elseif e[2]==1 then alpha[e[3]+1]=e[4]
      else positions[e[3]+1][e[2]-1]=signed(e[4])end
      cursor=cursor+1
    end
    last=time
  end
  local expected,jobs=nil,0
  local function flag(v,b)return math.floor(v/b)%2==1 end
  emu.addMemoryCallback(function()
    world_at(word(0x1fca4,S))
    local start=word(C.addr.oam_pos,W)
    local budget,high,bytes={},{},{}
    for i=0,31 do budget[i]=emu.read(0x600+i,W);high[i]=emu.read(0x400+i,W)end
    local cp=word(C.icons.checkpoint,W)
    local activated=cp==0 and -1 or word(0x1d800+cp-1,W)
    local function sprite(x,y,tile,attr)
      if start+#bytes>=512 or x< -15 or x>=256 or y<32 or y>=177 then return end
      local first,last=math.floor(y/8),math.floor((y+15)/8)
      for i=first,last do if budget[i]>=32 then return end end
      for i=first,last do budget[i]=budget[i]+2 end
      local object=(start+#bytes)/4;local index=math.floor(object/4)
      high[index]=high[index]+2^(2*(object%4)+1)
      if x<0 then high[index]=high[index]+2^(2*(object%4))end
      bytes[#bytes+1]=x%256;bytes[#bytes+1]=y
      bytes[#bytes+1]=tile;bytes[#bytes+1]=attr
    end
    for _,floor in ipairs(eligible) do
      if alpha[floor+1]~=0 then
        local n=C.icons.notes[floor+1];local p=C.icons.notes[floor]
        local flags,hold,ccw,planets=n[1],n[2],n[3],n[4]
        local x=signed((positions[floor+1][1]-word(C.icons.cam_x,W)-8)%65536)
        local y=signed((positions[floor+1][2]-word(C.icons.cam_y,W)-8)%65536)
        local speed=flags%4
        if speed~=0 then sprite(x,y,speed==1 and 32 or 34,speed==1 and 0x32 or 0x34)end
        if flag(flags,4)then sprite(x,y-(speed~=0 and 14 or 0),ccw~=0 and 38 or 36,0x36)end
        if flag(flags,32)then
          if hold>=0 then sprite(x+(hold>=1 and 1 or 0),y,hold>=1 and 106 or 104,hold>=1 and 0x34 or 0x32)
          elseif p and p[2]>=0 then sprite(x,y,108,p[2]>=1 and 0x34 or 0x32)
          elseif p and planets~=p[4]then sprite(x,y,planets==3 and 110 or 72,0x36)end
        end
        if flag(flags,64)and word(C.icons.attack,W)==0 then
          local stacked=speed~=0 or flag(flags,4)or flag(flags,16)or flag(flags,32)
          sprite(x,y-(stacked and 14 or 0),floor<=activated and 76 or 74,0x36)
        end
      end
    end
    expected={start=start,bytes=bytes,budget=budget,high=high}
  end,emu.callbackType.exec,C.icons.ready,C.icons.ready,emu.cpuType.snes)
  emu.addMemoryCallback(function()
    local e=expected;assert(e,'Icon completion without input')
    if word(C.addr.oam_pos,W)~=e.start+#e.bytes then
      local f=io.open(C.out..'/icon-failure.txt','w');f:write('time='..last..' start='..e.start..'\nexpected='..table.concat(e.bytes,',')..'\nactual=');for i=e.start,word(C.addr.oam_pos,W)-1 do f:write(emu.read(0x200+i,W)..',')end;f:write('\n');for _,floor in ipairs(eligible)do local p=positions[floor+1];local x=signed((p[1]-word(C.icons.cam_x,W)-8)%65536);local y=signed((p[2]-word(C.icons.cam_y,W)-8)%65536);if x>=-20 and x<=260 and y>=15 and y<=200 then f:write(floor..','..x..','..y..'\n')end end;f:close()
    end
    assert(word(C.addr.oam_pos,W)==e.start+#e.bytes,'Icon count differs at '..last..' actual='..word(C.addr.oam_pos,W)..' expected='..(e.start+#e.bytes)..' floors='..table.concat(eligible,','))
    for i,v in ipairs(e.bytes)do assert(emu.read(0x200+e.start+i-1,W)==v,'Icon data differs at '..i)end
    for i=0,31 do
      assert(emu.read(0x400+i,W)==e.high[i],'Icon high bits differ')
      assert(emu.read(0x600+i,W)==e.budget[i],'Icon scanline budget differs')
    end
    expected=nil;jobs=jobs+1
    if jobs%100==0 then local f=assert(io.open(C.out..'/mode1-icon-jobs.txt','w'));f:write(jobs);f:close()end
  end,emu.callbackType.exec,C.icons.complete,C.icons.complete,emu.cpuType.snes)
end
