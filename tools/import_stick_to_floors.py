"""Import native per-floor planet sticking without changing visual events."""
import json
from pathlib import Path
import UnityPy
from UnityPy.helpers.TypeTreeGenerator import TypeTreeGenerator
from UnityPy.files.ObjectReader import get_typetree_node
from import_campaign import DEFAULT_GAME,SCENES
from official_catalog import WORLDS
ROOT=Path(__file__).resolve().parents[1]

def main():
    for meta in WORLDS:
        if meta.get('text'):continue
        scene=SCENES.get(meta['id'],meta.get('scene'))
        if scene is None:continue
        game=Path(DEFAULT_GAME)
        env=UnityPy.load(str(game/f'A Dance of Fire and Ice_Data/level{scene}'))
        gen=TypeTreeGenerator(env.objects[0].assets_file.unity_version);gen.load_local_game(str(game));env.typetree_generator=gen
        floors={}
        for o in env.objects:
            if o.type.name!='MonoBehaviour':continue
            b=o.read_typetree(nodes=get_typetree_node(114,o.version),wrap=True,check_read=False)
            if b.m_Script.deref().read().m_ClassName!='scrFloor':continue
            d=o.read_typetree();floors[d['seqID']]=bool(d.get('stickToFloor',False))
        path=ROOT/f'assets/private/level{meta["id"]}.json';data=json.loads(path.read_text())
        data['native_stick_to_floors']=[floors[i] for i in range(len(data['floors']))]
        path.write_text(json.dumps(data,indent=2),encoding='utf-8')
        print(meta['code'],sum(floors.values()),'sticky floors',flush=True)

if __name__=='__main__':main()
