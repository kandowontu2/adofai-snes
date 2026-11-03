"""Import the twelve main worlds from the user's local ADOFAI installation."""
import argparse
import os
import json
from pathlib import Path
import UnityPy
from UnityPy.helpers.TypeTreeGenerator import TypeTreeGenerator
from UnityPy.files.ObjectReader import get_typetree_node

DEFAULT_GAME=os.environ.get('ADOFAI_GAME',r'C:\Program Files (x86)\Steam\steamapps\common\A Dance of Fire and Ice')
ROOT=Path(__file__).resolve().parents[1]
TITLES=['A DANCE OF FIRE AND ICE','OFFBEATS','THE WIND-UP','LOVE LETTERS',
        'THE MIDNIGHT TRAIN','PULSE','SPIN 2 WIN','JUNGLE CITY','CLASSIC PURSUIT',
        'BUTTERFLY PLANET','HERACLES','ARTIFICIAL CHARIOT']
SCENES={1:8,2:9,4:10,6:11,7:13,8:14,9:15,10:16,11:17,12:18}
FLOOR_FIELDS=('seqID','entryangle','exitangle','speed','isCCW','extraBeats','midSpin','holdLength','numPlanets')

def native_checkpoints(env):
    """Effects live on the same GameObject as their triggering scrFloor."""
    floor_ids={};effects=[]
    for o in env.objects:
        if o.type.name!='MonoBehaviour':continue
        b=o.read_typetree(nodes=get_typetree_node(114,o.version),wrap=True,check_read=False)
        cls=b.m_Script.deref().read().m_ClassName
        if cls not in ('scrFloor','ffxCheckpoint'):continue
        d=o.read_typetree()
        if cls=='scrFloor':floor_ids[d['m_GameObject']['m_PathID']]=d['seqID']
        elif d.get('m_Enabled',1):effects.append(d)
    return [dict(floor=floor_ids[d['m_GameObject']['m_PathID']],tileOffset=d['checkpointTileOffset']) for d in effects]

def json_checkpoints(level):
    # Duplicate Checkpoint actions on a floor are collapsed by the original.
    result={}
    for a in level.get('actions',[]):
        if a['eventType']=='Checkpoint' and a.get('active',True):
            result.setdefault(a['floor'],dict(floor=a['floor'],tileOffset=a.get('tileOffset',0)))
    return sorted(result.values(),key=lambda c:c['floor'])

def scene_chart(data,game,number):
    env=UnityPy.load(str(data/f'level{SCENES[number]}'))
    gen=TypeTreeGenerator(env.objects[0].assets_file.unity_version)
    gen.load_local_game(str(game));env.typetree_generator=gen
    floors=[];c=None
    for o in env.objects:
        if o.type.name!='MonoBehaviour':continue
        b=o.read_typetree(nodes=get_typetree_node(114,o.version),wrap=True,check_read=False)
        cls=b.m_Script.deref().read().m_ClassName
        if cls=='scrFloor':
            d=o.read_typetree();floors.append({k:d[k] for k in FLOOR_FIELDS})
        elif cls=='scrConductor':c=o.read_typetree()
    floors.sort(key=lambda x:x['seqID'])
    assert floors and [x['seqID'] for x in floors]==list(range(len(floors)))
    return {'id':number,'title':TITLES[number-1],'bpm':c['bpm'],'offset':c['addoffset'],
            'countdown':c['countdownTicks'],'separate_countdown':bool(c['separateCountdownTime']),
            'floors':floors,'checkpoints':native_checkpoints(env),'source':f'Unity scene level{SCENES[number]}'}

def json_chart(level,number):
    import math
    s=level['settings'];angles=level['angleData']
    assert all(a!=999 for a in angles),'Midspin chart needs explicit support'
    assert not any(a['eventType'] in ('SetSpeed','Twirl','Hold','Pause') for a in level['actions'])
    exits=[math.radians(90-a) for a in angles]
    entries=[math.pi*1.5]+[(a+math.pi)%(math.pi*2) for a in exits]
    exits.append(entries[-1]+math.pi)
    floors=[dict(seqID=i,entryangle=entries[i],exitangle=exits[i],speed=1.0,
                 isCCW=0,extraBeats=0.0,midSpin=0,holdLength=-1,numPlanets=2) for i in range(len(entries))]
    return {'id':number,'title':TITLES[number-1],'bpm':s['bpm'],'offset':s['offset']/1000,
            'countdown':s.get('countdownTicks',4),'separate_countdown':s.get('separateCountdownTime',True),
            'floors':floors,'checkpoints':json_checkpoints(level),'source':'Native JSON '+s['song']}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--game',type=Path,default=Path(DEFAULT_GAME))
    ap.add_argument('--levels',type=int,nargs='+',default=list(range(1,13)));args=ap.parse_args()
    data=args.game/'A Dance of Fire and Ice_Data';out=ROOT/'assets/private';out.mkdir(exist_ok=True,parents=True)
    resources=UnityPy.load(str(data/'resources.assets'))
    json_levels={}
    for o in resources.objects:
        if o.type.name=='TextAsset':
            t=o.read()
            if t.m_Name!='main':continue
            try:j=json.loads(t.m_Script)
            except Exception:continue
            song=j.get('settings',{}).get('song','')
            if song=='3-X THE WIND-UP':json_levels[3]=j
            if song=='5-X The Midnight Train':json_levels[5]=j
    for n in args.levels:
        c=json_chart(json_levels[n],n) if n in (3,5) else scene_chart(data,args.game,n)
        (out/f'level{n}.json').write_text(json.dumps(c,indent=2),encoding='utf8')
        print(f'{n}-X: {c["title"]}, {len(c["floors"])-1} steps, {c["bpm"]} BPM',flush=True)
    audio_names={3:'3-X',5:'5-X'}
    for o in resources.objects:
        if o.type.name=='AudioClip':
            c=o.read()
            n=next((n for n,name in audio_names.items() if n in args.levels and name==c.m_Name),None)
            if n is not None:
                (out/f'{n}-X.wav').write_bytes(next(iter(c.samples.values())))
                print('Audio',n,c.m_Name,c.m_Length,flush=True)
    del resources
    for n,asset in {1:1,2:9,4:10,6:11,7:13,8:14,9:15,10:16,11:17,12:18}.items():
        if n not in args.levels:continue
        env=UnityPy.load(str(data/f'sharedassets{asset}.assets'))
        for o in env.objects:
            if o.type.name=='AudioClip':
                c=o.read()
                if c.m_Name==f'{n}-X':
                    (out/f'{n}-X.wav').write_bytes(next(iter(c.samples.values())))
                    print('Audio',n,c.m_Name,c.m_Length,flush=True);break
        else:raise RuntimeError(f'Missing song {n}-X')
    for n in args.levels:assert (out/f'{n}-X.wav').exists()
    print('Import complete. The installed game was not changed.')

if __name__=='__main__':main()
