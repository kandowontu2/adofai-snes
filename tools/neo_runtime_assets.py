"""Small ROM lookups for native planet easing; no per-frame curve evaluation."""
import json
import math
from pathlib import Path
from track_motion import easing
from hold_path import sweep

ROOT=Path(__file__).resolve().parents[1]


def phase(ease, value, parts=1, mirror=True):
    if parts<=0 or ease==1:return value
    scaled=value*parts
    cycle=min(parts-1,math.floor(scaled))
    local=scaled-cycle
    eased=1-easing(ease,1-local) if mirror and cycle%2 else easing(ease,local)
    return (cycle+eased)/parts


def table_source(out,levels):
    records=[];samples=[];phases=[];starts=[];counts=[];shared={}
    for level in levels:
        starts.append(len(records)*8)
        chart=json.loads((out/f'level{level}.json').read_text())
        if not chart.get('neo_cosmos'):
            counts.append(0);continue
        raw=json.loads((ROOT/f'assets/private/level{level}.json').read_text())
        count=0
        for i,floor in enumerate(raw['floors'][:-1]):
            n=chart['notes'][i];end=chart['notes'][i+1]['frame']
            hold=n.get('hold_length',-1)>=0
            if floor.get('planetEase',1)==1 and not hold:continue
            duration=end-n['frame']
            if duration<=0:continue
            # The original applies easing to the whole floor arc, including
            # each complete hold turn, rather than easing every video step.
            span=sweep(n)*128/math.pi if hold else duration*n['rate']/256
            angles=[];fractions=[]
            for frame in range(duration+1):
                p=phase(floor.get('planetEase',1),frame/duration,floor.get('planetEaseParts',1),floor.get('planetEasePartBehavior',0)==0)
                # Translation and orbital angle must sample the same phase.
                # Otherwise rounding the hold duration drifts the planet away
                # from the rendered loops, especially on short/fast holds.
                if hold:p=round(p*256)/256
                angles.append(round(n['angle']+span*p)&255)
                fractions.append(round(p*256)&65535)
            key=(tuple(angles),tuple(fractions))
            if key not in shared:
                shared[key]=len(samples);samples.extend(angles);phases.extend(fractions)
            records.append((i,n['frame'],duration,shared[key]))
            count+=1
        counts.append(count)
    lines=['; NEO_TABLES', 'neo_ease_starts: .word '+','.join(map(str,starts)),
           'neo_ease_counts: .word '+','.join(map(str,counts)), 'neo_ease_records:']
    lines+=['.word '+','.join(map(str,row)) for row in records]
    lines+=['neo_ease_samples:']
    lines+=['.byte '+','.join(map(str,samples[i:i+32])) for i in range(0,len(samples),32)]
    lines+=['neo_ease_phases:']
    lines+=['.word '+','.join(map(str,phases[i:i+16])) for i in range(0,len(phases),16)]
    hold_starts=[];hold_styles=[]
    for level in levels:
        hold_starts.append(len(hold_styles))
        chart=json.loads((out/f'level{level}.json').read_text())
        if not chart.get('neo_cosmos'):
            continue
        roles = (0, 1, 2)
        previous = None
        for i, note in enumerate(chart['notes']):
            if note['planets'] == 3:
                if previous is None or previous['planets'] != 3:
                    roles = (i & 1, (i & 1) ^ 1, 2)
                else:
                    pivot, active, trailing = roles
                    if note['ccw'] == previous['ccw']:
                        roles = (active, trailing, pivot)
                    else:
                        roles = (active, pivot, trailing)
            else:
                roles = (i & 1, (i & 1) ^ 1, 2)
            pivot, active, trailing = roles
            hold_styles.append(int(note.get('hold_length', -1) > 0)
                               | pivot << 1 | active << 3 | trailing << 5)
            previous = note
    lines+=['neo_hold_starts: .word '+','.join(map(str,hold_starts)),'neo_hold_styles:']
    lines+=['.byte '+','.join(map(str,hold_styles[i:i+32])) for i in range(0,len(hold_styles),32)]
    free_records=[];free_starts=[];free_counts=[];free_phases=[];free_cells=[];coins=[];hazards=[];routes=[];lasers=[];deaths=[]
    for level in levels:
        chart=json.loads((out/f'level{level}.json').read_text())
        regions=chart.get('freeroam_regions',[])
        free_starts.append(len(free_records)*64);free_counts.append(len(regions))
        for r in regions:
            n=chart['notes'][r['step']];following=chart['notes'][r['step']+1]
            offset=len(free_phases)*2
            free_phases.extend(round(easing(r['ease'],i/r['return_duration'])*256) for i in range(r['return_duration']+1))
            rate=abs(n['rate'])*(-1 if following['ccw'] else 1)
            free_records.append((r['step'],r['start'],r['return_start'],r['return_duration'],r['unlock'],r['end'],*r['bounds'],
                                 following['x']-n['x']+r['exit_offset'][0],following['y']-n['y']+r['exit_offset'][1],offset,
                                 (following['angle']+128)&255,rate,int(r['move_camera']),len(free_cells)*2,len(r['cells']),
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
    lines+=['neo_free_starts: .word '+','.join(map(str,free_starts)),
            'neo_free_counts: .word '+','.join(map(str,free_counts)), 'neo_free_records:']
    lines+=['.word '+','.join(str(v&65535) for v in row) for row in free_records]
    lines+=['neo_free_phases:']
    lines+=['.word '+','.join(map(str,free_phases[i:i+16])) for i in range(0,len(free_phases),16)]
    lines+=['neo_free_cells:']
    lines+=['.word '+','.join(str(v&65535) for v in free_cells[i:i+16]) for i in range(0,len(free_cells),16)]
    lines+=['neo_free_coins:']
    lines+=['.word '+','.join(str(v&65535) for v in coins[i:i+16]) for i in range(0,len(coins),16)]
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
    from neo_math import table_source as math_tables
    return '\n'.join(lines)+'\n'+math_tables(out,levels)


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
