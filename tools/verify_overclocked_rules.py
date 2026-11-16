"""Check perfect-only failures and planet hiding in the actual MesenCE ROM."""
import argparse,json,os,re,subprocess
from pathlib import Path
from verification_data import identity
ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--pack',required=True)
    args=parser.parse_args();pack=ROOT/'build/packs'/args.pack
    levels=json.loads((pack/'pack.json').read_text())['levels'];local=levels.index(284)+1
    chart=json.loads((pack/'level284.json').read_text());frozen=identity(pack/'adofai.sfc')
    labels={n:int(a,16) for a,n in re.findall(r'al ([0-9A-Fa-f]+) \.([\w]+)',(pack/'adofai.lbl').read_text())}
    if 'SA1_FASTROM_MIRROR = 1' in (pack/'addresses.inc').read_text():labels['hit']+=0x800000
    template=pack/f'verification/mesen-{local}-prepared/config.lua'
    assert template.exists(),'Prepare the manual campaign replay first'
    cases=[('perfect',438,0,False,False),
           ('pure-early',438,-3,False,False),('pure-late',438,3,False,False),
           ('nonperfect',438,6,False,True),('practice',438,6,True,False),
           ('outside-rule',437,6,False,False),('scaled-margin',788,1,False,False)]
    results=[]
    for name,target,error,practice,death in cases:
        out=pack/'verification'/('overclocked-'+name);out.mkdir(parents=True,exist_ok=True)
        (out/'rules.txt').unlink(missing_ok=True)
        names=('hit','timing_error','tap_frac','practice','planet_scale_values')
        injection='return function(C)\nlocal Q={'+','.join(f'{n}={labels[n]}' for n in names)+'}\n'
        injection+=f'local target={target};local injectedError={error};local practice={str(practice).lower()};local death={str(death).lower()}\n'
        injection+=f'local hideStart={chart["notes"][158]["frame"]+3};local hideEnd={chart["notes"][163]["frame"]-3}\n'
        injection+='''local W=emu.memType.snesWorkRam
local function word(a)return emu.read(a,W)+256*emu.read(a+1,W)end
local function put(a,v)v=v%65536;emu.write(a,v%256,W);emu.write(a+1,math.floor(v/256),W)end
local fired=false;local hidden=0;local finished=false
local function finish(ok,why)
 if finished then return end;finished=true
 local f=assert(io.open(C.out..'/rules.txt','w'));f:write(why..' hidden_samples='..hidden..'\\n'..(ok and 'PASS' or 'FAIL')..'\\n');f:close()
 emu.stop(ok and 0 or 1)
end
emu.addMemoryCallback(function()
 if not fired and word(C.addr.step)+1==target then
  put(Q.timing_error,injectedError);put(Q.tap_frac,0);put(Q.practice,practice and 1 or 0);fired=true
 end
end,emu.callbackType.exec,Q.hit,Q.hit,emu.cpuType.snes)
emu.addMemoryCallback(function()
 local t=word(C.addr.chart_time)
 if word(C.addr.state)==1 and t>=hideStart and t<hideEnd then
  if word(Q.planet_scale_values+2)~=0 then finish(false,'Ice planet did not hide');return end
  local O=emu.memType.snesSpriteRam
  for i=0,7 do
   local y=emu.read(i*4+1,O);local palette=math.floor(emu.read(i*4+3,O)/2)%8
   if y<224 and palette==5 then finish(false,'Hidden Ice planet is still in OAM');return end
  end
  hidden=hidden+1
 end
end,emu.callbackType.write,C.addr.commits,C.addr.commits)
emu.addEventCallback(function()
 if finished or not fired then return end
 local state=word(C.addr.state);local step=word(C.addr.step);local misses=word(C.addr.misses)
 if state==2 or step>=target then
  local ok=death and state==2 and step==target-1 and misses==1 or
           not death and state==1 and step>=target and misses==(practice and 1 or 0)
  finish(ok and hidden>0,string.format('state=%d step=%d misses=%d',state,step,misses))
 end
end,emu.eventType.endFrame)
end
'''
        script=out/'rules.lua';script.write_text(injection)
        cfg=out/'config.lua';cfg.write_text('local C=dofile('+json.dumps(template.as_posix())+')\nC.out='+json.dumps(out.as_posix())+'\nC.palette_script='+json.dumps(script.as_posix())+'\nreturn C\n')
        result=subprocess.run([r'C:\mesen2\Mesen.exe','--testrunner','--timeout=180',str(pack/'adofai.sfc'),str(ROOT/'tools/verify_campaign_mesen.lua')],
            env=dict(os.environ,ADOFAI_TEST_CONFIG=str(cfg)),capture_output=True,text=True,timeout=200,creationflags=subprocess.CREATE_NO_WINDOW)
        (out/'emulator.log').write_text(result.stdout+result.stderr)
        report=(out/'rules.txt').read_text() if (out/'rules.txt').exists() else result.stdout+result.stderr
        assert result.returncode==0 and report.endswith('PASS\n'),(name,report)
        assert identity(pack/'adofai.sfc')==frozen
        results.append(dict(case=name,passed=True,result=report));print(name,'PASS',flush=True)
    (pack/'verification/overclocked-rules.json').write_text(json.dumps(dict(passed=True,**frozen,cases=results),indent=2))

if __name__=='__main__':main()
