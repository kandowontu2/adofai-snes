"""Measure section presentation progress and VBlank safety in MesenCE."""
import argparse,json,os,re,subprocess
from pathlib import Path
from verification_data import identity

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--rom',type=Path,required=True);ap.add_argument('--labels',type=Path,required=True);ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--metadata',type=Path,help='Pack metadata when profiling an installed release folder');ap.add_argument('--level',type=int,default=23);ap.add_argument('--steps',type=int,nargs=2,default=[75,110]);ap.add_argument('--frames',type=int,default=2500);ap.add_argument('--max-hold',type=int);ap.add_argument('--max-display-age',type=int,help='Separate chart-clock latency bound; defaults to max-hold');ap.add_argument('--manual',action='store_true',help='Replay controller inputs rather than enabling autoplay');ap.add_argument('--manual-jitter',action='store_true',help='Vary taps by one frame to exercise distinct hit-meter marks');ap.add_argument('--manual-jitter-frames',type=int,default=1);ap.add_argument('--manual-practice',action='store_true');ap.add_argument('--free-entry-lead',type=int,default=1);ap.add_argument('--tap-free-entries',action='store_true',help='Also press at automatic free-roam entry, one frame early');a=ap.parse_args()
    a.out.mkdir(parents=True,exist_ok=True)
    labels={n:int(v,16) for v,n in re.findall(r'al ([0-9a-fA-F]+) \.([\w]+)',a.labels.read_text())}
    fields={n:labels[n]&0x1ffff for n in ('state','step','music_active','commits','chart_time','display_chart_time','profile_phase','animation_time','animation_kind','pattern_vblank_overruns','elapsed','nmi_audio_ticks','audio_ticks','speed_offset')}
    script='local A={'+','.join(n+'='+str(v) for n,v in fields.items())+'}\n'
    script+='local output='+json.dumps((a.out/'presentation.json').resolve().as_posix())+'\n'
    levels=json.loads(((a.metadata or a.rom.parent)/'pack.json').read_text())['levels']
    index=levels.index(a.level);actions=({90:'x'} if a.manual_practice else {}) if a.manual else {90:'y'};f=100
    if 'menu_depth' in labels:
        from menu_sets import groups
        sets=groups(levels);group=next(i for i,(_,members) in enumerate(sets) if index in members)
        if len(sets)>1:
            for _ in range(group):actions[f]='down';f+=4
            actions[f]='start';f+=8
        index=sets[group][1].index(index)
    for _ in range(index):actions[f]='down';f+=4
    actions[max(180,f+8)]='start'
    if a.manual:
        chart=json.loads(((a.metadata or a.rom.parent)/f'level{a.level}.json').read_text())
        events=[];held=key=0
        for i,note in enumerate(chart['notes'][1:],1):
            if note['flags']&8:continue
            previous=chart['notes'][i-1]
            if previous['flags']&16 and i>=2:previous=chart['notes'][i-2]
            if previous.get('hold_length',-1)>=0 and note.get('hold_length',-1)<0:held=0
            else:key=1 if key!=1 else 2;held=key
            jitter=(-1,0,1,0)[i%4]*a.manual_jitter_frames if a.manual_jitter else 0
            events.append((note['frame']+jitter,held))
        # Free-roam objectives need actual directional hops too. Without
        # these taps a rhythm-only profile dies at the coin check, silently
        # measuring only the part before the requested transition.
        for region in chart.get('freeroam_regions',[]):
            route=region.get('demo_route',[])
            if not route:continue
            if a.tap_free_entries:
                # Replace the ordinary landing edge, rather than pressing
                # again on the following frame and cancelling the first hop.
                events=[(t,v) for t,v in events if t!=region['start']]
            held=next((v for t,v in sorted(events,reverse=True) if t<=region['start']),1)
            held=held if held in (1,2) else 1
            if a.tap_free_entries:
                held=3-held;events.append((region['start']-a.free_entry_lead,held))
            for at,x,y,angle in route:
                held=3-held;events.append((at,held))
            events.append((route[-1][0]+3,0))
        events.sort()
        script+='local manual_events={'+','.join('{'+str(t)+','+str(v)+'}' for t,v in events)+'};local manual_index=1;local manual_held=0\n'
    script+='local actions={'+','.join(f'[{f}]="{button}"' for f,button in actions.items())+'}\n'
    script+=f'local first_step={a.steps[0]};local last_step={a.steps[1]};local finish_frame={a.frames}\n'
    script+='''local W=emu.memType.snesWorkRam
local frame=0;local measured=0;local delivered=0;local last=nil;local gap=0;local maximum=0;local max_age=0;local max_lead=0;local furthest=0
local trace=io.open(output..'.csv','w');trace:write('frame,step,clock,display,commit,phase,event_time,event_kind,worker,remaining,atomic,deferrals,done,pending,dma_request,dma_active,active,limit,view_w,view_h,delta_flags,delta_budget,identity,tag_count,native_ready\\n')
local function bw(a)return emu.read(a,emu.memType.snesSaveRam)+256*emu.read(a+1,emu.memType.snesSaveRam)end
local function ir(a)return emu.read(a,emu.memType.sa1InternalRam)+256*emu.read(a+1,emu.memType.sa1InternalRam)end
local function word(a)return emu.read(a,W)+256*emu.read(a+1,W)end
emu.addEventCallback(function()
 local b={}
 if actions[frame] then b[actions[frame]]=true end
 if manual_events then
  local function w(a)return emu.read(a,W)+256*emu.read(a+1,W)end
  if w(A.state)==1 then
   local delta=(w(A.nmi_audio_ticks)-w(A.audio_ticks)+32768)%65536-32768
   local offset=w(A.speed_offset);if offset>=32768 then offset=offset-65536 end
   local current=w(A.elapsed)+delta*.004*60.0988118623-offset
   while manual_events[manual_index] and current+1>=manual_events[manual_index][1]do
    manual_held=manual_events[manual_index][2];manual_index=manual_index+1
   end
   if manual_held%2==1 then b.a=true end
   if math.floor(manual_held/2)%2==1 then b.b=true end
  end
 end
 emu.setInput(b,0)
end,emu.eventType.inputPolled)
-- Count/input scheduling stays at startFrame. Measure after visible output:
-- a safe NMI can finish its non-PPU bookkeeping in the top HUD band.
emu.addEventCallback(function() frame=frame+1 end,emu.eventType.startFrame)
emu.addEventCallback(function()
 local step=word(A.step);furthest=math.max(furthest,step)
 if word(A.state)==1 and word(A.music_active)==1 and step>=first_step and step<=last_step then
  measured=measured+1
  if last then gap=gap+1 end
  local commit=word(A.commits)
  trace:write(string.format('%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d\\n',frame,step,word(A.chart_time),word(A.display_chart_time),commit,word(A.profile_phase),word(A.animation_time),word(A.animation_kind),bw(0x30),bw(0x1fc4c),bw(0x1fc5a),bw(0x1fc90),ir(0x782),ir(0x78a),ir(0x784),ir(0x786),bw(0x1fc70),bw(0x1fcc6),bw(0x1fcbc),bw(0x1fcbe),bw(0x3ef1e),bw(0x2b700),bw(0x1fca0),bw(0x16c22),bw(0x2b200)))
  if last and commit~=last then delivered=delivered+1;maximum=math.max(maximum,gap);gap=0 end
  maximum=math.max(maximum,gap)
  local age=(word(A.chart_time)-word(A.display_chart_time)+32768)%65536-32768
  max_age=math.max(max_age,age);max_lead=math.max(max_lead,-age)
  last=commit
 end
 if frame==finish_frame then
  local f=io.open(output,'w')
  f:write(string.format('{"frames":%d,"delivered":%d,"fps":%.6f,"max_gap":%d,"max_display_age":%d,"vblank_overruns":%d,"max_display_lead":%d,"furthest_step":%d}',measured,delivered,60.0988*delivered/math.max(1,measured-1),maximum,max_age,word(A.pattern_vblank_overruns),max_lead,furthest))
  f:close();trace:close();emu.stop(0)
 end
end,emu.eventType.endFrame)
'''
    path=a.out/'profile.lua';path.write_text(script)
    before=identity(a.rom)
    (a.out/'presentation.json').unlink(missing_ok=True)
    r=subprocess.run([r'C:\mesen2\Mesen.exe','--testrunner','--timeout=300',str(a.rom.resolve()),str(path.resolve())],creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0,capture_output=True,text=True,timeout=330)
    (a.out/'emulator.log').write_text(r.stdout+r.stderr)
    assert r.returncode==0,(r.stdout,r.stderr)
    assert before==identity(a.rom),'ROM or MSU data changed while profiling'
    result=json.loads((a.out/'presentation.json').read_text());assert result['frames']>0
    result.update(before);result['step_range']=a.steps;result['level']=a.level;result['sample_phase']='endFrame';result['input_mode']='manual' if a.manual else 'autoplay';result['manual_jitter']=a.manual_jitter;result['manual_jitter_frames']=a.manual_jitter_frames;result['practice']=a.manual_practice
    (a.out/'result.json').write_text(json.dumps(result,indent=2));print(result)
    target_chart=json.loads(((a.metadata or a.rom.parent)/f'level{a.level}.json').read_text())
    assert result['furthest_step']>=min(a.steps[1],len(target_chart['notes'])-1),('Replay did not cover requested section',result)
    assert result['vblank_overruns']==0,result
    if a.max_hold is not None:
        assert result['max_gap']<=a.max_hold,result
    age_limit=a.max_display_age if a.max_display_age is not None else a.max_hold
    if age_limit is not None:assert result['max_display_age']<=age_limit,result

if __name__=='__main__':main()
