-- Reconstruct chart semantics independently of the worker's packed
-- metadata, dispatch and exact scanline-budget implementation.
return function(C)
 local I=C.snapshot_icons
 local W,S=emu.memType.snesWorkRam,emu.memType.snesSaveRam
 local function word(a,t)return emu.read(a,t)+256*emu.read(a+1,t)end
 local function signed(v)return (v+32768)%65536-32768 end
 local function bit(v,b)return math.floor(v/b)%2==1 end
 local expected,jobs=nil,0
 emu.addMemoryCallback(function()
  local start=word(C.addr.oam_pos,W)
  local objects,tiles,budget,high,bytes={},{},{},{},{}
  for y=C.viewport_top or 32,175 do objects[y]=0;tiles[y]=0 end
  for i=0,31 do budget[i]=emu.read(0x600+i,W);high[i]=emu.read(0x400+i,W)end
  local function charge(y,size)
   for line=math.max(C.viewport_top or 32,y),math.min(175,y+size-1)do
    objects[line]=objects[line]+1;tiles[line]=tiles[line]+size/8
   end
  end
  for a=0,start-1,4 do
   local object=a/4;local h=high[math.floor(object/4)]
   charge(emu.read(0x201+a,W),bit(h,2^(2*(object%4)+1))and 16 or 8)
  end
  local function sprite(x,y,tile,attr,size)
   size=size or 16
   if start+#bytes>=512 or x< -15 or x>=256 or y<(C.viewport_top or 32) or y>(C.viewport_bottom or 176) then return end
   for line=y,math.min(175,y+size-1)do
    if objects[line]>=32 or tiles[line]+size/8>34 then return end
   end
   charge(y,size)
   for b=math.floor(y/8),math.floor((y+size-1)/8)do budget[b]=budget[b]+size/8 end
   local object=(start+#bytes)/4;local index=math.floor(object/4)
   if size==16 then high[index]=high[index]+2^(2*(object%4)+1)end
   if x<0 then high[index]=high[index]+2^(2*(object%4))end
   bytes[#bytes+1]=x%256;bytes[#bytes+1]=y
   bytes[#bytes+1]=tile;bytes[#bytes+1]=attr
  end
  local inverse=C.symbol_scale_inverse and math.abs(signed(word(C.symbol_scale_inverse,W)))or 256
  local scale=inverse==0 and 0 or math.max(1,math.min(32,math.floor((inverse+8)/16)))
  local function event(x,y,tile,attr)
   if scale==0 then return end
   if scale==16 then return sprite(x,y,tile,attr)end
   local box=scale<=8 and 8 or scale<=16 and 16 or 32
   local center=(16-box)/2
   local first=64+(tile-32)/2*(box/8)
   if box==32 then
    sprite(x+center,y+center,first,attr+1)
    sprite(x+center+16,y+center,first+2,attr+1)
    sprite(x+center,y+center+16,first+32,attr+1)
    sprite(x+center+16,y+center+16,first+34,attr+1)
   else sprite(x+center,y+center,first,attr+1,box)end
  end
  local record=word(I.checkpoint,W)
  local activated=record==0 and -1 or word(0x1d800+record-1,W)
  for a=0,word(0x16c08,S)-1,2 do
   local floor=word(0x15000+a,S)
   local n,p=I.notes[floor+1],I.notes[floor]
   assert(n,'Projected symbol floor exceeds the chart')
   local flags,hold,ccw,planets=n[1],n[2],n[3],n[4]
   if emu.read(0x8400+floor,S)~=0 and not bit(flags,128)then
    local x,y=signed(word(0x3a400+a,S)),signed(word(0x3ba00+a,S))
    local speed=flags%4
    if speed~=0 then event(x,y,speed==1 and 32 or 34,speed==1 and 0x32 or 0x34)end
    if bit(flags,4)then event(x,y-(speed~=0 and math.floor((scale*14+8)/16)or 0),ccw~=0 and 38 or 36,ccw~=0 and 0x34 or 0x32)end
    if bit(flags,32)then
     if hold>=0 then sprite(x+(hold>=1 and 1 or 0),y,hold>=1 and 106 or 104,hold>=1 and 0x34 or 0x32)
     elseif p and p[2]>=0 then sprite(x,y,108,p[2]>=1 and 0x34 or 0x32)
     elseif p and planets~=p[4]then sprite(x,y,planets==3 and 110 or 72,0x36)end
    end
    if bit(flags,64)and word(I.attack,W)==0 then
     local stacked=speed~=0 or bit(flags,4)or bit(flags,16)or bit(flags,32)
     sprite(x,y-(stacked and 14 or 0),floor<=activated and 76 or 74,0x36)
    end
   end
  end
  expected={start=start,bytes=bytes,budget=budget,high=high,sparse=word(0x3ee42,S)==65535}
 end,emu.callbackType.exec,I.ready,I.ready,emu.cpuType.snes)
 local function complete()
  local e=assert(expected,'Snapshot icon completion without input')
  local context=' time='..word(0x1fca4,S)..' step='..word(C.addr.step,W)
  assert(word(C.addr.oam_pos,W)==e.start+#e.bytes,'Snapshot icon count differs'..context..' actual='..word(C.addr.oam_pos,W)..' expected='..(e.start+#e.bytes))
  for i,v in ipairs(e.bytes)do assert(emu.read(0x200+e.start+i-1,W)==v,'Snapshot icon byte '..i..' differs'..context..' expected='..v..' actual='..emu.read(0x200+e.start+i-1,W)..' all='..table.concat(e.bytes,','))end
  if #e.bytes>0 then
   for i=0,31 do
    assert(emu.read(0x400+i,W)==e.high[i],'Snapshot icon high bits differ'..context)
    assert(emu.read(0x600+i,W)==e.budget[i],'Snapshot icon budget differs'..context)
   end
  end
  expected=nil;jobs=jobs+1
  if jobs%100==0 then local f=assert(io.open(C.out..'/snapshot-icon-jobs.txt','w'));f:write(jobs);f:close()end
 end
 emu.addMemoryCallback(complete,emu.callbackType.exec,I.complete,I.complete,emu.cpuType.snes)
 emu.addMemoryCallback(function()if expected and expected.sparse then complete()end end,
                       emu.callbackType.exec,I.sparse_complete,I.sparse_complete,emu.cpuType.snes)
end
