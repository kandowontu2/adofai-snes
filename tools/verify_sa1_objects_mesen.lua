-- Independent small-sprite contract for the batched essential tile pass.
return function(C)
  local W=emu.memType.snesWorkRam;local S=emu.memType.snesSaveRam
  local function word(a,t)return emu.read(a,t)+256*emu.read(a+1,t)end
  local function signed(v)return (v+32768)%65536-32768 end
  local expected=nil;local jobs=0
  local function dump()
    local f=io.open(C.out..'/spill-failure.bin','wb')
    local bytes={}
    for a=0x2b800,0x2bdff do bytes[#bytes+1]=string.char(emu.read(a,S)) end
    for a=0x3ec00,0x3ee7f do bytes[#bytes+1]=string.char(emu.read(a,S)) end
    f:write(table.concat(bytes));f:close()
  end
  emu.addMemoryCallback(function()
    local start=word(C.addr.oam_pos,W);local count=word(0x16c32,S)
    local streamed=word(0x3ef00,S)~=0 and word(0x2b800,S)~=0
    local exact=streamed and word(0x2bc80,S)~=0
    local direct=streamed and word(0x2bc6e,S)~=0
    if streamed and not direct then count=word(0x2b800,S)end
    if exact then count=word(0x16c32,S)end
    if count==0 then expected={start=start,empty=true};return end
    local budget={};local high={};local bytes={}
    for i=0,31 do budget[i]=emu.read(0x600+i,W);high[i]=emu.read(0x400+i,W)end
    local objects,tiles={},{}
    for y=32,175 do objects[y]=0;tiles[y]=0 end
    local function charge(x,y,size)
      if x<=-size or x>=256 then return end
      for line=math.max(32,y),math.min(175,y+size-1)do
        objects[line]=objects[line]+1;tiles[line]=tiles[line]+size/8
        assert(objects[line]<=32 and tiles[line]<=34,'Exact admission exceeded hardware scanline limits')
      end
    end
    if exact then
      for i=0,start/4-1 do
        local h=math.floor(high[math.floor(i/4)]/2^(2*(i%4)))%4
        local x=emu.read(0x200+i*4,W)-(h%2==1 and 256 or 0)
        charge(x,emu.read(0x201+i*4,W),h>=2 and 16 or 8)
      end
    end
    for cell=0,count-1 do
      if start+#bytes>=512 then break end
      local a=0x38c00+cell*6;local x=signed(word(a,S));local y=signed(word(a+2,S));local tile=word(a+4,S)
      if streamed then
        a=0x2b820+cell*6
        x=signed((word(a,S)-word(0x1fcd2,S))%65536)
        y=signed((word(a+2,S)-word(0x1fcd4,S))%65536)
        tile=word(a+4,S)
      end
      if exact or direct then
        a=0x3ec00+cell*4
        x=emu.read(a,S);y=emu.read(a+1,S);tile=emu.read(a+2,S)
        local negatives=word(0x2bc26,S)
        for j=0,negatives-2,2 do if word(0x2bc28+j,S)==cell*4 then x=x-256 end end
      end
      if x>= (streamed and -7 or -15) and x<256 and y>=25 and y<177 then
        local first=math.floor(y/8);local last=math.floor((y+7)/8);local fits=true
        if not exact then for i=first,last do if budget[i]>=33 then fits=false end end end
        if fits then
          if exact then charge(x,y,8)end
          for i=first,last do budget[i]=budget[i]+1 end
          local object=(start+#bytes)/4
          if x<0 then local i=math.floor(object/4);high[i]=high[i]+2^(2*(object%4))end
          bytes[#bytes+1]=x%256;bytes[#bytes+1]=y
          bytes[#bytes+1]=tile;bytes[#bytes+1]=0x21
        end
      end
    end
    expected={start=start,bytes=bytes,budget=budget,high=high}
  end,emu.callbackType.exec,C.objects.entry,C.objects.entry,emu.cpuType.snes)
  emu.addMemoryCallback(function()
    local e=expected;assert(e,'Essential sprite job completed without input')
    if e.empty then assert(word(C.addr.oam_pos,W)==e.start);expected=nil;return end
    assert(word(C.addr.oam_pos,W)==e.start+#e.bytes,'Essential sprite count differs')
    for i,v in ipairs(e.bytes)do assert(emu.read(0x200+e.start+i-1,W)==v,'Essential sprite data differs')end
    for i=0,31 do
      if emu.read(0x400+i,W)~=e.high[i] or emu.read(0x600+i,W)~=e.budget[i] then dump() end
      assert(emu.read(0x400+i,W)==e.high[i],'Essential sprite high bits differ byte='..i..' actual='..emu.read(0x400+i,W)..' expected='..e.high[i]..' start='..e.start..' jobs='..jobs)
      assert(emu.read(0x600+i,W)==e.budget[i],'Essential sprite budget differs row='..i..' actual='..emu.read(0x600+i,W)..' expected='..e.budget[i])
    end
    expected=nil;jobs=jobs+1
    if jobs%100==0 then local f=io.open(C.out..'/sa1-object-jobs.txt','w');f:write(jobs);f:close()end
  end,emu.callbackType.exec,C.objects.complete,C.objects.complete,emu.cpuType.snes)
end
