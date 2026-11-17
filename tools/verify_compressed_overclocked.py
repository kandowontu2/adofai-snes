"""Replay Overclocked manually in MesenCE without any PCM tracks present."""
import argparse,json,os,re,shutil,subprocess,sys
from pathlib import Path
from verification_data import identity
ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--pack',required=True)
    parser.add_argument('--level-id',type=int,default=284,help='Global chart ID; defaults to Overclocked')
    args=parser.parse_args();pack=ROOT/'build/packs'/args.pack;frozen=identity(pack/'adofai.sfc')
    local=json.loads((pack/'pack.json').read_text())['levels'].index(args.level_id)+1
    subprocess.run([sys.executable,str(ROOT/'tools/run_mesen_campaign.py'),'--pack',args.pack,
                    '--levels',str(local),'--prepare-only','--sampled-graphics'],check=True)
    template=pack/f'verification/mesen-{local}-prepared/config.lua';assert template.exists()
    out=pack/('verification/overclocked-compressed' if args.level_id==284 else f'verification/compressed-{args.level_id}')
    out.mkdir(parents=True,exist_ok=True)
    assert not list(out.glob('*.pcm'))
    shutil.copyfile(pack/'adofai.sfc',out/'adofai.sfc')
    (out/'adofai.msu').unlink(missing_ok=True);(out/'adofai.msu').hardlink_to(pack/'adofai.msu')
    labels={n:int(a,16) for a,n in re.findall(r'al ([0-9A-Fa-f]+) \.([\w]+)',(pack/'adofai.lbl').read_text())}
    script='return function(C)\nlocal active='+str(labels['music_active'])+';local pcm='+str(labels['msu_pcm'])+'\n'
    script+='''local count=0
local function w(a)return emu.read(a,emu.memType.snesWorkRam)+256*emu.read(a+1,emu.memType.snesWorkRam)end
-- elapsed is published only after all fractional-clock updates complete.
-- inputPolled can otherwise interrupt those updates and read a mixed pair.
emu.addMemoryCallback(function()
 local offset=w(C.addr.speed_offset);if offset>=32768 then offset=offset-65536 end
 C.coherent_time=w(C.addr.clock_song_frames)+w(C.addr.clock_song_frac)/65536+w(C.addr.music_origin)
   -offset-w(C.addr.speed_offset_frac)/65536
 C.coherent_ticks=w(C.addr.audio_ticks)
end,emu.callbackType.write,C.addr.elapsed,C.addr.elapsed)
emu.addEventCallback(function()
 if w(C.addr.state)==1 and w(active)~=0 then assert(w(pcm)==0,'Compressed edition selected PCM');count=count+1 end
 if w(C.addr.state)==3 then
  assert(count>100,'No compressed playback coverage')
  local f=assert(io.open(C.out..'/audio-mode.txt','w'));f:write('BRR samples='..count..'\\nPASS\\n');f:close()
 end
end,emu.eventType.endFrame)
end
'''
    (out/'audio.lua').write_text(script)
    clocks=''.join('C.addr.'+name+'='+str(labels[name])+';' for name in
                   ('clock_song_frames','clock_song_frac','speed_offset_frac','music_origin','speed_scale'))
    (out/'config.lua').write_text('local C=dofile('+json.dumps(template.as_posix())+');C.out='+json.dumps(out.as_posix())+';'+clocks+'C.palette_script='+json.dumps((out/'audio.lua').as_posix())+';return C\n')
    # Observe a coherent BRR clock pair and predict the next controller poll.
    replay=(ROOT/'tools/verify_campaign_mesen.lua').read_text()
    assert replay.count('lead=1.5')==1
    replay=replay.replace('lead=1.5',"""if C.coherent_time then
          local ticks=(word(C.addr.nmi_audio_ticks)-C.coherent_ticks+32768)%65536-32768
          current=C.coherent_time+ticks*word(C.addr.speed_scale)/65536
        end
        -- The SPC publishes its clock in four-millisecond ticks. Include
        -- that publication latency when predicting the next video poll.
        lead=1+word(C.addr.speed_scale)/65536""")
    (out/'replay.lua').write_text(replay)
    for name in ('result.txt','audio-mode.txt','verification.json'):(out/name).unlink(missing_ok=True)
    result=subprocess.run([r'C:\mesen2\Mesen.exe','--testrunner','--timeout=450',str(out/'adofai.sfc'),str(out/'replay.lua')],
        env=dict(os.environ,ADOFAI_TEST_CONFIG=str(out/'config.lua')),capture_output=True,text=True,timeout=480,creationflags=subprocess.CREATE_NO_WINDOW)
    (out/'emulator.log').write_text(result.stdout+result.stderr)
    report=(out/'result.txt').read_text();audio=(out/'audio-mode.txt').read_text() if (out/'audio-mode.txt').exists() else ''
    assert result.returncode==0 and report.endswith('PASS\n') and audio.endswith('PASS\n'),report
    assert identity(pack/'adofai.sfc')==frozen and identity(out/'adofai.sfc')==frozen
    (out/'verification.json').write_text(json.dumps(dict(passed=True,**frozen,result=report.splitlines()[0],audio=audio),indent=2))
    overruns=re.search(r'vblank_overruns=(\d+)',report)
    assert overruns and int(overruns[1])==0
    (out/'manifest.json').write_text(json.dumps(dict(passed=True,**frozen,vfx_off=False,
        vblank_overruns=int(overruns[1]),graphics_dumps=True,sampled_graphics=True,audio_mode='BRR'),indent=2))
    print('COMPRESSED MANUAL PASS',args.level_id,flush=True)

if __name__=='__main__':main()
