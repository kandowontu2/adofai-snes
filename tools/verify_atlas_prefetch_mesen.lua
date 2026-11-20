-- Exercise the real prefetch oracle, including two deliberate corruptions.
local C=dofile(os.getenv('ADOFAI_TEST_CONFIG'))
assert(C.dma_script and C.dma_prefetch_begin,'Atlas controls require the live DMA oracle')
local W,S,V=emu.memType.snesWorkRam,emu.memType.snesSaveRam,emu.memType.snesVideoRam
local function word(a,m)return emu.read(a,m)+256*emu.read(a+1,m)end
local observed=false
emu.addMemoryCallback(function()
 if observed or word(0x3efb8,S)%2~=1 then return end
 local front=word(0x3ef80,S)
 local scroll=C.snapshot_aligned and 0 or 1
 local first=math.floor((C.viewport_top+scroll)/8)*32
 local last=math.floor((C.viewport_bottom-1+scroll)/8)*32+31
 for i=first,last do
  local a=0xe000+i*2;local entry=word(a,V);local glyph=entry%1024
  if (front==512 and 16384 or 0)+glyph*64==0xa7c0 then
   observed=true
   local f=assert(io.open(C.out..'/control.txt','w'));f:write(C.prefetch_test..' observed reserved glyph at clock '..word(C.addr.chart_time,W));f:close()
   if C.prefetch_test=='blank-pixels' then emu.write(0xa7c0,1,V)
   elseif C.prefetch_test=='foreign-atlas' then
    local changed=entry-glyph+(front==512 and 1 or 400)
    emu.write(a,changed%256,V);emu.write(a+1,math.floor(changed/256),V)
   end
   return
  end
 end
end,emu.callbackType.exec,C.dma_prefetch_begin,C.dma_prefetch_begin,emu.cpuType.snes)
emu.addEventCallback(function()
 if word(C.addr.state,W)==1 and word(C.addr.chart_time,W)>=600 then
  assert(observed,'Reserved glyph control was not exercised')
  assert(C.prefetch_test=='baseline','Injected atlas corruption was not rejected')
  local f=assert(io.open(C.out..'/result.txt','w'));f:write('PASS\n');f:close();emu.stop(0)
 end
end,emu.eventType.startFrame)
dofile(C.prefetch_campaign_script)
