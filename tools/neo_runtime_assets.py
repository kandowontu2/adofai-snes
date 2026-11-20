"""Small ROM lookups for native planet easing; no per-frame curve evaluation."""
import json
import math
from pathlib import Path
from track_motion import easing
from hold_path import sweep
from pack_sources import load_source

ROOT=Path(__file__).resolve().parents[1]


def planet_roles(notes):
    """Follow native insertion order; a twirl changes motion, not the list."""
    roles=(0,1,2);previous=None;result=[]
    for i,note in enumerate(notes):
        if note['planets']==3:
            if previous is None or previous['planets']!=3:
                pivot=i&1
                # SetNumPlanets inserts the new orb immediately before the
                # old chosen orb. After landing, it is next to move; the
                # old chosen orb stays behind on the tile it already held.
                roles=(pivot,2,pivot^1) if i else (0,1,2)
            else:
                pivot,active,trailing=roles
                roles=(trailing,pivot,active) if note.get('flags',0)&16 else (active,trailing,pivot)
        else:roles=(i&1,(i&1)^1,2)
        result.append(roles);previous=note
    return result


def phase(ease, value, parts=1, mirror=True):
    if parts<=0 or ease==1:return value
    scaled=value*parts
    cycle=min(parts-1,math.floor(scaled))
    local=scaled-cycle
    eased=1-easing(ease,1-local) if mirror and cycle%2 else easing(ease,local)
    return (cycle+eased)/parts


def twirl_curve(note, following, bpm):
    """Native OutSine reflection back to the ordinary orbit over half an arc."""
    duration=following['frame']-note['frame']
    if duration<=0:return []
    free=note.get('freeroam',False)
    tween=60/bpm*note['speed']*.375*60.0988118623 if free else duration/2
    initial=.5 if free else 1
    entry=note['entry_angle'];exit=note['exit_angle'];tau=math.tau
    if abs(entry-exit)>tau:exit+=tau if exit<entry else -tau
    aligned=min(abs(entry-exit)%tau,tau-abs(entry-exit)%tau)<.0001
    result=[]
    for frame in range(min(duration,math.ceil(tween))+1):
        normal=entry if aligned else entry+(exit+(math.pi if entry>exit else -math.pi)-entry)*frame/duration
        weight=initial*(1-math.sin(min(1,frame/tween)*math.pi/2))
        co=math.cos(2*normal);si=math.sin(2*normal)
        result.append(tuple(round(v*256) for v in (1-weight+weight*co,weight*si,1-weight-weight*co)))
    return result


def planet_previews(notes, floors):
    """Two-to-three insertion guide, in the entry tile's world coordinates."""
    rows=[]
    for i,n in enumerate(notes):
        if not i or n['planets']!=3 or notes[i-1]['planets']==3:continue
        radius=24*floors[i].get('radiusScale',1)
        entry=n['entry_angle']
        apex=entry+(-math.pi/3 if n['ccw'] else math.pi/3)
        rows.append((i,*(round(radius*f(a)) for a in (entry,apex) for f in (math.cos,math.sin))))
    return rows


