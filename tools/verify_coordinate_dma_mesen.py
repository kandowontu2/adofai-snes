"""Ensure native coordinate copies own DMA before programming its source bank."""
import argparse,json,os,re,subprocess
from pathlib import Path
from verification_data import identity
ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--pack',required=True)
    pack=ROOT/'build/packs'/parser.parse_args().pack;frozen=identity(pack/'adofai.sfc')
    local=json.loads((pack/'pack.json').read_text())['levels'].index(140)+1
    template=pack/f'verification/mesen-{local}-autoplay/config.lua';assert template.exists()
    labels={n:int(a,16) for a,n in re.findall(r'al ([0-9A-Fa-f]+) \.([\w]+)',(pack/'adofai.lbl').read_text())}
    address=labels['native_receive_bank']
    if 'SA1_FASTROM_MIRROR = 1' in (pack/'addresses.inc').read_text():address+=0x800000
    out=pack/'verification/coordinate-dma';out.mkdir(parents=True,exist_ok=True)
    script='return function(C)\nlocal busy='+str(labels['msu_data_busy'])+'\n'
    script+='''local pending=false;local count=0
emu.addMemoryCallback(function()pending=true end,emu.callbackType.exec,'''+str(address)+','+str(address)+''',emu.cpuType.snes)
emu.addMemoryCallback(function()
 if pending then
  assert(emu.read(busy,emu.memType.snesWorkRam)==1,'DMA source bank was written before acquiring the interrupt guard')
  pending=false;count=count+1
 end
end,emu.callbackType.write,0x4304,0x4304,emu.cpuType.snes)
emu.addEventCallback(function()
 if emu.read(C.addr.state,emu.memType.snesWorkRam)==3 then
  assert(count>100,'Insufficient native DMA coverage')
  local f=assert(io.open(C.out..'/dma-guard.txt','w'));f:write('protected_transfers='..count..'\\nPASS\\n');f:close()
 end
end,emu.eventType.endFrame)
end
'''
    (out/'guard.lua').write_text(script)
    # Retain the ordinary coordinate equality probe and all other chart probes.
    (out/'coordinates.lua').write_text('return function(C)\ndofile('+json.dumps((ROOT/'tools/verify_coordinates_mesen.lua').as_posix())+')(C)\ndofile('+json.dumps((out/'guard.lua').as_posix())+')(C)\nend\n')
    (out/'config.lua').write_text('local C=dofile('+json.dumps(template.as_posix())+');C.out='+json.dumps(out.as_posix())+';C.coordinates.script='+json.dumps((out/'coordinates.lua').as_posix())+';return C\n')
    for name in ('result.txt','dma-guard.txt','verification.json'):(out/name).unlink(missing_ok=True)
    result=subprocess.run([r'C:\mesen2\Mesen.exe','--testrunner','--timeout=600',str(pack/'adofai.sfc'),str(ROOT/'tools/verify_campaign_mesen.lua')],
        env=dict(os.environ,ADOFAI_TEST_CONFIG=str(out/'config.lua')),capture_output=True,text=True,timeout=630,creationflags=subprocess.CREATE_NO_WINDOW)
    (out/'emulator.log').write_text(result.stdout+result.stderr)
    report=(out/'result.txt').read_text();guard=(out/'dma-guard.txt').read_text() if (out/'dma-guard.txt').exists() else ''
    assert result.returncode==0 and report.endswith('PASS\n') and guard.endswith('PASS\n'),report
    assert identity(pack/'adofai.sfc')==frozen
    (out/'verification.json').write_text(json.dumps(dict(passed=True,**frozen,result=report.splitlines()[0],guard=guard),indent=2))
    print('NATIVE COORDINATE DMA GUARD PASS',flush=True)

if __name__=='__main__':main()
