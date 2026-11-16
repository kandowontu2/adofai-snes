"""Sample authored planet visibility/size without evaluating tweens on cartridge."""
import bisect,json
from pathlib import Path
from track_motion import enabled,easing
from make_assets import FPS
ROOT=Path(__file__).resolve().parents[1]

def schedule(data,chart):
    commands=[[],[],[]]
    for order,a in enumerate(data.get('featured_actions',[])):
        if a['eventType']!='ScalePlanets' or not enabled(a.get('active',True)):continue
        if a.get('eventTag'):raise ValueError('Conditional planet scaling requires a runtime callback')
        n=chart['notes'][a['floor']];beat=60/data['bpm']/n['speed']*FPS
        start=max(0,round(n['time']*FPS+a.get('angleOffset',0)/180*beat))
        targets={'All':(0,1,2),'Both':(0,1,2),'FirePlanet':(0,),'IcePlanet':(1,),'GreenPlanet':(2,)}[a['targetPlanet']]
        for target in targets:commands[target].append((start,order,a.get('duration',0)*beat,a['scale']/100,a.get('ease','Linear')))
    if not any(commands):return []
    tracks=[]
    for row in commands:
        row.sort();track=[]
        for start,order,duration,target,ease in row:
            previous=1.
            if track:
                at,length,origin,end,curve=track[-1]
                phase=1 if length<=0 else min(1,max(0,(start-at)/length))
                previous=origin+(end-origin)*easing(curve,phase)
            track.append((start,duration,previous,target,ease))
        tracks.append(([r[0] for r in track],track))
    rows=[]
    for frame in range(chart['notes'][-1]['frame']+121):
        values=[]
        for times,track in tracks:
            value=1.
            index=bisect.bisect_right(times,frame)-1
            if index>=0:
                start,duration,previous,target,ease=track[index]
                phase=1 if duration<=0 else min(1,(frame-start)/duration)
                value=previous+(target-previous)*easing(ease,phase)
            values.append(max(0,min(32,round(value*16)))*16)
        if not rows or values!=rows[-1][1:]:rows.append([frame,*values])
    return rows

def tables(folder,levels):
    entries=[];rows=[]
    for local,n in enumerate(levels):
        path=ROOT/f'assets/private/level{n}.json'
        if not path.exists():continue
        data=json.loads(path.read_text())
        if not data.get('planet_scale_import'):continue
        events=schedule(data,json.loads((Path(folder)/f'level{n}.json').read_text()))
        if events:
            start=len(rows)*8;rows.extend(events);entries.append((local,start,len(rows)*8))
    if not entries:return ''
    assert len(rows)*8<32768, 'Binary-search midpoint must fit a 16-bit sum'
    return '\n.segment "NEOCODE"\nPLANET_SCALE_LEVEL_COUNT = '+str(len(entries))+'\n'+''.join(
        label+': .word '+','.join(str(row[column]) for row in entries)+'\n'
        for column,label in enumerate(('planet_scale_levels','planet_scale_starts','planet_scale_ends')))+\
        'planet_scale_rows: .word '+','.join(str(v) for row in rows for v in row)+'\n'+\
        'planet_scale_radii: .byte '+','.join(str(min(15,(radius*scale+8)//16)) for scale in range(33) for radius in range(16))+'\n.segment "RODATA"\n'
