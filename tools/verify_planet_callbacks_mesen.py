"""Check perfect-only planet scaling against real Watch and early inputs."""
import argparse,json,re,subprocess,sys
from pathlib import Path
from pack_sources import load_source
from planet_scale import conditional_scales,schedule
from verification_data import identity,freeze_data_identity
from run_mesen_campaign import suite_digest

ROOT=Path(__file__).resolve().parents[1]


def verify(pack,level_id):
    ids=json.loads((pack/'pack.json').read_text())['levels'];local=ids.index(level_id)+1
    chart=json.loads((pack/f'level{level_id}.json').read_text());source=load_source(pack,level_id)
    rows=conditional_scales(source,chart);assert rows,'No conditional planet sizes in this chart'
    trigger=min(r[0] for r in rows);expiry=min(r[1] for r in rows if r[0]==trigger)
    rows=[r for r in rows if r[0]==trigger]
    automatic=bool(chart['notes'][trigger]['flags']&8)
    defaults=schedule(source,chart)
    labels={n:int(a,16) for a,n in re.findall(r'al ([0-9A-Fa-f]+) \.([\w]+)',(pack/'adofai.lbl').read_text())}
    frozen=identity(pack/'adofai.sfc',fresh=True);freeze_data_identity(pack/'adofai.sfc',frozen)
    suite=suite_digest();cases=[]
    for watch in (True,False):
        subprocess.run([sys.executable,str(ROOT/'tools/run_mesen_campaign.py'),'--pack',pack.name,
            '--levels',str(local),'--prepare-only',*(['--autoplay'] if watch else [])],cwd=ROOT,check=True)
        original=pack/'verification'/f'mesen-{local}{"-autoplay" if watch else ""}-prepared/config.lua'
        out=pack/'verification'/f'planet-callbacks-{level_id}-{"perfect" if watch else "early"}'
        out.mkdir(parents=True,exist_ok=True);(out/'result.txt').unlink(missing_ok=True)
        address={k:labels[k] for k in ('state','step','chart_time','planet_scale_values','NOTE_JUDGMENTS','planet_scale_update_done')}
        if 'SA1_FASTROM_HELPERS = 1' in (pack/'addresses.inc').read_text():
            address['planet_scale_update_done']|=0x800000
        config=dict(out=out.as_posix(),original=original.as_posix(),trigger=trigger,expiry=expiry,
                    perfect=watch or automatic,automatic=automatic,rows=rows,defaults=defaults,addr=address)
        # JSON arrays/objects are converted to Lua literals without evaluating
        # any chart text as code.
        def lua(v):
            if isinstance(v,dict):return '{'+','.join('['+json.dumps(k)+']='+lua(x) for k,x in v.items())+'}'
            if isinstance(v,list):return '{'+','.join(map(lua,v))+'}'
            return json.dumps(v)
        script='local T='+lua(config)+'\n'
        script+=r'''
local C=dofile(T.original);C.out=T.out
C.palette_script=nil;C.graphics_dumps=false;C.sampled_graphics=false
if not T.perfect then
 local changed=false
 if C.neo_events then
  for _,r in ipairs(C.neo_events) do if r[3]==T.trigger then r[1]=r[1]-4;changed=true;break end end
 else
  for i,step in ipairs(C.manual_steps) do if step==T.trigger then C.manual_times[i]=C.manual_times[i]-4;changed=true;break end end
 end
 assert(changed,'Could not find the callback floor input')
end
local M=emu.memType.snesMemory
local function w(a)return emu.read(a,M)+256*emu.read(a+1,M)end
local samples,frames=0,0
emu.addEventCallback(function()
 frames=frames+1;assert(frames<C.frames,'Callback control timed out')
 assert(w(T.addr.state)~=2,'Callback control died before its observation window')
end,emu.eventType.startFrame)
emu.addMemoryCallback(function()
 if w(T.addr.state)~=1 then return end
 local at=w(T.addr.chart_time);local step=w(T.addr.step)
 if step<T.trigger then return end
 local expected={256,256,256}
 for _,r in ipairs(T.defaults) do if r[1]<=at then expected={r[2],r[3],r[4]}else break end end
 local grade=emu.read(T.addr.NOTE_JUDGMENTS+T.trigger,M)
 if not T.automatic and grade==0 and step==T.trigger then return end
 local perfect=T.automatic or grade>=4 and grade<=6
 assert((T.automatic or grade>0) and perfect==T.perfect,'Control did not produce its intended actual judgment: '..grade)
 if perfect then
  for _,r in ipairs(T.rows) do if at<r[2] then expected[1+r[3]/2]=r[4]end end
 end
 for i=1,3 do
  assert(w(T.addr.planet_scale_values+(i-1)*2)==expected[i],
   'Planet callback target '..i..' differs at '..at)
 end
 if at<T.expiry then samples=samples+1 end
 if at>=T.expiry+1 then
  assert(samples>=3,'Too few real judgment/scale observations')
  local f=assert(io.open(T.out..'/result.txt','w'));f:write('PASS samples='..samples..'\n');f:close();emu.stop(0)
 end
end,emu.callbackType.exec,T.addr.planet_scale_update_done,T.addr.planet_scale_update_done,emu.cpuType.snes)
local original=dofile
dofile=function(p)if p==T.original then return C end;return original(p)end
'''
        script+='original('+json.dumps((ROOT/'tools/verify_campaign_mesen.lua').as_posix())+')\n'
        path=out/'verify.lua';path.write_text(script)
        import os
        env=os.environ.copy();env['ADOFAI_TEST_CONFIG']=original.as_posix()
        result=subprocess.run(['C:/mesen2/Mesen.exe','--testrunner','--timeout=450',str(pack/'adofai.sfc'),str(path)],
            cwd=ROOT,env=env,capture_output=True,text=True,timeout=480,creationflags=subprocess.CREATE_NO_WINDOW)
        (out/'emulator.log').write_text(result.stdout+result.stderr)
        message=(out/'result.txt').read_text() if (out/'result.txt').exists() else result.stdout+result.stderr
        assert result.returncode==0 and message.startswith('PASS '),message
        cases.append(dict(watch=watch,perfect=watch or automatic,automatic=automatic,result=message.strip()))
        print('PLANET CALLBACK',level_id,'Watch' if watch else 'manual',message.strip(),flush=True)
    assert identity(pack/'adofai.sfc',fresh=True)==frozen and suite_digest()==suite
    report=dict(passed=True,**frozen,suite_digest=suite,level_id=level_id,trigger=trigger,targets=len(rows),cases=cases)
    (pack/'verification'/f'planet-callbacks-{level_id}.json').write_text(json.dumps(report,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--pack',type=Path,required=True)
    parser.add_argument('--level-id',type=int,required=True);args=parser.parse_args()
    verify(args.pack.resolve(),args.level_id)
