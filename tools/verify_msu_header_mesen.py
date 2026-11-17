"""Verify MesenCE rejects an MSU file with the previous restart format."""
import argparse,json,re,shutil,subprocess,tempfile
from pathlib import Path
from verification_data import identity

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--pack',required=True)
    args=parser.parse_args();root=Path(__file__).resolve().parents[1]
    base=root/'build/packs'/args.pack;out=base/'verification/msu-header'
    out.mkdir(exist_ok=True,parents=True)
    labels={n:int(a,16)&0x1ffff for a,n in re.findall(r'al ([0-9a-fA-F]+) \.([\w]+)',(base/'adofai.lbl').read_text())}
    with (base/'adofai.msu').open('rb') as f:header=f.read(32)
    expected=int.from_bytes(header[12:14],'little')
    declared=int(re.search(r'MSU_DATA_VERSION = (\d+)',(base/'addresses.inc').read_text())[1])
    assert expected==declared and expected>=32
    with tempfile.TemporaryDirectory() as directory:
        folder=Path(directory);shutil.copyfile(base/'adofai.sfc',folder/'adofai.sfc')
        (folder/'adofai.msu').write_bytes(header[:12]+(expected-1).to_bytes(2,'little')+header[14:])
        lua=folder/'verify.lua'
        lua.write_text('local frame=0\nlocal W=emu.memType.snesWorkRam\n'
            'local function word(a)return emu.read(a,W)+256*emu.read(a+1,W)end\n'
            'emu.addEventCallback(function()\nframe=frame+1\nif frame==180 then\n'
            f'local ok=word({labels["msu_present"]})==0 and word({labels["state"]})==0\n'
            'local f=assert(io.open('+json.dumps((out/'result.txt').as_posix())+',"w"))\n'
            'f:write(ok and "PASS\\n" or "FAIL\\n");f:close();emu.stop(ok and 0 or 1)\n'
            'end\nend,emu.eventType.startFrame)\n')
        result=subprocess.run([r'C:\mesen2\Mesen.exe','--testrunner',str(folder/'adofai.sfc'),str(lua)],
            capture_output=True,text=True,timeout=90,creationflags=subprocess.CREATE_NO_WINDOW)
        (out/'emulator.log').write_text(result.stdout+result.stderr)
        assert result.returncode==0 and (out/'result.txt').read_text()=='PASS\n'
    report=dict(passed=True,**identity(base/'adofai.sfc'),rejected_version=expected-1,expected_version=expected)
    (out/'manifest.json').write_text(json.dumps(report,indent=2));print(report)

if __name__=='__main__':main()
