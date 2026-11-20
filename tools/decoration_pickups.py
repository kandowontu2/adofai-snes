"""Compile Collect N's authored pickups and counter conditions.

The source implements counters using colliders attached to the planets. Store
the equivalent bounded counters directly; do not run conditional pickup tweens
on the song clock or decide which objects the player collected offline.
"""
import re
import json
from pathlib import Path


def configure(data, chart):
    from track_motion import motion_schedule
    motion_schedule(data, chart)
    decorations=data.get('featured_decorations',[])
    origin=chart['notes'][0]
    hidden=set()
    for stage,region in enumerate(chart['freeroam_regions'],1):
        root=chart['notes'][region['step']]
        dx,dy=root.get('position_track_offset',(0,0))
        points=[];types=[];tags=[]
        for dec in decorations:
            if dec.get('hitbox')!='Event' or dec.get('relativeTo')!='Global':continue
            match=next((re.fullmatch(r'(coin|star|heart)'+str(stage)+r'_(\d+)',t)
                        for t in dec.get('hitboxEventTag','').split()
                        if re.fullmatch(r'(coin|star|heart)'+str(stage)+r'_(\d+)',t)),None)
            if not match:continue
            kind,index=match.groups()
            points.append([round(origin['x']+24*dec['position'][0]-root['x']-dx),
                           round(origin['y']-24*dec['position'][1]-root['y']-dy)])
            types.append(('coin','star','heart').index(kind))
            tags.append(kind+str(stage)+'_'+index)
        assert len(points)<=32,('Pickup mask capacity',stage,len(points))
        modes=[0]*4;targets=[0]*4
        for dec in decorations:
            tag=dec.get('tag','');event=dec.get('hitboxEventTag','').split()
            counter=next((kind for kind in ('coin','star','heart','pickup')
                          if kind+'counter'+str(stage) in tag.split()),None)
            if counter is None:continue
            axis=('coin','star','heart','pickup').index(counter)
            if 'nokill_'+str(stage) in event:
                modes[axis]=2;targets[axis]=round(dec['position'][1]/2)
            elif 'kill_'+str(stage) in event and dec.get('decorationImage')=='killtrigger.png':
                # A lone forbidden state, unlike the upper bound beside an
                # explicit correct state. Never replace an equality rule.
                if not modes[axis]:modes[axis]=3;targets[axis]=round(dec['position'][1]/2)
        region.update(coins=points,coin_types=types,coin_tags=tags,
                      coin_modes=modes,coin_targets=targets,coin_check=region['return_start'],
                      pickup_lives=3)
        region['pickup_ui']=1
        if stage==11:
            # Correct answers enable the next collider in the original.
            # Future answers remain guarded until their question is active.
            answers=[];wrong=[]
            for dec in decorations:
                event=dec.get('hitboxEventTag','')
                if dec.get('relativeTo')!='Global':continue
                p=[round(origin['x']+24*dec['position'][0]-root['x']-dx),
                   round(origin['y']-24*dec['position'][1]-root['y']-dy)]
                match=re.fullmatch(r'q(1[1-5])s',event)
                if match:answers.append((int(match[1]),p))
                elif event=='q15w':wrong.append(p)
            answers.sort()
            assert [q for q,p in answers]==list(range(11,16))
            region.update(coins=[p for q,p in answers]+wrong,
                          coin_types=[4]*5+[5]*len(wrong),
                          coin_modes=[2,0,0,0],coin_targets=[5,0,0,0],
                          coin_required=5,pickup_lives=0,pickup_ui=2,
                          question_texts=json.loads((Path(__file__).resolve().parents[1]/
                              'assets/gameplay/collect-n-questions.json').read_text())['questions'])
            hidden.update('q'+str(q) for q in range(11,16))
        hidden.update(tags)
    # Native sprites own collection visibility; the snapshot layer retains
    # the instructions and scenery, but never a second, uncollectible coin.
    chart['decoration_background_tags']=sorted(hidden)
    hidden.update(tag for dec in decorations if dec.get('decorationImage') in ('chalkcounter.png','chalkcounterfull.png')
                  for tag in dec.get('tag','').split())
    chart['decoration_background_tags']=sorted(hidden)
    chart['decoration_required_images']=sorted({
        dec.get('decorationImage','') for dec in decorations
        if re.fullmatch(r'(?:axis|simple(?:origin|neg[123]i?|[123]i?|i|negi))\.png',
                        dec.get('decorationImage',''))})
    from pickup_routes import route
    for region in chart['freeroam_regions']:
        region['demo_route']=route(region,chart['notes'][region['step']])


def accepts(region, counts):
    values=[*counts,sum(counts)]
    return all(mode==0 or mode==1 and value>=target or mode==2 and value==target
               or mode==3 and value!=target
               for mode,target,value in zip(region['coin_modes'],region['coin_targets'],values))
