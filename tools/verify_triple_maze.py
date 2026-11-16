"""Prove that an isolated collision with the third planet fails in MesenCE."""
import argparse,json,math,os,re,subprocess
from pathlib import Path
from verification_data import identity
ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--pack',required=True)
    args=parser.parse_args();pack=ROOT/'build/packs'/args.pack;frozen=identity(pack/'adofai.sfc')
    levels=json.loads((pack/'pack.json').read_text())['levels'];local=levels.index(280)+1
    chart=json.loads((pack/'level280.json').read_text());region=chart['freeroam_regions'][0]
    labels={n:int(a,16) for a,n in re.findall(r'al ([0-9A-Fa-f]+) \.([\w]+)',(pack/'adofai.lbl').read_text())}
    at=min(region['return_start']-10,region['start']+60)
    boxes=[o['frames'][at-o['start']] for o in region['decoration_hitboxes']]
    def hits(p,b):
        x,y,co,si,hw,hh=b[:6];dx=p[0]-x;dy=p[1]-y
        u=max(0,abs(round((dx*co+dy*si)/256))-hw)
        v=max(0,abs(round((-dx*si+dy*co)/256))-hh)
        return hw>0 and hh>0 and u*u+v*v<=36
    case=None
    for b in boxes:
        for angle in range(0,256,16):
            third=angle-43
            pivot=(b[0]-round(24*math.cos(third*math.pi/128)),b[1]-round(24*math.sin(third*math.pi/128)))
            orbit=(pivot[0]+round(24*math.cos(angle*math.pi/128)),pivot[1]+round(24*math.sin(angle*math.pi/128)))
            if not any(hits(p,c) for p in (pivot,orbit) for c in boxes):case=(*pivot,angle);break
        if case:break
    assert case,'No isolated third-planet collision fixture'
    template=pack/f'verification/mesen-{local}-prepared/config.lua';assert template.exists()
    out=pack/'verification/triple-third-planet-collision';out.mkdir(parents=True,exist_ok=True)
    for filename in ('injected.txt','result.txt','verification.json'):
        (out/filename).unlink(missing_ok=True)
    names=('neo_deco_collision','neo_free_x','neo_free_y','neo_free_angle','neo_free_time','neo_free_mode','neo_free_reversed')
    script='return function(C)\nlocal Q={'+','.join(f'{n}={labels[n]}' for n in names)+'}\n'
    script+=f'local target={at};local px={case[0]};local py={case[1]};local angle={case[2]}\n'
    script+='''local W=emu.memType.snesWorkRam
local function word(a)return emu.read(a,W)+256*emu.read(a+1,W)end
local function put(a,v)v=v%65536;emu.write(a,v%256,W);emu.write(a+1,math.floor(v/256),W)end
local fired=false
emu.addMemoryCallback(function()
 if not fired and word(C.addr.chart_time)>=target and word(Q.neo_free_mode)==1 then
  put(Q.neo_free_x,px);put(Q.neo_free_y,py);put(Q.neo_free_angle,angle);put(Q.neo_free_reversed,0)
  put(Q.neo_free_time,word(C.addr.chart_time));fired=true
  local f=assert(io.open(C.out..'/injected.txt','w'));f:write(word(C.addr.chart_time));f:close()
 end
end,emu.callbackType.exec,Q.neo_deco_collision,Q.neo_deco_collision,emu.cpuType.snes)
end
'''
    injection=out/'inject.lua';injection.write_text(script)
    cfg=out/'config.lua';cfg.write_text('local C=dofile('+json.dumps(template.as_posix())+')\nC.out='+json.dumps(out.as_posix())+'\nC.palette_script='+json.dumps(injection.as_posix())+f'\nC.neo_failure_step={region["step"]}; C.frames={at+1400}\nreturn C\n')
    result=subprocess.run([r'C:\mesen2\Mesen.exe','--testrunner','--timeout=180',str(pack/'adofai.sfc'),str(ROOT/'tools/verify_campaign_mesen.lua')],
        env=dict(os.environ,ADOFAI_TEST_CONFIG=str(cfg)),capture_output=True,text=True,timeout=200,creationflags=subprocess.CREATE_NO_WINDOW)
    (out/'emulator.log').write_text(result.stdout+result.stderr)
    report=(out/'result.txt').read_text() if (out/'result.txt').exists() else result.stdout+result.stderr
    assert result.returncode==0 and report.endswith('PASS\n') and (out/'injected.txt').exists(),report
    assert identity(pack/'adofai.sfc')==frozen
    (out/'verification.json').write_text(json.dumps(dict(passed=True,**frozen,position=case,frame=at),indent=2))
    print('THIRD PLANET COLLISION PASS',flush=True)

if __name__=='__main__':main()
