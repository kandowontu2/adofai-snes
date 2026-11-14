-- An automatic midspin can remain the logical input stage while waiting for
-- a real tap. Its detached symbol must never become a rendered planet pivot.
return function(C)
 local P=C.midspin;local W=emu.memType.snesWorkRam;local samples=0;local virtual=0
 local function w(a)return emu.read(a,W)+256*emu.read(a+1,W)end
 emu.addMemoryCallback(function()
  if w(C.addr.state)~=1 or w(C.addr.selected_level)~=C.level-1 then return end
  local logical=w(P.addr.m7_logical_step);local actual=w(C.addr.step);local clock=w(P.addr.chart_time)
  assert((P.flags[actual+1]&16)==0,'Detached midspin used as planet pivot')
  assert(w(P.addr.m7_visual_step)==actual,'Stale visual midspin stage')
  -- A real orbit immediately beyond a marker may not begin before its
  -- authored time, regardless of when the judgment accepted the input.
  if actual>0 and (P.flags[actual]&16)~=0 then
   assert(clock>=P.times[actual+1],'Midspin orbit handed off before the beat')
  end
  local expected=actual
  samples=samples+1;if expected~=logical then virtual=virtual+1 end
  if samples%100==0 then local f=assert(io.open(C.out..'/midspin-poses.txt','w'));f:write('samples='..samples..' virtual='..virtual);f:close()end
 end,emu.callbackType.exec,P.entry,P.entry,emu.cpuType.snes)
end
