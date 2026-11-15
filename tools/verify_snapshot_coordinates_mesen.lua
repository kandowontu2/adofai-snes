-- Snapshot-only ROMs must never dereference their omitted world-cell index.
return function(C)
 local W=emu.memType.snesWorkRam
 local function word(a)return emu.read(a,W)+256*emu.read(a+1,W)end
 local address=C.sparse.address
 emu.addMemoryCallback(function()
  assert(word(C.addr.state)~=1 or word(C.addr.selected_level)~=C.level-1,
         'Snapshot renderer read the omitted sparse coordinate index')
 end,emu.callbackType.read,address,address+1,emu.cpuType.snes)
end
