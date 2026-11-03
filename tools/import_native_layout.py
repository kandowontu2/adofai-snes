"""Preserve authored native floor positions and component timing units."""
import argparse,json
from pathlib import Path
import numpy as np
import UnityPy
from UnityPy.helpers.TypeTreeGenerator import TypeTreeGenerator
from UnityPy.files.ObjectReader import get_typetree_node
from scipy.spatial.transform import Rotation
from import_campaign import DEFAULT_GAME,SCENES
from official_catalog import WORLDS
ROOT=Path(__file__).resolve().parents[1]

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--levels',type=int,nargs='+');args=ap.parse_args()
    game=Path(DEFAULT_GAME)
    for meta in WORLDS:
        if args.levels and meta['id'] not in args.levels:continue
        if meta.get('text'):continue
        scene=SCENES.get(meta['id'],meta.get('scene'))
        if scene is None:continue
        env=UnityPy.load(str(game/f'A Dance of Fire and Ice_Data/level{scene}'))
        gen=TypeTreeGenerator(env.objects[0].assets_file.unity_version);gen.load_local_game(str(game));env.typetree_generator=gen
        transforms={};by_object={};floors={};controller=None
        for obj in env.objects:
            if obj.type.name=='Transform':
                t=obj.read_typetree();transforms[obj.path_id]=t;by_object[t['m_GameObject']['m_PathID']]=obj.path_id
            if obj.type.name!='MonoBehaviour':continue
            base=obj.read_typetree(nodes=get_typetree_node(114,obj.version),wrap=True,check_read=False)
            cls=base.m_Script.deref().read().m_ClassName
            if cls=='scrFloor':
                d=obj.read_typetree();floors[d['seqID']]=d['m_GameObject']['m_PathID']
            elif cls=='scrController':controller=obj.read_typetree()
        cache={}
        def world(i):
            if not i:return np.eye(4)
            if i not in cache:
                t=transforms[i];m=np.eye(4);q=t['m_LocalRotation'];s=t['m_LocalScale'];p=t['m_LocalPosition']
                m[:3,:3]=Rotation.from_quat([q[k] for k in 'xyzw']).as_matrix()@np.diag([s[k] for k in 'xyz'])
                m[:3,3]=[p[k] for k in 'xyz'];cache[i]=world(t['m_Father']['m_PathID'])@m
            return cache[i]
        assert controller is not None
        path=ROOT/f'assets/private/level{meta["id"]}.json';data=json.loads(path.read_text())
        data['native_tile_size']=controller.get('tileSize',1.5)
        data['native_component_notation']=controller.get('useComponentNotationForFx',True)
        data['native_positions']=[world(by_object[floors[i]])[:2,3].tolist() for i in range(len(data['floors']))]
        # scrFloor.Start overrides serialized per-floor values in native worlds.
        data['native_controller_stick_to_floor']=bool(controller.get('stickToFloor',False))
        data['native_layout_version']=2
        path.write_text(json.dumps(data,indent=2))
        print(meta['id'],data['native_tile_size'],data['native_component_notation'],data['native_positions'][:3],flush=True)

if __name__=='__main__':main()
