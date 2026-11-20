"""Real controller negative controls for typed pickups and ordered answers."""
import argparse
import json
import os
import re
import subprocess
from pathlib import Path

from neo_freeroam import demo_route
from verification_data import identity

ROOT=Path(__file__).resolve().parents[1]


def verify(pack,level):
    frozen=identity(pack/'adofai.sfc')
    n=json.loads((pack/'pack.json').read_text())['levels'][level-1]
    chart=json.loads((pack/f'level{n}.json').read_text())
    rooms=chart['freeroam_regions'];quiz=rooms[-1]
    assert all(r.get('pickup_lives')==3 for r in rooms[:3])
    assert quiz.get('coin_types',[])[:5]==[4]*5
    original=pack/f'verification/mesen-{level}/config.lua'
    labels={name:int(address,16) for address,name in re.findall(
        r'al ([0-9A-Fa-f]+) \.([\w]+)',(pack/'adofai.lbl').read_text())}
    route=demo_route(dict(quiz,goal=[0,-144]),chart['notes'][quiz['step']])
    cases=[]
    for name in ('three-strikes','future-answer'):
        out=pack/'verification'/('pickups-'+name);out.mkdir(parents=True,exist_ok=True)
        (out/'result.txt').unlink(missing_ok=True)
        (out/'manifest.json').write_text(json.dumps(dict(passed=False)))
        script='local C=dofile('+json.dumps(original.as_posix())+')\nC.out='+json.dumps(out.as_posix())+'\n'
        script+='C.palette_script=nil;C.graphics_dumps=false;C.sampled_graphics=false\n'
        if name=='three-strikes':
            windows=[(r['start'],r['return_start']) for r in rooms[:3]]
            script+='local windows={'+','.join('{'+str(a)+','+str(b)+'}' for a,b in windows)+'}\n'
            script+='local events={}\nfor _,row in ipairs(C.neo_events) do\n local keep=true\n for _,w in ipairs(windows) do if row[1]>w[1] and row[1]<w[2] then keep=false end end\n if keep then events[#events+1]=row end\nend\nC.neo_events=events\n'
            script+=f'C.neo_failure_step={rooms[2]["step"]};C.frames={rooms[2]["end"]+500}\n'
            script+='emu.addEventCallback(function()\n local W=emu.memType.snesWorkRam\n'
            script+=f' local state=emu.read({labels["state"]},W)\n if state==2 then assert(emu.read({labels["neo_pickup_strikes"]},W)==3,"Death did not follow exactly three failed objectives")end\nend,emu.eventType.startFrame)\n'
        else:
            script+=f'local events={{}}\nfor _,row in ipairs(C.neo_events) do if row[1]<={quiz["start"]} then events[#events+1]=row end end\nlocal key=events[#events][2]\n'
            script+='for _,at in ipairs({'+','.join(str(hop[0]) for hop in route)+'}) do key=3-key;events[#events+1]={at,key,'+str(quiz['step']+1)+'}end\nC.neo_events=events\n'
            script+=f'C.neo_failure_step={quiz["step"]};C.frames={route[-1][0]+500}\n'
        script+='return C\n'
        config=out/'config.lua';config.write_text(script)
        result=subprocess.run(['C:/mesen2/Mesen.exe','--testrunner','--timeout=450',str(pack/'adofai.sfc'),
            str(ROOT/'tools/verify_campaign_mesen.lua')],env=dict(os.environ,ADOFAI_TEST_CONFIG=str(config)),
            capture_output=True,text=True,timeout=480,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        (out/'emulator.log').write_text(result.stdout+result.stderr)
        outcome=(out/'result.txt').read_text() if (out/'result.txt').exists() else result.stdout+result.stderr
        print(name,outcome,flush=True)
        assert result.returncode==0 and outcome.endswith('PASS\n'),outcome
        assert identity(pack/'adofai.sfc')==frozen
        (out/'manifest.json').write_text(json.dumps(dict(passed=True,case=name,**frozen),indent=2))
        cases.append(name)
    return cases


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pack',type=Path,required=True)
    parser.add_argument('--level',type=int,required=True)
    args=parser.parse_args();verify(args.pack.resolve(),args.level)
