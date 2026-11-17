-- Check the insertion guide against native entry vectors and live world
-- coordinates. Neither baked frames nor the cartridge's preview table is
-- used as its own visual-position oracle.
return function(C)
 local P=C.preview;local W=emu.memType.snesWorkRam;local M=emu.memType.snesMemory
 local function word(a,t)return emu.read(a,t)+256*emu.read(a+1,t)end
 local function w(a)return word(a,W)end
 local function bus(a)return word(a,M)end
 local function signed(v)return (v+32768)%65536-32768 end
 local function mul(a,b)return math.floor((a*b+128)/256)end
 local circles,dashes=0,0;local vertices=nil;local index=0
 local function report()
  local f=assert(io.open(C.out..'/planet-previews.txt','w'))
  f:write('PASS circles='..circles..' dashes='..dashes..'\n');f:close()
 end
 emu.addMemoryCallback(function()
  if w(C.addr.state)~=1 then return end
  local floor=w(P.addr.render_i);local row=assert(P.entries[floor],'Preview on an ordinary/pause/two-planet floor')
  assert(floor>w(C.addr.step),'Insertion preview survived the third planet entering')
  local x=signed(bus(P.source_x+floor*2)-bus(0x41FCDA))
  local y=signed(bus(P.source_y+floor*2)-bus(0x41FCDC))
  local co=signed(bus(0x41FCCC));local si=signed(bus(0x41FCCE))
  local function project(px,py)
   local dx=signed(px-w(P.addr.cam_x)-128);local dy=signed(py-w(P.addr.cam_y)-104)
   return {mul(dx,co)-mul(dy,si)+128,mul(dx,si)+mul(dy,co)+104}
  end
  vertices={project(x,y),project(x+row[1],y+row[2]),project(x+row[3],y+row[4])}
  local q=vertices[3]
  assert(math.abs(signed(w(P.addr.sprite_x))-(q[1]-8))<=1 and math.abs(signed(w(P.addr.sprite_y))-(q[2]-8))<=1,
         'White preview planet detached from its entry tile at floor '..floor)
  assert(w(P.addr.sprite_attr)==0x3e,'Preview planet is not using the white palette')
  for i=1,7 do
   assert(word((240+i)*2,emu.memType.snesCgRam)==0x7fff,'White preview palette was not installed')
  end
  assert(word(255*2,emu.memType.snesCgRam)==0x56b5,'Insertion guide must be quieter than its white planet')
  index=0;circles=circles+1
 end,emu.callbackType.exec,P.circle,P.circle,emu.cpuType.snes)
 emu.addMemoryCallback(function()
  if w(C.addr.state)~=1 then return end
  assert(vertices and index<9,'Missing or excessive insertion guide dashes')
  local edge=math.floor(index/3)+1;local part=index%3+1
  local a,b=vertices[edge],vertices[edge%3+1]
  local x=math.floor(((4-part)*a[1]+part*b[1])/4)-4
  local y=math.floor(((4-part)*a[2]+part*b[2])/4)-4
  assert(math.abs(signed(w(P.addr.sprite_x))-x)<=1 and math.abs(signed(w(P.addr.sprite_y))-y)<=1,
         'Dashed insertion guide does not follow the projected triangle')
  assert(w(P.addr.sprite_attr)==0x3f,'Preview guide palette or CHR bank is incorrect')
  index=index+1;dashes=dashes+1
 end,emu.callbackType.exec,P.dash,P.dash,emu.cpuType.snes)
 emu.addEventCallback(function()if w(C.addr.state)==3 then report()end end,emu.eventType.endFrame)
end
