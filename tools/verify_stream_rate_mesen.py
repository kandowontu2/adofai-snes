"""Verify that streamed BRR delivery stays ahead of the SPC playback clock."""
import argparse,json,os,re,subprocess,sys
from pathlib import Path
from verification_data import identity
ROOT=Path(__file__).resolve().parents[1]

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--pack',required=True);ap.add_argument('--level',type=int,default=11)
    ap.add_argument('--speed',type=float,default=2.5);ap.add_argument('--tag',default='final')
    args=ap.parse_args();base=ROOT/'build/packs'/args.pack
    ids=json.loads((base/'pack.json').read_text())['levels'];local=ids.index(args.level)+1
    subprocess.run([sys.executable,str(ROOT/'tools/run_mesen_campaign.py'),'--pack',args.pack,
                    '--levels',str(local),'--speed',str(args.speed),'--autoplay','--prepare-only'],check=True)
    template=base/f'verification/mesen-{local}-speed-{round(args.speed*10):02d}-autoplay-prepared/config.lua'
    assert args.speed!=1,'This probe requires BRR playback, without song-start PCM'
    out=base/f'verification/audio-rate-{args.level}-{round(args.speed*10):02d}-{args.tag}'
    out.mkdir(parents=True,exist_ok=True);frozen=identity(base/'adofai.sfc',fresh=True)
    labels={n:int(a,16) for a,n in re.findall(r'al ([0-9A-Fa-f]+) \.([\w]+)',(base/'adofai.lbl').read_text())}
    fields=('state','step','music_active','msu_pcm','speed_stream','audio_pending_packets')
    script='return function(C)\nlocal A={'+','.join(f'{k}={labels[k]}' for k in fields)+'}\n'
    script+='''local W,S=emu.memType.snesWorkRam,emu.memType.spcRam
local function w(a,t)return emu.read(a,t)+256*emu.read(a+1,t)end
local written,started,samples,minimum,peak=0,false,0,100000000,0
local log=assert(io.open(C.out..'/samples.csv','w'));log:write('step,ticks,written,consumed,lead,pending\\n')
local function finish(ok,reason)
 local f=assert(io.open(C.out..'/transport.json','w'))
 f:write(string.format('{"passed":%s,"samples":%d,"minimum_lead_bytes":%.2f,"peak_pending_packets":%d,"step":%d,"reason":"%s"}',tostring(ok),samples,minimum,peak,w(A.step,W),reason));f:close();log:close()
end
emu.addMemoryCallback(function(a,v)
 if v==0x80 then written=0;started=false
 elseif v<0x80 then written=written+3
 elseif v==0x81 or v==0x85 then started=true end
end,emu.callbackType.write,0x2140,0x2140,emu.cpuType.snes)
emu.addEventCallback(function()
 if not started then return end
 if w(A.state,W)==1 and w(A.music_active,W)~=0 then
  assert(w(A.msu_pcm,W)==0,'BRR transport probe selected PCM')
  local ticks=w(0x14,S);local consumed=ticks*w(A.speed_stream,W)*3/512
  local lead=written-consumed;local pending=w(A.audio_pending_packets,W)
  minimum=math.min(minimum,lead);peak=math.max(peak,pending);samples=samples+1
  log:write(string.format('%d,%d,%d,%.2f,%.2f,%d\\n',w(A.step,W),ticks,written,consumed,lead,pending))
  if lead<=0 then finish(false,'SPC playback overtook delivered music');emu.stop(1)end
 elseif w(A.state,W)==3 then
  assert(samples>100,'Insufficient streamed music coverage')
  finish(true,'complete song without transport starvation');started=false
 end
end,emu.eventType.startFrame)
end
'''
    (out/'probe.lua').write_text(script)
    replay='local C=dofile('+json.dumps(template.as_posix())+');C.out='+json.dumps(out.as_posix())+'\n'
    replay+='local old=C.palette_script;C.palette_script=nil;if old then dofile(old)(C)end\n'
    replay+='dofile('+json.dumps((out/'probe.lua').as_posix())+')(C)\n'
    replay+='local load=dofile;dofile=function(p)if p=='+json.dumps(template.as_posix())+' then return C end;return load(p)end\n'
    replay+='load('+json.dumps((ROOT/'tools/verify_campaign_mesen.lua').as_posix())+')\n'
    (out/'replay.lua').write_text(replay)
    (out/'transport.json').unlink(missing_ok=True)
    r=subprocess.run([r'C:\mesen2\Mesen.exe','--testrunner','--timeout=450',str(base/'adofai.sfc'),str(out/'replay.lua')],
        env=dict(os.environ,ADOFAI_TEST_CONFIG=template.as_posix()),capture_output=True,text=True,timeout=480,creationflags=subprocess.CREATE_NO_WINDOW)
    (out/'emulator.log').write_text(r.stdout+r.stderr)
    report=json.loads((out/'transport.json').read_text());report.update(frozen,speed=args.speed,id=args.level)
    (out/'verification.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)
    assert identity(base/'adofai.sfc',fresh=True)==frozen
    assert r.returncode==0 and report['passed'],report

if __name__=='__main__':main()
