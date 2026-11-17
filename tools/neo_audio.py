"""Sample-clock hold sounds from scrConductor's native schedule."""


def hold_events(data, notes):
    config = dict(data['native_holdsound'])
    changes = {e['floor']: e for e in data.get('native_effects', []) if e['type'] == 'ffxSetHoldsound'}
    result = []
    for i, note in enumerate(notes[1:-1], 1):
        if i in changes:
            e = changes[i]
            config.update({k: v for k, v in e.items() if k.startswith('hold')})
            config['holdSoundVolume'] = e['volume']
        if note.get('hold_length', -1) < 0 or note['flags'] & 16:
            continue
        start, end = note['time'], notes[i+1]['time']
        volume = config.get('holdSoundVolume', 1.)
        def emit(sound, time, until=None):
            result.append(dict(note=i, sound=sound, time=time, end=until, volume=volume))
        if config.get('holdStartSound', 1) == 0:
            emit('HeldbeatStartFuse', start)
        if config.get('holdLoopSound', 1) == 0:
            emit('HeldbeatLoopFuse', start, end)
        if config.get('holdEndSound', 1) == 0:
            # The sample's main transient is 101 ms into the recording.
            emit('HeldbeatEndFuse', end - .101)
        mid = config.get('holdMidSound', 2)
        if mid < 2:
            name, lead = ('Fuse', .107) if mid == 0 else ('SingSing', .212)
            delay = config.get('holdMidSoundDelay', .5)
            if delay <= 0:
                continue
            once = config.get('holdMidSoundType', 0) == 0
            at_start = config.get('holdMidSoundTiming', 1) == 0
            at = start+delay if at_start else end-delay
            while start < at < end:
                emit('HeldbeatMid'+name, at-lead)
                if once:
                    break
                at += delay if at_start else -delay
    result.extend(track_cues(data,notes))
    result.extend(planet_cues(data,notes))
    result.extend(play_sound_events(data,notes))
    return sorted(result, key=lambda e: e['time'])


def track_cues(data,notes):
    """Authored floor countdowns and free-roam half-beat accompaniment."""
    from import_hitsounds import SOUNDS
    result=[];volume=data.get('native_hit_volume',1.)
    changes={e['floor']:e for e in data.get('native_effects',[]) if e['type']=='ffxSetHitsound'}
    multiplier=data.get('native_countdown_multiplier',1.)
    for i,floor in enumerate(data.get('floors',[])[:-1]):
        if i in changes:volume=changes[i]['volume']
        beat=60/data['bpm']/floor['speed']
        ticks=floor.get('countdownTicks',0)
        for j in range(ticks):
            result.append(dict(note=i,sound='Hat',time=notes[i+1]['time']-(ticks-j)*beat/multiplier,end=None,volume=volume))
        if not floor.get('freeroam'):continue
        half=0
        while half*.5<floor['extraBeats']-ticks/multiplier+1:
            sound=SOUNDS[floor['freeroamSoundOffBeat' if half%2 else 'freeroamSoundOnBeat']]
            if sound!='None':result.append(dict(note=i,sound=sound,time=notes[i]['time']+half*.5*beat,end=None,volume=volume*(.7 if half%2 else .8)))
            half+=1
    return result


def suppress_regular_hit(notes, i):
    return (notes[i].get('hold_length', -1) >= 0 or notes[i-1].get('hold_length', -1) >= 0
            or (i >= 2 and notes[i-1]['flags'] & 16 and notes[i-2].get('hold_length', -1) >= 0))


def planet_cues(data,notes):
    """scrConductor's insertion/removal chime, including its hold exclusion."""
    from track_motion import enabled
    changes={e['floor']:e['volume'] for e in data.get('native_effects',[]) if e['type']=='ffxSetHitsound'}
    for e in data.get('featured_actions',[]):
        if e['eventType']=='SetHitsound' and enabled(e.get('active',True)):
            changes[e['floor']]=e.get('hitsoundVolume',100)/100
    result=[];volume=data.get('native_hit_volume',1.)
    for i,note in enumerate(notes[1:],1):
        volume=changes.get(i,volume)
        if suppress_regular_hit(notes,i):continue
        previous=notes[i-1].get('planets',2);current=note.get('planets',2)
        if previous==current:continue
        result.append(dict(note=i,sound='VehiclePositive' if current>previous else 'VehicleNegative',
                           time=note['time'],end=None,volume=volume*.6))
    return result


def play_sound_events(data,notes):
    """Native ffxPlaySound timing, sample lead, pitch and optional stop time."""
    import json
    from pathlib import Path
    from import_hitsounds import SOUNDS
    from track_motion import enabled
    offsets=json.loads((Path(__file__).resolve().parents[1]/'assets/audio/hit-sound-offsets.json').read_text())
    result=[]
    for event in data.get('featured_actions',[]):
        if event['eventType']!='PlaySound' or not enabled(event.get('active',True)):continue
        sound=event['hitsound'];volume=event.get('hitsoundVolume',100)/100
        if sound=='None' or volume<=0:continue
        if sound not in SOUNDS:raise ValueError(('External PlaySound sample requires importing',sound))
        i=event['floor'];note=notes[i]
        at=note['time']+event.get('angleOffset',0)/180*60/data['bpm']/note['speed']-event.get('offset',0)/1000
        duration=event.get('playDuration',0)/1000
        result.append(dict(note=i,sound=sound,time=at-offsets.get(sound,0),end=at+duration if duration>0 else None,
                           volume=volume,pitch=event.get('pitch',100),loop=False))
    return result
