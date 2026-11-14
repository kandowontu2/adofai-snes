-- Check the real PPU state, independently of the engine's budget counter.
return function(C)
 local W=emu.memType.snesWorkRam;local M=emu.memType.snesMemory
 local function word(a)return emu.read(a,W)+256*emu.read(a+1,W)end
 local function legal(p)return p['ppu.scanline']>=225 or p['ppu.forcedBlank']==true end
 local start=nil;local writes=0;local extended=0;local commits=0;local ends=0;local lastEnd=nil;local startLines={}
 local remaining=0;local began=0;local bytes=0;local bounded=false
 local prefetch=false;local prefetches=0;local vramAddress=0;local front=0
 emu.addMemoryCallback(function(a,v)vramAddress=(vramAddress-vramAddress%256)+v end,emu.callbackType.write,0x2116,0x2116,emu.cpuType.snes)
 emu.addMemoryCallback(function(a,v)vramAddress=vramAddress%256+256*v end,emu.callbackType.write,0x2117,0x2117,emu.cpuType.snes)
 if C.dma_prefetch_begin then
  emu.addMemoryCallback(function()
   prefetch=true;prefetches=prefetches+1
   local S,V=emu.memType.snesSaveRam,emu.memType.snesVideoRam
   front=emu.read(0x3ef80,S)+256*emu.read(0x3ef81,S)
   assert(front==0 or front==512,'Invalid front atlas bank')
   -- Check the real map's references, not only the producer's bank flag.
   for i=0,607 do
    local a=0xe100+i*2;local entry=emu.read(a,V)+256*emu.read(a+1,V);local glyph=entry%1024
    assert(glyph==0 or (glyph>=512 and 512 or 0)==front,'Prefetch front bank differs from hardware map')
   end
  end,emu.callbackType.exec,C.dma_prefetch_begin,C.dma_prefetch_begin,emu.cpuType.snes)
 end
 emu.addMemoryCallback(function(a,v)
  local relevant=false;local size=0
  for i=0,7 do if math.floor(v/2^i)%2==1 then
   local base=0x4300+i*16;local port=emu.read(base+1,M)
   if C.dma_prefetch_begin and i==0 and port==0x80 and emu.read(base,M)==8 then
    local source=emu.read(base+2,M)+256*emu.read(base+3,M)
    if source==0x2001 and emu.read(base+4,M)==0 then
     local S=emu.memType.snesSaveRam
     local running=emu.read(0x3ef2e,S)+256*emu.read(0x3ef2f,S)
     assert(running==0,'Audio refill reprogrammed DMA 0 during an early graphics upload')
    end
   end
   if emu.read(base,M)<128 and (port==4 or port==0x18 or port==0x19 or port==0x22)then
    relevant=true;local n=emu.read(base+5,M)+256*emu.read(base+6,M);size=size+(n==0 and 65536 or n)
   end
  end end
  if not relevant then return end
  if prefetch then
   assert(v==32,'Atlas prefetch touched a different DMA channel')
   local source=emu.read(0x4352,M)+256*emu.read(0x4353,M)
   local bank=source>=16384 and 512 or 0
   assert(bank~=front and source+size<=(bank==512 and 32768 or 16384),'Prefetch overwrote the visible atlas')
   assert(vramAddress*2==source,'Prefetch destination differs from its back atlas')
  end
  local p=emu.getState()
  assert(legal(p),'PPU DMA started outside VBlank/forced blank at scanline '..p['ppu.scanline']..' state='..word(C.addr.state)..' clock='..word(C.addr.chart_time)..' ready='..word(C.addr.frame_ready)..' pc='..p['cpu.k']..':'..p['cpu.pc'])
  writes=writes+1
  assert(remaining==0,'A PPU DMA did not deliver all of its bytes')
  remaining=size;began=p.masterClock
  bounded=word(C.addr.frame_ready)~=0 and word(C.addr.state)==1
  if p['ppu.scanline']<225 then extended=extended+1 end
  if word(C.addr.frame_ready)~=0 and word(C.addr.state)==1 and not start then
   start=p.masterClock;local line=p['ppu.scanline'];startLines[line]=(startLines[line] or 0)+1
  end
 end,emu.callbackType.write,0x420b,0x420b,emu.cpuType.snes)
 -- An instruction-fetch callback can run before pending DMA actually
 -- starts. Count the real writes to the PPU ports instead; the last byte
 -- proves completion, without relying on instruction-fetch ordering.
 local function portWrite(a)
  if prefetch then assert(a==0x2118 or a==0x2119,'Prefetch changed live OAM or palette')end
  bytes=bytes+1
  if remaining==0 then
   local p=emu.getState();assert(legal(p),'Direct PPU write outside blanking')
   return
  end
  remaining=remaining-1
  if remaining~=0 and remaining%64==0 then
   local p=emu.getState();assert(legal(p),'PPU DMA byte outside blanking at scanline '..p['ppu.scanline']..' clock='..word(C.addr.chart_time))
  end
  if remaining~=0 then return end
  local p=emu.getState();ends=ends+1;lastEnd=p.masterClock
  assert(legal(p),'PPU DMA last byte outside VBlank/forced blank at scanline '..p['ppu.scanline']..' clock='..word(C.addr.chart_time))
  assert(not bounded or p.masterClock-began<54*1364,'Individual PPU DMA crossed a display interval')
 end
 for _,port in ipairs({0x2104,0x2118,0x2119,0x2122})do
  emu.addMemoryCallback(portWrite,emu.callbackType.write,port,port,emu.cpuType.snes)
 end
 local function complete()
  if not start then return end
  local p=emu.getState()
  assert(ends==writes,'Missing post-DMA completion callback')
  assert(lastEnd and lastEnd-start<54*1364,'Scene transfer crossed an entire display interval')
  start=nil;commits=commits+1
  if commits%100==0 then
   local f=io.open(C.out..'/dma-window.txt','w')
   f:write('PASS commits='..commits..' transfers='..writes..' completions='..ends..' bytes='..bytes..' extended='..extended..' prefetches='..prefetches);f:close()
   local h=io.open(C.out..'/dma-start-lines.txt','w')
   for line=0,311 do if startLines[line] then h:write(line..','..startLines[line]..'\n') end end;h:close()
  end
 end
 emu.addMemoryCallback(complete,emu.callbackType.exec,C.dma_complete,C.dma_complete,emu.cpuType.snes)
 if C.dma_prefetch_complete then
  emu.addMemoryCallback(function()complete();prefetch=false end,emu.callbackType.exec,C.dma_prefetch_complete,C.dma_prefetch_complete,emu.cpuType.snes)
 end
end
