-- Independently check handedness of the three live planet positions.
return function(C)
 local T=C.triplet;local W=emu.memType.snesWorkRam
 local function w(a)return emu.read(a,W)+256*emu.read(a+1,W)end
 local function signed(v)return (v+32768)%65536-32768 end
 local function hidden(p)return p.x==-4096 and p.y==-4096 end
 local points={};local samples=0;local births=0;local culled=0;local handoffs=0;local previous=nil;local previousTwo=nil;local inThree=false
 local function report()
  local f=assert(io.open(C.out..'/triplet-geometry.txt','w'))
  f:write('PASS oriented_triangles='..samples..' activation_handoffs='..births..' culled_triangles='..culled..' twirl_handoffs='..handoffs..'\n');f:close()
 end
 emu.addMemoryCallback(function()
  if w(C.addr.state)~=1 or w(C.addr.selected_level)~=C.level-1 then return end
  local slot=w(C.addr.oam_pos)
  if slot~=0 and slot~=16 and slot~=32 then return end
  local point={x=signed(w(T.x)),y=signed(w(T.y)),color=math.floor(w(T.attr)/2)%4}
  if T.continuity then
   local M=emu.memType.snesMemory
   local function bus(a)return emu.read(a,M)+256*emu.read(a+1,M)end
   point.wx=(w(T.fx)+bus(0x41FCDA))%65536
   point.wy=(w(T.fy)+bus(0x41FCDC))%65536
  end
  if slot==0 then points={} end
  points[slot]=point
  local control=T.controls[w(C.addr.step)+1]
  if not control then return end
  if control<2 then
   if slot==16 and points[0] then previousTwo={points[0].color,point.color,w(C.addr.step)};inThree=false end
   return
  end
  if slot~=32 or not points[0] or not points[16] then return end
  local a,b=points[16],points[32];local pivot=points[0]
  local ax,ay=a.x-pivot.x,a.y-pivot.y
  local bx,by=b.x-pivot.x,b.y-pivot.y
  local cross=ax*by-ay*bx
  local reversed=(control%2)==1
  if w(T.free)==1 and w(T.reversed)~=0 then reversed=not reversed end
  local step=w(C.addr.step);local now=w(T.now);local twirl=T.twirls[step+1]
  local determinant=1
  if twirl then
   local phase=math.max(0,math.min(1,(now-twirl.start)/twirl.tween))
   local weight=twirl.first*(1-math.sin(phase*math.pi/2))
   determinant=1-2*weight
   if determinant<0 then reversed=not reversed end
  end
  -- mode7_rotate_project returns $F000/$F000 for a culled orb. It is a
  -- sentinel, not a projected position (for example 3PXH-X's blind section).
  local clipped=hidden(pivot) or hidden(a) or hidden(b)
  if clipped then culled=culled+1 end
  -- Rotation and uniform camera scaling preserve this orientation. Skip
  -- culled or degenerate projections where there is no triangle to check.
  if not clipped and math.abs(determinant)>.1 and math.abs(cross)>2 then
   assert((cross>0)==reversed,'Third planet is on the wrong side at floor '..w(C.addr.step))
   samples=samples+1
  end
  if T.continuity then
   local colors={[pivot.color]=pivot,[a.color]=a,[b.color]=b}
   if previous and step==previous.step+1 and step<=75 and twirl and now-previous.time<=2 then
    for color,p in pairs(colors)do
     local old=assert(previous.colors[color],'Missing persistent planet identity')
     local dx=signed(p.wx-old.wx);local dy=signed(p.wy-old.wy)
     assert(dx*dx+dy*dy<=64,'Planet teleported at triple-planet twirl floor '..step)
    end
    handoffs=handoffs+1
   end
   previous={step=step,time=now,colors=colors}
  end
  if not inThree and previousTwo and w(C.addr.step)==previousTwo[3]+1 then
   assert(pivot.color==previousTwo[2] and points[32].color==previousTwo[1],
          'Existing planets changed roles when the third planet entered')
   births=births+1
  end
  inThree=true
  if samples%100==0 then report()end
 end,emu.callbackType.exec,T.entry,T.entry,emu.cpuType.snes)
 emu.addEventCallback(function()if w(C.addr.state)==3 then report()end end,emu.eventType.endFrame)
end
