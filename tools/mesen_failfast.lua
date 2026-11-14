-- Mesen may disable a failed callback and continue emulation. Never let a
-- disabled oracle produce a passing replay. Guard assertions AND Lua errors.
return function(C)
 local failed=false
 local originalAssert=assert
 local function fail(message)
  if not failed then
   failed=true
   local f=io.open(C.out..'/result.txt','w')
   if f then f:write(tostring(message)..'\nFAIL\n');f:close()end
  end
  emu.stop(1)
 end
 assert=function(condition,message)
  if not condition then fail(message or 'Assertion failed')end
  return originalAssert(condition,message)
 end
 local function guarded(callback)
  return function(...)
   if failed then return end
   local ok,message=pcall(callback,...)
   if not ok then fail(message)end
  end
 end
 local memory=emu.addMemoryCallback
 emu.addMemoryCallback=function(callback,...)return memory(guarded(callback),...)end
 local event=emu.addEventCallback
 emu.addEventCallback=function(callback,...)return event(guarded(callback),...)end
end
