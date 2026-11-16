"""Compile explicitly supported perfect-only conditional hazard sections."""
import json
from pathlib import Path
from track_motion import enabled
ROOT=Path(__file__).resolve().parents[1]

def ranges(data):
    tag=data.get('perfect_only_tag')
    if not tag:return []
    hazards=[d for d in data.get('featured_decorations',[]) if tag in d.get('tag','').split()
             and d.get('hitbox')=='Kill' and d.get('relativeTo') in ('RedPlanet','BluePlanet')]
    assert {d['relativeTo'] for d in hazards}=={'RedPlanet','BluePlanet'},'Missing conditional death hazards'
    actions=[a for a in data.get('featured_actions',[]) if enabled(a.get('active',True))]
    moves=[a for a in actions if a['eventType']=='MoveDecorations' and a.get('eventTag')==tag]
    assert moves and all(tag in a.get('tag','').split() and a.get('duration',0)==0 for a in moves)
    for d in hazards:
        for a in moves:
            assert all(abs(p+(o or 0))<1e-6 for p,o in zip(d.get('position',[0,0]),a['positionOffset'])), 'Death hazard must land on the planet'
    events={a['floor']:a for a in actions if a['eventType']=='SetConditionalEvents'}
    result=[];first=None
    for floor in range(len(data['floors'])+1):
        if floor not in events and floor<len(data['floors']):continue
        condition=events.get(floor,{})
        active=condition.get('earlyPerfectTag')==tag or condition.get('latePerfectTag')==tag
        if active:
            assert all(condition.get(k)==tag for k in ('earlyPerfectTag','latePerfectTag','veryEarlyTag','veryLateTag','tooEarlyTag','tooLateTag'))
            assert condition.get('perfectTag','NONE') in ('','NONE')
        if active and first is None:first=floor
        elif not active and first is not None:result.append((first,floor));first=None
    return result

def tables(folder,levels):
    entries=[];rows=[]
    for local,n in enumerate(levels):
        path=ROOT/f'assets/private/level{n}.json'
        if not path.exists():continue
        intervals=ranges(json.loads(path.read_text()))
        if not intervals:continue
        start=len(rows)*4;rows.extend(intervals)
        entries.append((local,start,len(rows)*4))
    if not entries:return ''
    return '\n.segment "NEOCODE"\nCONDITIONAL_LEVEL_COUNT = '+str(len(entries))+'\n'+''.join(
        label+': .word '+','.join(str(row[column]) for row in entries)+'\n'
        for column,label in enumerate(('conditional_levels','conditional_starts','conditional_ends')))+\
        'conditional_ranges: .word '+','.join(str(v) for row in rows for v in row)+'\n.segment "RODATA"\n'
