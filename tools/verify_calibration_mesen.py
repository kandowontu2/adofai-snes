"""Check the live calibration orbit and SPC click voice in Mesen."""
import argparse,csv,json,os,re,subprocess
from pathlib import Path
from verification_data import identity
ROOT=Path(__file__).resolve().parents[1]

def verify(base,route):
    base=base.resolve();out=base/f'verification/calibration-mesen-{route}';out.mkdir(parents=True,exist_ok=True)
    loaded=identity(base/'adofai.sfc')
    labels={m[1]:int(m[0],16)&0x1ffff for m in re.findall(r'al ([0-9A-Fa-f]+) \.([\w]+)',(base/'adofai.lbl').read_text())}
    actions={120:'select'}
    if route=='options':actions={90:'b',100:'down',104:'down',108:'down',112:'down',116:'down',124:'a'}
    if route=='after-pcm':actions={90:'y',120:'start',420:'start',428:'select',436:'select'}
    if route=='after-brr':actions={**{90+i*4:'r' for i in range(10)},138:'y',150:'start',450:'start',458:'select',466:'select'}
    if route=='retry':actions={120:'select',300:'start'}
    start=max(actions);finish=start+120
    script='local A={'+','.join(k+'='+str(labels[k]) for k in ('state','audio_ticks','angle'))+'}\n'
    script+='local actions={'+','.join('['+str(k)+']='+json.dumps(v) for k,v in actions.items())+'}\n'
    script+='local out='+json.dumps(out.as_posix())+'\nlocal first='+str(start)+'\nlocal finish='+str(finish)+'\n'
    script+='''local frame=0
local W=emu.memType.snesWorkRam
local function word(a)return emu.read(a,W)+256*emu.read(a+1,W)end
local f=io.open(out..'/frames.csv','w')
f:write('frame,state,ticks,angle,envelope,output,volume,pitch,sample\\n')
emu.addEventCallback(function()
 local b={};if actions[frame] then b[actions[frame]]=true end;emu.setInput(b,0)
end,emu.eventType.inputPolled)
emu.addEventCallback(function()
 frame=frame+1
 if frame>=first then
  local s=emu.getState()
  f:write(string.format('%d,%d,%d,%d,%d,%d,%d,%d,%d\\n',frame,word(A.state),word(A.audio_ticks),word(A.angle),
   s['spc.dsp.voices[1].envVolume'] or -1,emu.read(0x19,emu.memType.spcDspRegisters),
   emu.read(0x10,emu.memType.spcDspRegisters),emu.read(0x13,emu.memType.spcDspRegisters),emu.read(0x14,emu.memType.spcDspRegisters)))
  if frame==first+20 or frame==first+40 then
   local h=io.open(out..'/frame-'..frame..'.png','wb');h:write(emu.takeScreenshot());h:close()
  end
 end
 if frame==finish then f:close();emu.stop(0) end
end,emu.eventType.startFrame)
'''
    path=out/'verify.lua';path.write_text(script)
    result=subprocess.run([r'C:\mesen2\Mesen.exe','--testrunner',str(base/'adofai.sfc'),str(path)],cwd=ROOT,
                          creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0,timeout=60,capture_output=True,text=True)
    assert result.returncode==0,result.stdout[-2000:]+result.stderr[-2000:]
    rows=[{k:int(v) for k,v in row.items()} for row in csv.DictReader((out/'frames.csv').open())]
    live=[r for r in rows if r['state']==5 and r['frame']>start+2]
    assert len(live)>=115 and len({r['angle'] for r in live})>=26,('Frozen orbit',route)
    assert sum(b['angle']<a['angle']-200 for a,b in zip(live,live[1:]))>=3,('Orbit did not complete',route)
    assert all(1<=(b['angle']-a['angle'])%256<=11 for a,b in zip(live,live[1:])),('Orbit jumped',route)
    sound=[r for r in rows if r['state']==5 and r['envelope']>0 and r['volume']==112 and r['pitch']==8 and r['sample']==1]
    pulses=[]
    for r in sound:
        if not pulses or r['frame']-pulses[-1]>5:pulses.append(r['frame'])
    assert len(pulses)>=4 and pulses[0]-start<=3,('Missing immediate/repeating beat',route,pulses)
    assert all(abs(b-a-30)<=1 for a,b in zip(pulses,pulses[1:])),(route,pulses)
    assert any(r['output']!=0 for r in sound),('Silent DSP output',route)
    assert identity(base/'adofai.sfc')==loaded
    report=dict(passed=True,core='Mesen',route=route,unique_angles=len({r['angle'] for r in live}),click_frames=pulses,**loaded)
    (out/'result.json').write_text(json.dumps(report,indent=2));return report

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--pack',default='master');args=ap.parse_args()
    base=ROOT/'build/packs'/args.pack
    cases=[verify(base,route) for route in ('menu','options','after-pcm','after-brr','retry')]
    report=dict(passed=True,cases=cases,**identity(base/'adofai.sfc'))
    (base/'verification/calibration-mesen.json').write_text(json.dumps(report,indent=2))
    print('PASS: Mesen continuous calibration orbit and immediate/repeating SPC clicks in five entry flows')

if __name__=='__main__':main()