def table_source(out,levels):
    records=[];samples=[];phases=[];radius_samples=[];tails=[];starts=[];counts=[];shared={}
    for level in levels:
        starts.append(len(records)*8)
        chart=json.loads((out/f'level{level}.json').read_text())
        if not chart.get('neo_cosmos'):
            counts.append(0);continue
        raw=load_source(out,level)
        count=0
        for i,floor in enumerate(raw['floors'][:-1]):
            n=chart['notes'][i];end=chart['notes'][i+1]['frame']
            hold=n.get('hold_length',-1)>=0
            radius=floor.get('radiusScale',1);next_radius=raw['floors'][i+1].get('radiusScale',1)
            if floor.get('planetEase',1)==1 and not hold and radius==next_radius:continue
            duration=end-n['frame']
            if duration<=0:continue
            # The original applies easing to the whole floor arc, including
            # each complete hold turn, rather than easing every video step.
            span=sweep(n)*128/math.pi if hold else duration*n['rate']/256
            angles=[];fractions=[];sizes=[]
            for frame in range(duration+1):
                p=phase(floor.get('planetEase',1),frame/duration,floor.get('planetEaseParts',1),floor.get('planetEasePartBehavior',0)==0)
                # Translation and orbital angle must sample the same phase.
                # Otherwise rounding the hold duration drifts the planet away
                # from the rendered loops, especially on short/fast holds.
                if hold:p=round(p*256)/256
                angles.append(round(n['angle']+span*p)&255)
                fractions.append(round(p*256)&65535)
                sizes.append(round((radius+(next_radius-radius)*max(0,min(1,p)))*256))
            key=(tuple(angles),tuple(fractions),tuple(sizes))
            if key not in shared:
                shared[key]=len(samples);samples.extend(angles);phases.extend(fractions);radius_samples.extend(sizes)
            records.append((i,n['frame'],duration,shared[key]))
            # The hold pivot ends one radius behind the release floor.
            # NOTE_ANGLE on that floor includes multiplanet spacing and is
            # not the hold's exit direction (60 degrees different for three).
            tails.append((round(-24*next_radius*math.cos(n['exit_angle'])),
                          round(-24*next_radius*math.sin(n['exit_angle']))))
            count+=1
        counts.append(count)
    assert len(samples)*2<65536,'Native orbit curve lookup address capacity'
    lines=['; NEO_TABLES', 'neo_ease_starts: .word '+','.join(map(str,starts)),
           'neo_ease_counts: .word '+','.join(map(str,counts)), 'neo_ease_records:']
    lines+=['.word '+','.join(map(str,row)) for row in records]
    lines+=['neo_ease_tails:']
    lines+=['.word '+','.join(str(v&65535) for v in row) for row in tails]
    lines+=['neo_ease_samples:']
    lines+=['.byte '+','.join(map(str,samples[i:i+32])) for i in range(0,len(samples),32)]
    lines+=['neo_ease_phases:']
    lines+=['.word '+','.join(map(str,phases[i:i+16])) for i in range(0,len(phases),16)]
    lines+=['neo_ease_radii:']+['.word '+','.join(map(str,radius_samples[i:i+16])) for i in range(0,len(radius_samples),16)]
    hold_starts=[];hold_styles=[];motion_starts=[];radii=[];margins=[]
    for level in levels:
        hold_starts.append(len(hold_styles))
        chart=json.loads((out/f'level{level}.json').read_text())
        if not chart.get('neo_cosmos'):
            motion_starts.append(65535)
            continue
        assert len(chart['notes'])<65536,'Planet presentation chart exceeds one offset bank'
        raw=load_source(out,level)
        scaled=any(f.get('radiusScale',1)!=1 or n.get('margin',100)!=(800 if n.get('margin',100)>100 else 100)
                   for f,n in zip(raw['floors'],chart['notes']))
        motion_starts.append(len(radii)*2 if scaled else 65535)
        role_schedule=planet_roles(chart['notes'])
        for i, note in enumerate(chart['notes']):
            if scaled:
                radii.append(round(raw['floors'][i].get('radiusScale',1)*256))
                margins.append(round(note.get('margin',100)))
            pivot, active, trailing = role_schedule[i]
            hold_styles.append(int(note.get('hold_length', -1) > 0)
                               | pivot << 1 | active << 3 | trailing << 5)
    lines+=['neo_hold_starts: .word '+','.join(map(str,hold_starts)),'neo_hold_styles:']
    lines+=['.byte '+','.join(map(str,hold_styles[i:i+32])) for i in range(0,len(hold_styles),32)]
    for name,values in [('neo_motion_starts',motion_starts),('neo_orbit_radii',radii),('neo_note_margins',margins)]:
        lines += [name+':']+['.word '+','.join(map(str,values[i:i+16])) for i in range(0,len(values),16)]
    free_records=[];free_starts=[];free_counts=[];free_phases=[];free_cells=[];coins=[];hazards=[];routes=[];lasers=[];deaths=[];entries=[];twirls=[]
    twirl_ranges=[];twirl_positions=[];coin_requirements=[];coin_types=[];coin_modes=[];coin_targets=[];pickup_lives=[]
    pickup_ui=[];question_starts=[];question_text=[]
    for level in levels:
        chart=json.loads((out/f'level{level}.json').read_text())
        regions=chart.get('freeroam_regions',[])
        free_starts.append(len(free_records)*64);free_counts.append(len(regions))
        for r in regions:
            coin_requirements.append(r.get('coin_required',3))
            coin_types.extend(r.get('coin_types',[0]*len(r.get('coins',[]))))
            coin_modes.extend(r.get('coin_modes',[1,0,0,0]))
            coin_targets.extend(r.get('coin_targets',[r.get('coin_required',3),0,0,0]))
            pickup_lives.append(r.get('pickup_lives',0))
            pickup_ui.append(r.get('pickup_ui',0))
            question_starts.append(len(question_text))
            for question in r.get('question_texts',[]):
                assert len(question)==3
                for line in question:
                    assert len(line)<=32,('Question exceeds HUD width',line)
                    question_text.extend(line.upper().encode('ascii').ljust(32,b' '))
            n=chart['notes'][r['step']];following=chart['notes'][r['step']+1]
            origin_offset=n.get('position_track_offset',(0,0))
            exit_offset=following.get('position_track_offset',(0,0))
            entries.extend(r.get('entry',(0,0)))
            twirl_cells={tuple(p) for p in r.get('twirls',[])}
            twirl_ranges.append((len(twirl_positions)*2,len(twirl_cells)))
            twirl_positions.extend(v for p in sorted(twirl_cells) for v in p)
            twirls.extend(int(tuple(p) in twirl_cells) for p in r['cells'])
            offset=len(free_phases)*2
            free_phases.extend(round(easing(r['ease'],i/r['return_duration'])*256) for i in range(r['return_duration']+1))
            rate=abs(n['rate'])*(-1 if following['ccw'] else 1)
            free_records.append((r['step'],r['start'],r['return_start'],r['return_duration'],r['unlock'],r['end'],*r['bounds'],
                                 following['x']-n['x']+r['exit_offset'][0]+exit_offset[0]-origin_offset[0],following['y']-n['y']+r['exit_offset'][1]+exit_offset[1]-origin_offset[1],offset,
                                 # UpdateFreeroam aims at the entry vector,
                                 # before the new floor's multiplanet spacing.
                                 (round(following['entry_angle']*128/math.pi)+128)&255,rate,int(r['move_camera']),len(free_cells)*2,len(r['cells']),
                                 len(coins)*2,len(r.get('coins',[])),r.get('coin_check',65535),len(hazards)*10,len(r.get('hazards',[])),
                                 int(chart['code'] in ('T3-X', 'T3EX-X')),
                                 len(routes)*8,len(r.get('demo_route',[])),r['fade_duration'],len(lasers)*2,r.get('laser',{}).get('start',0),r.get('laser',{}).get('end',0),r.get('laser',{}).get('axis',0),len(deaths)*2))
            lasers.extend(v for rect in r.get('laser',{}).get('rectangles',[]) for v in rect)
            deaths.extend(r.get('cell_deaths',[65535]*len(r['cells'])))
            routes.extend(r.get('demo_route',[]))
            free_cells.extend(v for p in r['cells'] for v in p)
            coins.extend(v for p in r.get('coins',[]) for v in p)
            for h in r.get('hazards',[]):
                hazards.append((h['warn'],h['check'],h['end'],len(free_cells)*2,len(h['cells'])))
                free_cells.extend(v for p in h['cells'] for v in p)
                twirls.extend(0 for p in h['cells'])
    lines+=['neo_free_starts: .word '+','.join(map(str,free_starts)),
            'neo_free_counts: .word '+','.join(map(str,free_counts)), 'neo_free_records:']
    lines+=['.word '+','.join(str(v&65535) for v in row) for row in free_records]
    lines+=['neo_free_phases:']
    lines+=['.word '+','.join(map(str,free_phases[i:i+16])) for i in range(0,len(free_phases),16)]
    lines+=['neo_free_cells:']
    lines+=['.word '+','.join(str(v&65535) for v in free_cells[i:i+16]) for i in range(0,len(free_cells),16)]
    lines+=['neo_free_entries:']+['.word '+','.join(str(v&65535) for v in entries[i:i+16]) for i in range(0,len(entries),16)]
    lines+=['neo_free_twirls:']+['.byte '+','.join(map(str,twirls[i:i+32])) for i in range(0,len(twirls),32)]
    lines+=['neo_free_twirl_ranges:']+['.word '+','.join(map(str,row)) for row in twirl_ranges]
    lines+=['neo_free_twirl_positions:']+['.word '+','.join(str(v&65535) for v in twirl_positions[i:i+16]) for i in range(0,len(twirl_positions),16)]
    lines+=['neo_free_coins:']
    lines+=['.word '+','.join(str(v&65535) for v in coins[i:i+16]) for i in range(0,len(coins),16)]
    lines+=['neo_free_coin_requirements: .word '+','.join(map(str,coin_requirements or [3]))]
    for name,values in [('neo_coin_types',coin_types),('neo_coin_modes',coin_modes),('neo_coin_targets',coin_targets),('neo_pickup_lives',pickup_lives),('neo_pickup_ui',pickup_ui),('neo_question_text_starts',question_starts)]:
        lines += [name+':']+['.word '+','.join(map(str,values[i:i+16])) for i in range(0,len(values),16)]
    lines+=['neo_question_text:']+['.byte '+','.join(map(str,question_text[i:i+32])) for i in range(0,len(question_text),32)]
    lines+=['neo_free_hazards:']
    lines+=['.word '+','.join(map(str,row)) for row in hazards]
    lines+=['neo_free_routes:']
    lines+=['.word '+','.join(str(v&65535) for v in row) for row in routes]
    for name,values in [('neo_free_lasers',lasers),('neo_free_deaths',deaths)]:
        lines += [name+':']+['.word '+','.join(str(v&65535) for v in values[i:i+16]) for i in range(0,len(values),16)]
    meteor_starts=[];meteor_counts=[];meteors=[]
    for level in levels:
        chart=json.loads((out/f'level{level}.json').read_text())
        meteor_starts.append(len(meteors)*14)
        events=chart.get('neo_meteors',[]);meteor_counts.append(len(events))
        for e in events:
            n=chart['notes'][e['judge']]
            meteors.append((e['start'],e['end'],e['judge'],n['x']+e['dx'],n['y']+e['dy'],e['vx'],e['vy']))
    lines+=['neo_meteor_starts: .word '+','.join(map(str,meteor_starts)),
            'neo_meteor_counts: .word '+','.join(map(str,meteor_counts)), 'neo_meteor_records:']
    lines+=['.word '+','.join(str(v&65535) for v in row) for row in meteors]
    swirl_starts=[];swirl_counts=[];swirl_records=[];swirl_samples=[];swirl_shared={}
    for level in levels:
        chart=json.loads((out/f'level{level}.json').read_text());notes=chart['notes']
        swirl_starts.append(len(swirl_records)*8);count=0
        for i in range(1,len(notes)-1):
            note=notes[i]
            if note['planets']!=3 or notes[i-1]['planets']!=3 or not note['flags']&4:continue
            curve=twirl_curve(note,notes[i+1],chart['bpm'])
            if not curve:continue
            key=tuple(curve)
            if key not in swirl_shared:
                swirl_shared[key]=len(swirl_samples);swirl_samples.extend(curve)
            swirl_records.append((i,note['frame'],len(curve)-1,swirl_shared[key]));count+=1
        swirl_counts.append(count)
    assert len(swirl_records)*8<65536 and len(swirl_samples)*2<65536,'Twirl lookup address capacity'
    lines+=['neo_twirl_starts: .word '+','.join(map(str,swirl_starts)),
            'neo_twirl_counts: .word '+','.join(map(str,swirl_counts)),'neo_twirl_records:']
    lines+=['.word '+','.join(map(str,row)) for row in swirl_records]
    for j,name in enumerate(('a','b','d')):
        values=[row[j]&65535 for row in swirl_samples]
        lines+=['neo_twirl_'+name+':']+['.word '+','.join(map(str,values[i:i+16])) for i in range(0,len(values),16)]
    preview_rows=[];preview_starts=[];preview_counts=[]
    for level in levels:
        chart=json.loads((out/f'level{level}.json').read_text())
        raw=load_source(out,level)
        rows=planet_previews(chart['notes'],raw['floors'])
        preview_starts.append(len(preview_rows)*10);preview_counts.append(len(rows));preview_rows.extend(rows)
    assert len(preview_rows)*10<65536,'Planet preview record capacity'
    lines+=['neo_preview_starts: .word '+','.join(map(str,preview_starts)),
            'neo_preview_counts: .word '+','.join(map(str,preview_counts)),'neo_preview_records:']
    lines+=['.word '+','.join(str(v&65535) for v in row) for row in preview_rows]
    from neo_math import table_source as math_tables
    from decoration_hitboxes import table_source as decoration_tables
    return '\n'.join(lines)+'\n'+math_tables(out,levels)+decoration_tables(json.loads((out/f'level{n}.json').read_text()) for n in levels)


def binary_tables(out, levels):
    import struct
    data=bytearray();labels={}
    for line in table_source(out,levels).splitlines():
        line=line.split(';')[0].strip()
        if not line:continue
        if ':' in line:
            name,line=line.split(':',1);labels[name]=len(data);line=line.strip()
        if not line:continue
        kind,values=line.split(None,1)
        for value in values.split(','):
            data.extend(struct.pack('<H',int(value)&65535) if kind=='.word' else bytes([int(value)&255]))
    return bytes(data),labels


def tables(out, levels):
    data,labels=binary_tables(out,levels)
    base=json.loads((out/'placements.json').read_text())['neo_tables']
    return '; NEO_TABLES (banked read-only payload)\n'+'\n'.join(f'{name} = ${base+offset:06X}' for name,offset in labels.items())+'\n'
