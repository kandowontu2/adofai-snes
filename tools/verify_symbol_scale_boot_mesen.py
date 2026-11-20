"""Dirty the symbol mailbox at reset; verify boot and a real fault control."""
import argparse,json,os,re,shutil,subprocess,tempfile
from pathlib import Path
from verification_data import identity

ROOT=Path(__file__).resolve().parents[1]


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--pack',required=True)
    args=ap.parse_args();base=ROOT/'build/packs'/args.pack;out=base/'verification/symbol-scale-boot'
    out.mkdir(parents=True,exist_ok=True);frozen=identity(base/'adofai.sfc',fresh=True)
    labels={n:int(v,16) for v,n in re.findall(r'al ([0-9A-Fa-f]+) \.([\w]+)',(base/'adofai.lbl').read_text())}
    original=(base/'adofai.sfc').read_bytes();bad=bytearray(original)
    signature=bytes([0x8f])+labels['SYMBOL_SCALE_SIZE'].to_bytes(3,'little')+b'\xc9\0\0'
    at=bad.find(signature,0x10000,0x18000);assert at>=0 and bad.find(signature,at+1,0x18000)<0
    bad[at+4:at+7]=b'\xea'*3
    if 'SA1_FASTROM_HELPERS = 1' in (base/'addresses.inc').read_text():bad[at+0x200004:at+0x200007]=b'\xea'*3
    cases=[]
    for name,rom,expected in [('initialized',original,True),('missing-zero-compare',bad,False)]:
        with tempfile.TemporaryDirectory(prefix='scale-boot-',dir=out) as directory:
            folder=Path(directory).resolve();assert folder.is_relative_to(out.resolve())
            (folder/'adofai.sfc').write_bytes(rom);os.link(base/'adofai.msu',folder/'adofai.msu')
            state=labels['state'];pending=labels['SYMBOL_SCALE_PENDING']&0x3ffff;size=labels['SYMBOL_SCALE_SIZE']&0x3ffff
            result=out/f'{name}.txt';lua=folder/'verify.lua'
            result.unlink(missing_ok=True)
            lua.write_text(f'''local W,S=emu.memType.snesWorkRam,emu.memType.snesSaveRam
local frame,injected=0,0
local function word(a,t)return emu.read(a,t)+256*emu.read(a+1,t)end
emu.addMemoryCallback(function()
 injected=injected+1
 for a={size},{size+21} do emu.write(a,0xa5,S)end
end,emu.callbackType.exec,0x8000,0x8000,emu.cpuType.snes)
emu.addEventCallback(function()
 frame=frame+1
 if frame==180 then
  local ok=injected==1 and word({state},W)==0 and word({pending},S)==0 and word({size},S)==16
  local f=assert(io.open({json.dumps(result.as_posix())},'w'))
  f:write((ok and 'PASS' or 'FAIL')..' injected='..injected..' pending='..word({pending},S)..' state='..word({state},W)..'\\n');f:close()
  emu.stop(ok and 0 or 1)
 end
end,emu.eventType.endFrame)
''')
            r=subprocess.run([r'C:\mesen2\Mesen.exe','--testrunner',str(folder/'adofai.sfc'),str(lua)],capture_output=True,text=True,timeout=90,creationflags=subprocess.CREATE_NO_WINDOW)
            (out/f'{name}.log').write_text(r.stdout+r.stderr)
            text=result.read_text();passed=r.returncode==0 and text.startswith('PASS ')
            assert passed==expected and text.startswith('PASS ' if expected else 'FAIL '),(name,text,r.returncode)
            cases.append(dict(case=name,accepted=passed,expected=expected))
    assert identity(base/'adofai.sfc',fresh=True)==frozen
    (out/'verification.json').write_text(json.dumps(dict(passed=True,**frozen,cases=cases),indent=2))
    print('SYMBOL BOOT AND FAULT CONTROL PASS',flush=True)


if __name__=='__main__':main()
