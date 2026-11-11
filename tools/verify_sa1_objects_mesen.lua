-- Independent small-sprite contract for the batched essential tile pass.
return function(C)
  local W=emu.memType.snesWorkRam;local S=emu.memType.snesSaveRam
  local function word(a,t)return emu.read(a,t)+256*emu.read(a+1,t)end
  local function signed(v)return (v+32768)%65536-32768 end
  local expected=nil;local jobs=0
  emu.addMemoryCallback(function()
    local start=word(C.addr.oam_pos,W);local count=word(0x16c32,S)
    if count==0 then expected={start=start,empty=true};return end
    local budget={};local high={};local bytes={}
    for i=0,31 do budget[i]=emu.read(0x600+i,W);high[i]=emu.read(0x400+i,W)end
    for cell=0,count-1 do
      if start+#bytes>=512 then break end
      local a=0x38c00+cell*6;local x=signed(word(a,S));local y=signed(word(a+2,S));local tile=word(a+4,S)
      if x>= -15 and x<256 and y>=25 and y<177 then
        local first=math.floor(y/8);local last=math.floor((y+7)/8);local fits=true
        for i=first,last do if budget[i]>=33 then fits=false end end
        if fits then
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
      assert(emu.read(0x400+i,W)==e.high[i],'Essential sprite high bits differ')
      assert(emu.read(0x600+i,W)==e.budget[i],'Essential sprite budget differs')
    end
    expected=nil;jobs=jobs+1
    if jobs%100==0 then local f=io.open(C.out..'/sa1-object-jobs.txt','w');f:write(jobs);f:close()end
  end,emu.callbackType.exec,C.objects.complete,C.objects.complete,emu.cpuType.snes)
end
