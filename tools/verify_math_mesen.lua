-- Check emitted OBJ characters against independent question/answer pairs.
-- This catches stale text, one answer using different ink, missing letters,
-- bank errors and font corruption after other songs/checkpoints.
return function(C)
 local M=C.math;local W=emu.memType.snesWorkRam;local pending=nil;local samples=0;local fontChecked=false
 local function w(a)return emu.read(a,W)+256*emu.read(a+1,W)end
 local function signed(v)return v>=32768 and v-65536 or v end
 local function pool(g)
  if M.code=='T3EX-X' then return ({'3','3c','4','3b'})[g+1]end
  local speed=C.speed
  if g==0 then return 'base0'end
  if g==1 then return speed<16 and '2' or '1b'end
  if g==2 then return speed<13 and '3' or speed<16 and '2b' or speed<20 and '2' or '1c'end
  return speed<13 and '3c' or speed<16 and '3' or speed<20 and '2b' or '1d'
 end
 emu.addMemoryCallback(function()
  if w(C.addr.selected_level)~=C.level-1 then return end
  if not fontChecked then
   local f=assert(io.open(M.font,'rb'));local bytes=f:read('*a');f:close()
   for i=1,#bytes do assert(emu.read(0xFD40+i-1,emu.memType.snesVideoRam)==bytes:byte(i),'Math font VRAM differs from external CHR')end
   fontChecked=true
  end
  local group=w(M.addr.neo_math_group)//2;local label=w(M.addr.neo_math_label)
  local choice=w(M.addr.neo_math_choices+group*2);assert(choice<4,'Invalid math variant')
  local text=M.pools[pool(group)][choice+1][label+1]
  pending={text=text,first=w(M.addr.oam_pos),x=signed(w(M.addr.sprite_x))+8-#text*3,y=w(M.addr.sprite_y),attr=group<2 and 0x35 or 0x33}
 end,emu.callbackType.exec,M.before,M.before,emu.cpuType.snes)
 emu.addMemoryCallback(function()
  if not pending then return end
  local p=pending;pending=nil;local at=p.first
  for i=1,#p.text do
   local x=p.x+(i-1)*6
   if x>=-15 and x<256 and p.y>=32 and p.y<177 then
    assert(at<w(M.addr.oam_pos),'Math label lost a visible character: '..p.text..' at '..p.x..','..p.y..' OAM '..p.first..'..'..w(M.addr.oam_pos))
    assert(emu.read(0x200+at,W)==(x&255) and emu.read(0x201+at,W)==p.y,'Math label position changed')
    local glyph=assert(M.chars:find(p.text:sub(i,i),1,true))-1
    assert(emu.read(0x202+at,W)==234+glyph,'Wrong randomized question/answer glyph')
    assert(emu.read(0x203+at,W)==p.attr,'Math choices have different styling')
    at=at+4
   end
  end
  assert(at==w(M.addr.oam_pos),'Unexpected math glyphs')
  samples=samples+1
  if samples%100==0 then local f=assert(io.open(C.out..'/math-labels.txt','w'));f:write('samples='..samples);f:close()end
 end,emu.callbackType.exec,M.after,M.after,emu.cpuType.snes)
end
