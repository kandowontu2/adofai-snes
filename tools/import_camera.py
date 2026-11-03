"""Read original camera zoom settings and events, without altering the game."""
import json
from pathlib import Path
import UnityPy
from UnityPy.helpers.TypeTreeGenerator import TypeTreeGenerator
from UnityPy.files.ObjectReader import get_typetree_node
from import_campaign import DEFAULT_GAME,SCENES
from official_catalog import WORLDS,load_game_json
ROOT=Path(__file__).resolve().parents[1]

def native(game,scene):
    env=UnityPy.load(str(game/f'A Dance of Fire and Ice_Data/level{scene}'))
    gen=TypeTreeGenerator(env.objects[0].assets_file.unity_version);gen.load_local_game(str(game));env.typetree_generator=gen
    floors={};effects=[];initial=1.
    for o in env.objects:
        if o.type.name!='MonoBehaviour':continue
        b=o.read_typetree(nodes=get_typetree_node(114,o.version),wrap=True,check_read=False)
        cls=b.m_Script.deref().read().m_ClassName
        if cls not in ('scrFloor','scrCamera','ffxCameraPlus'):continue
        d=o.read_typetree()
        if cls=='scrFloor':floors[d['m_GameObject']['m_PathID']]=d['seqID']
        elif cls=='scrCamera':initial=d.get('zoomSize',1.)
        elif d.get('m_Enabled',1):effects.append(d)
    return initial,[dict(d,floor=floors[d['m_GameObject']['m_PathID']]) for d in effects if d['m_GameObject']['m_PathID'] in floors]

def main():
    game=Path(DEFAULT_GAME);catalog={m['id']:m for m in WORLDS}
    for n in range(1,62):
        path=ROOT/f'assets/private/level{n}.json';data=json.loads(path.read_text())
        if n>=40:raw=load_game_json(Path(data['source']).read_text(encoding='utf-8-sig'))
        elif catalog[n].get('text'):raw=load_game_json((ROOT/f'build/catalog/text-{catalog[n]["text"]}.json').read_text(encoding='utf-8-sig'))
        else:raw=None
        if raw is not None:
            data['camera_initial']=raw['settings'].get('zoom',100)/100
            data['camera_rotation_initial']=raw['settings'].get('rotation',0)
            data['camera_actions']=[a for a in raw.get('actions',[]) if a['eventType'] in ('MoveCamera','RepeatEvents','SetConditionalEvents')]
            data['native_camera_effects']=[]
        else:
            scene=SCENES.get(n,catalog[n].get('scene'))
            initial,effects=native(game,scene) if scene else (1.,[])
            data['camera_initial']=initial;data['native_camera_effects']=effects;data['camera_actions']=[]
        path.write_text(json.dumps(data,indent=2),encoding='utf-8')
        print(data.get('code',str(n)),data['camera_initial'],len(data['camera_actions']),len(data['native_camera_effects']),flush=True)

if __name__=='__main__':main()
