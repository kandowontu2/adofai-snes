"""Inventory official local charts without modifying the game installation."""
import argparse,hashlib,json
from collections import Counter
from pathlib import Path
import UnityPy
from UnityPy.helpers.TypeTreeGenerator import TypeTreeGenerator
from UnityPy.files.ObjectReader import get_typetree_node
from import_campaign import DEFAULT_GAME,native_checkpoints
ROOT=Path(__file__).resolve().parents[1]

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--game',type=Path,default=Path(DEFAULT_GAME));args=ap.parse_args()
    game=args.game;data=game/'A Dance of Fire and Ice_Data'
    out=ROOT/'build/catalog';out.mkdir(exist_ok=True,parents=True)
    rows=[]
    env=UnityPy.load(str(data/'resources.assets'))
    for o in env.objects:
        if o.type.name!='TextAsset':continue
        t=o.read()
        try:j=json.loads(t.m_Script)
        except Exception:continue
        if not isinstance(j,dict) or not ('angleData' in j or 'pathData' in j):continue
        name=f'text-{o.path_id}'
        (out/f'{name}.json').write_text(json.dumps(j,indent=2),encoding='utf8')
        rows.append(dict(source=name,name=t.m_Name,settings=j.get('settings',{}),steps=len(j.get('angleData',j.get('pathData',[]))),
                         events=dict(Counter(a['eventType'] for a in j.get('actions',[])))))
    (out/'text-catalog.json').write_text(json.dumps(rows,indent=2))
    print('TEXT CHARTS',[(r['source'],r['name'],r['settings'].get('song'),r['steps']) for r in rows],flush=True)
    for scene in [12]+list(range(16,30)):
        env=UnityPy.load(str(data/f'level{scene}'))
        gen=TypeTreeGenerator(env.objects[0].assets_file.unity_version);gen.load_local_game(str(game));env.typetree_generator=gen
        classes=Counter();floors=[];conductors=[];makers=[]
        for o in env.objects:
            if o.type.name!='MonoBehaviour':continue
            b=o.read_typetree(nodes=get_typetree_node(114,o.version),wrap=True,check_read=False)
            cls=b.m_Script.deref().read().m_ClassName;classes[cls]+=1
            if cls=='scrFloor':floors.append(o.read_typetree())
            if cls=='scrConductor':conductors.append(o.read_typetree())
            if cls=='scrLevelMaker':makers.append(o.read_typetree())
        floors.sort(key=lambda f:f['seqID'])
        info=dict(scene=scene,floors=floors,conductors=conductors,makers=makers,classes=dict(classes),checkpoints=native_checkpoints(env))
        (out/f'scene-{scene}.json').write_text(json.dumps(info,indent=2))
        special={k:dict(Counter(str(f.get(k)) for f in floors)) for k in ('speed','isCCW','midSpin','extraBeats','numPlanets','holdLength','isFake','isAuto','isLandable')}
        print('SCENE',scene,'floor count',len(floors),'timing',[{k:c.get(k) for k in ('bpm','addoffset','separateCountdownTime','countdownTicks')} for c in conductors],special,flush=True)
        print('EFFECTS',[(k,v) for k,v in classes.items() if k.startswith('ffx')],flush=True)
    (out/'source.json').write_text(json.dumps(dict(path=str(game.resolve()),build_sha256=hashlib.sha256((data/'globalgamemanagers').read_bytes()).hexdigest()),indent=2))

if __name__=='__main__':main()
