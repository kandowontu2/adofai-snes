-- Compare accelerated native streaks with the existing sprite contract.
return function(C)
  local W=emu.memType.snesWorkRam
  local M=emu.memType.snesMemory
  local function word(a,t)return emu.read(a,t)+256*emu.read(a+1,t)end
  local function signed(v)return (v+32768)%65536-32768 end
  local function value(n)return word(C.addr[n],W)end
  local arc={}
  for _,name in ipairs({'x','y','tiles','flips'}) do
    arc[name]={}
    for i=0,63 do
      local address=C.arc['orbit_arc_'..name]
      arc[name][i]=(name=='x' or name=='y') and signed(word(address+i*2,M)) or emu.read(address+i,M)
    end
  end
  local expected=nil
  local jobs=0
  emu.addMemoryCallback(function()
    local current=value('trail_current')
    local pieces=value('trail_pieces')
    local age=value('trail_age')
    local direction=signed(value('trail_previous'))
    local px=value('trail_pos_x');local py=value('trail_pos_y')
    local orb=value('trail_orb');local start=value('oam_pos')
    local budget={};local high={};local bytes={};local stroke=0
    for i=0,31 do budget[i]=emu.read(0x600+i,W);high[i]=emu.read(0x400+i,W)end
    while pieces>0 and math.floor(stroke/2)+age<4 do
      local x=signed(px+arc.x[current]);local y=signed(py+arc.y[current])
      if start+#bytes>=512 or x< -15 or x>=256 or y<32 or y>=177 then break end
      local first=math.floor(y/8);local last=math.floor((y+7)/8);local fits=true
      for i=first,last do if budget[i]>=33 then fits=false end end
      if not fits then break end
      for i=first,last do budget[i]=budget[i]+1 end
      local object=(start+#bytes)/4
      if x<0 then local i=math.floor(object/4);high[i]=high[i]+2^(2*(object%4))end
      bytes[#bytes+1]=x%256;bytes[#bytes+1]=y
      bytes[#bytes+1]=arc.tiles[current]+16*(math.floor(stroke/2)+age)
      bytes[#bytes+1]=0x38+orb*2+arc.flips[current]
      current=(current+direction)%64;stroke=stroke+1;pieces=pieces-1
    end
    expected={start=start,bytes=bytes,high=high,budget=budget,current=current,stroke=stroke,pieces=pieces}
  end,emu.callbackType.exec,C.arc.sa1_draw_arc,C.arc.sa1_draw_arc,emu.cpuType.snes)
  emu.addMemoryCallback(function()
    assert(expected,'Arc completed without input')
    local e=expected
    assert(value('oam_pos')==e.start+#e.bytes,'SA-1 streak object count differs')
    for i,v in ipairs(e.bytes) do assert(emu.read(0x200+e.start+i-1,W)==v,'SA-1 streak sprite differs')end
    for i=0,31 do
      assert(emu.read(0x400+i,W)==e.high[i],'SA-1 streak high bits differ')
      assert(emu.read(0x600+i,W)==e.budget[i],'SA-1 streak budget differs')
    end
    assert(value('trail_current')==e.current and value('trail_stroke')==e.stroke and value('trail_pieces')==e.pieces,'SA-1 streak state differs')
    jobs=jobs+1;expected=nil
    if jobs%100==0 then local f=io.open(C.out..'/sa1-arc-jobs.txt','w');f:write(jobs);f:close()end
  end,emu.callbackType.exec,C.arc.sa1_arc_complete,C.arc.sa1_arc_complete,emu.cpuType.snes)
end
