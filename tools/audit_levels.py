"""Read-only discovery of local main-level charts and their mechanics."""
import json
from collections import Counter
from pathlib import Path
import UnityPy
from UnityPy.helpers.TypeTreeGenerator import TypeTreeGenerator
from UnityPy.files.ObjectReader import get_typetree_node

game=Path(r'C:\Program Files (x86)\Steam\steamapps\common\A Dance of Fire and Ice')
data=game/'A Dance of Fire and Ice_Data'
out=Path('build/expansion-audit');out.mkdir(parents=True,exist_ok=True)
env=UnityPy.load(str(data/'resources.assets'))
texts=[]
for o in env.objects:
    if o.type.name=='TextAsset':
        d=o.read()
        if d.m_Name=='main':
            try:j=json.loads(d.m_Script)
            except Exception:continue
            if 'angleData' in j or 'pathData' in j:
                info={'id':o.path_id,'settings':j.get('settings',{}),'steps':len(j.get('angleData',[])),
                      'event_types':dict(Counter(x['eventType'] for x in j.get('actions',[])))}
                texts.append(info)
                (out/f'text-{o.path_id}.json').write_text(json.dumps(j,indent=2))
(out/'text-levels.json').write_text(json.dumps(texts,indent=2))
print('TEXT LEVELS',[(x['id'],x['settings'].get('song'),x['settings'].get('artist'),x['steps'],x['event_types']) for x in texts])
for scene in [8,9,10,11,13,14,15]:
    env=UnityPy.load(str(data/f'level{scene}'))
    gen=TypeTreeGenerator(env.objects[0].assets_file.unity_version);gen.load_local_game(str(game));env.typetree_generator=gen
    rows=[];counter=Counter()
    for o in env.objects:
        if o.type.name!='MonoBehaviour':continue
        b=o.read_typetree(nodes=get_typetree_node(114,o.version),wrap=True,check_read=False)
        s=b.m_Script.deref().read();cls=s.m_ClassName;counter[cls]+=1
        if cls in ('scrFloor','scrConductor','ffxSpeed','ffxTwirl','ffxPause','scrLevelMaker'):
            rows.append({'id':o.path_id,'class':cls,'data':o.read_typetree()})
    (out/f'scene-{scene}.json').write_text(json.dumps(rows,indent=2))
    floors=sorted([x['data'] for x in rows if x['class']=='scrFloor'],key=lambda x:x['seqID'])
    c=next(x['data'] for x in rows if x['class']=='scrConductor')
    special={k:dict(Counter(str(f.get(k)) for f in floors)) for k in ('speed','isCCW','midSpin','extraBeats','numPlanets','holdLength')}
    print('SCENE',scene,'floors',len(floors),'conductor',{k:c[k] for k in ('bpm','addoffset','separateCountdownTime','countdownTicks')},'mechanics',special)
    print('classes',[(k,v) for k,v in counter.items() if k.startswith('ffx')])
