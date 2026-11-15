"""Exercise deliberate pivot/orbit collisions using the real cartridge code."""
import argparse
import json
import os
import re
import subprocess
from pathlib import Path

from verification_data import identity

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pack', type=Path, required=True)
    parser.add_argument('--level-id', type=int, choices=(75,251), default=75)
    args = parser.parse_args()
    pack = args.pack.resolve()
    labels = {n:int(a,16) for a,n in re.findall(r'al ([0-9a-fA-F]+) \.([\w]+)',(pack/'adofai.lbl').read_text())}
    levels = json.loads((pack/'pack.json').read_text())['levels']
    local = levels.index(args.level_id)+1
    chart = json.loads((pack/f'level{args.level_id}.json').read_text())
    region = chart['freeroam_regions'][0]
    rotating = any('redspinny' in o['tag'].split() for o in region['decoration_hitboxes'])
    assert rotating == (args.level_id==251), 'Rotating bar belongs only to the Community maze'
    template = pack/f'verification/mesen-{local}-prepared/config.lua'
    assert template.exists(), 'Run campaign replay --prepare-only first'
    frozen = identity(pack/'adofai.sfc')
    results = []
    cases = [
        ('orbit-mine', 4400, (240,-72), 128),
        ('perfect-route-mine', 4400, (144,-72), 0),
        ('pivot-sweeping-bar', 5300, None, 0),
    ]
    if args.level_id==251:
        bar=next(o for o in region['decoration_hitboxes'] if 'redspinny' in o['tag'])
        at=next(bar['start']+i for i,f in enumerate(bar['frames']) if f[4]>2 and f[5]>2)
        cases=[('pivot-rotating-bar',at,bar['frames'][at-bar['start']][:2],0)]
    for name, time, position, angle in cases:
        if position is None:
            obj = next(o for o in region['decoration_hitboxes'] if 'redsweep' in o['tag'])
            position = obj['frames'][time-obj['start']][:2]
        out = pack/'verification'/f'{args.level_id}-{name}'
        out.mkdir(parents=True,exist_ok=True)
        script = out/'inject.lua'
        relevant = ('neo_free_x','neo_free_y','neo_free_angle','neo_free_time','neo_deco_collision','neo_deco_cursor','neo_deco_box','neo_free_mode','combo','misses','judgment_counts')
        source = 'return function(C)\nlocal Q={'+','.join(k+'='+str(labels[k]) for k in relevant)+'}\n'
        source += f'local target={time};local px={position[0]};local py={position[1]};local angle={angle}\n'
        source += 'local perfect_case='+str(name=='perfect-route-mine').lower()+'\n'
        source += '''local W=emu.memType.snesWorkRam
local function word(a)return emu.read(a,W)+256*emu.read(a+1,W)end
local function put(a,v)v=v%65536;emu.write(a,v%256,W);emu.write(a+1,math.floor(v/256),W)end
local fired=false
emu.addMemoryCallback(function()
 if not fired and word(C.addr.chart_time)>=target and word(Q.neo_free_mode)==1 then
  if perfect_case then put(Q.misses,0);put(Q.judgment_counts+8,word(Q.combo)) end
  put(Q.neo_free_x,px);put(Q.neo_free_y,py);put(Q.neo_free_angle,angle)
  put(Q.neo_free_time,word(C.addr.chart_time));fired=true
  local f=assert(io.open(C.out..'/injected.txt','w'));f:write(word(C.addr.chart_time));f:close()
 end
end,emu.callbackType.exec,Q.neo_deco_collision,Q.neo_deco_collision,emu.cpuType.snes)
end
'''
        script.write_text(source)
        config = 'local C=dofile('+json.dumps(template.as_posix())+')\n'
        config += 'C.out='+json.dumps(out.as_posix())+'\nC.palette_script='+json.dumps(script.as_posix())+'\n'
        config += f'C.neo_failure_step={region["step"]};C.frames={time+1400};C.graphics_dumps=false;C.arc=nil;C.objects=nil;C.holds=nil\nreturn C\n'
        cfg = out/'config.lua';cfg.write_text(config)
        result = subprocess.run([r'C:\mesen2\Mesen.exe','--testrunner','--timeout=180',str(pack/'adofai.sfc'),str(ROOT/'tools/verify_campaign_mesen.lua')],
                                env=dict(os.environ,ADOFAI_TEST_CONFIG=str(cfg)),capture_output=True,text=True,timeout=200,
                                creationflags=subprocess.CREATE_NO_WINDOW)
        (out/'emulator.log').write_text(result.stdout+result.stderr)
        report = (out/'result.txt').read_text()
        assert result.returncode == 0 and report.endswith('PASS\n') and (out/'injected.txt').exists(), (name,report)
        assert identity(pack/'adofai.sfc') == frozen, 'Build changed during collision verification'
        results.append(dict(case=name,clock=int((out/'injected.txt').read_text()),passed=True))
        print(name,'PASS',flush=True)
    (pack/f'verification/decoration-hitboxes-{args.level_id}.json').write_text(json.dumps(dict(passed=True,**frozen,cases=results),indent=2))


if __name__ == '__main__':
    main()
