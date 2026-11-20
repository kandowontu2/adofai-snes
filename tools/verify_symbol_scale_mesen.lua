-- Verify actual published scaled artwork in VRAM for both renderers.
return function(C)
 local W,S=emu.memType.snesWorkRam,emu.memType.snesSaveRam
 local function word(a,t)return emu.read(a,t)+256*emu.read(a+1,t)end
 local G=C.symbol_scale
 if G then
  local f=assert(io.open(G.frames,'rb'));local frames=f:read('*a');f:close()
  local function u16(at)return frames:byte(at+1)+256*frames:byte(at+2)end
  local previous,checks,frame=nil,0,0
  emu.addEventCallback(function()
   frame=frame+1
   if word(C.addr.state,W)~=1 or word(G.pending,S)~=0 or word(G.irq,S)~=0 then return end
   local size=word(G.loaded,S);local vram=word(G.vram,S)
   if size==16 or size<1 or size>32 then return end
   local key=size*65536+vram
   if key==previous and frame%240~=0 then return end
   local at=u16((size-1)*4);local count=u16((size-1)*4+2)
   for offset=0,count-1 do
    local address=vram*2+offset
    if count==512 and offset>=256 then address=address+256 end
    assert(emu.read(address,emu.memType.snesVideoRam)==frames:byte(at+offset+1),'Scaled symbol CHR differs at '..address..' size='..size)
   end
   checks=checks+1;previous=key
   local h=assert(io.open(C.out..'/symbol-scale-pixels.txt','w'));h:write('PASS checks='..checks);h:close()
  end,emu.eventType.endFrame)
 end
end
