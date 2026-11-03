"""Replay official cartridge packs in the independent Mesen SNES core."""
import argparse,json,os,re,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
import hashlib,sys
sys.path.insert(0,str(ROOT/'tools'))
from official_catalog import PACKS
from verification_data import identity
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--mesen',type=Path,default=Path(r'C:\mesen2\Mesen.exe'))
    ap.add_argument('--levels',type=int,nargs='+');ap.add_argument('--pack',default='main');ap.add_argument('--all',action='store_true');ap.add_argument('--checkpoints',action='store_true')
    ap.add_argument('--speed',type=float,default=1.0);ap.add_argument('--time-attack',action='store_true');ap.add_argument('--resume',action='store_true')
    ap.add_argument('--trace-frame',type=int);ap.add_argument('--graphics-dumps',action='store_true');ap.add_argument('--capture-steps',type=int,nargs='+');ap.add_argument('--autoplay',action='store_true');args=ap.parse_args()
    speed=round(args.speed*10);assert 5<=speed<=20 and abs(speed-args.speed*10)<1e-6
    assert not(args.checkpoints and args.time_attack)
    for pack in PACKS if args.all else [args.pack]:
      base=ROOT/'build/campaign' if pack=='main' else ROOT/f'build/packs/{pack}'
      labels={m[1]:int(m[0],16) for m in re.findall(r'al ([0-9A-Fa-f]+) \.([\w]+)',(base/'adofai.lbl').read_text())}
      levels=json.loads((base/'pack.json').read_text())['levels']
      for level in args.levels or range(1,len(levels)+1):
        suffix=f'-speed-{speed:02d}'+('-attack' if args.time_attack else '') if speed!=10 or args.time_attack else ''
        if args.autoplay:suffix+='-autoplay'
        out=base/f'verification/mesen-{"checkpoints-" if args.checkpoints else ""}{level}{suffix}';out.mkdir(parents=True,exist_ok=True)
        if args.graphics_dumps:
            for capture in out.glob('ppu-*.bin'):capture.unlink()
        global_id=levels[level-1]
        chart=json.loads((base/f'level{global_id}.json').read_text())
        if args.checkpoints and not chart['checkpoints']:continue
        digest=hashlib.sha256((base/'adofai.sfc').read_bytes()).hexdigest()
        loaded_identity=identity(base/'adofai.sfc')
        report=out/'result.txt';manifest=out/'manifest.json'
        if args.resume and report.exists() and manifest.exists():
            previous=json.loads(manifest.read_text())
            if previous['sha256']==digest and previous.get('msu_sha256')==loaded_identity['msu_sha256'] and report.read_text().endswith('PASS\n'):
                print(chart['code']+': PASS (current ROM already verified)',flush=True)
                continue
        names=('state','step','elapsed','combo','perfects','misses','selected_level','speed_tenths','time_attack','judgment_counts','score_lo','score_hi','finish_cs','nmi_audio_ticks','audio_ticks','speed_offset')
        if chart.get('track_palette_versions'):names+=('display_state','display_chart_time')
        if args.graphics_dumps:names+=('display_state','display_chart_time','display_cam_x','display_cam_y','commits')
        names=tuple(dict.fromkeys(names))
        if args.checkpoints:names+=('checkpoint_floor','checkpoint_preroll','music_origin','checkpoints_used','display_state','cam_x','cam_y','angle','chart_time')
        cpconfig=''
        if args.checkpoints:cpconfig=',checkpoints={'+','.join('{trigger='+str(c['trigger'])+',floor='+str(c['floor'])+',origin='+str(c['origin_frame'])+'}' for c in chart['checkpoints'])+'}'
        actions=''
        if suffix:
            seq={90:'b'};f=96
            if args.time_attack:seq[f]='right';f+=4
            seq[f]='down';f+=4
            for _ in range(abs(speed-10)):seq[f]='right' if speed>10 else 'left';f+=4
            seq[f]='start';f+=8
            for _ in range(level-1):seq[f]='down';f+=4
            seq[f+12]='start'
            actions=',menu_actions={'+','.join('['+str(k)+']="'+v+'"' for k,v in seq.items())+'}'
        pitch=round(1536*speed/10)
        if json.loads((base/'pack.json').read_text()).get('fast_audio_rate') and speed>10:pitch=round(pitch/3)*3
        scheduled=',pitch='+str(pitch)+',manual_times={'+','.join(str(n['frame']) for n in chart['notes'][1:] if not(n['flags']&8))+'},manual_steps={'+','.join(str(n['step']) for n in chart['notes'][1:] if not(n['flags']&8))+'}'
        if args.autoplay:scheduled+=',autoplay=true'
        if args.graphics_dumps:scheduled+=',graphics_dumps=true'
        if args.trace_frame:scheduled+=',trace_frame='+str(args.trace_frame)
        if args.capture_steps:scheduled+=',capture_steps={'+','.join(map(str,args.capture_steps))+'}'
        if chart.get('track_palette_versions'):
            scheduled+=',palette_script='+json.dumps((ROOT/'tools/verify_palette_mesen.lua').as_posix())+',palette={'+','.join('{'+','.join(map(str,e))+'}' for e in chart['track_palette_versions'])+'}'
        config='return {addr={'+','.join(k+'='+str(labels[k]) for k in names)+'},times={'+','.join(str(n['frame']) for n in chart['notes'])+'},out='+json.dumps(out.as_posix())+',level='+str(level)+',steps='+str(chart['steps'])+',hits='+str(chart['hits'])+',speed='+str(speed)+',attack='+str(int(args.time_attack))+',finish_centis='+str(round(chart['notes'][-1]['time']*100*1536/pitch) if 'time' in chart['notes'][-1] else round(chart['notes'][-1]['frame']/60.0988118623*100*1536/pitch))+',frames='+str(round(chart['duration']*60.099*1536/pitch)+600+(len(chart['checkpoints'])*900 if args.checkpoints else 0))+cpconfig+actions+'}\n'
        config=config.rstrip()[:-1]+scheduled+'}\n'
        path=out/'config.lua';path.write_text(config)
        env=os.environ.copy();env['ADOFAI_TEST_CONFIG']=str(path)
        script='verify_checkpoints_mesen.lua' if args.checkpoints else 'verify_campaign_mesen.lua'
        if report.exists():report.unlink()
        # Mesen's own default wall-clock limit is shorter than long songs
        # under concurrent verification. Keep both limits explicit.
        result=subprocess.run([str(args.mesen),'--testrunner','--timeout=300',str(base/'adofai.sfc'),str(ROOT/'tools'/script)],env=env,cwd=ROOT,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0,timeout=330,capture_output=True,text=True)
        (out/'emulator.log').write_text(result.stdout+result.stderr)
        report=out/'result.txt'
        if not report.exists():raise RuntimeError(f'Mesen exited {result.returncode} without a result; see {out / "emulator.log"}\n'+result.stdout[-2000:]+result.stderr[-2000:])
        text=report.read_text();print(chart['code']+': '+text.splitlines()[0],flush=True)
        assert identity(base/'adofai.sfc')==loaded_identity,'ROM or MSU data changed during Mesen verification'
        samples=re.search(r'palette_samples=(\d+)',text)
        (out/'manifest.json').write_text(json.dumps(dict(code=chart['code'],sha256=digest,**loaded_identity,summary=text.splitlines()[0],speed=speed/10,time_attack=args.time_attack,track_palette_samples=int(samples[1]) if samples else 0),indent=2))
        assert result.returncode==0 and text.endswith('PASS\n'),text[-1000:]
if __name__=='__main__':main()
