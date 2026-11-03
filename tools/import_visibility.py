"""Read original per-floor appearance, disappearance, and opacity triggers."""
import json,sys
from pathlib import Path
import UnityPy
from UnityPy.helpers.TypeTreeGenerator import TypeTreeGenerator
from UnityPy.files.ObjectReader import get_typetree_node
from import_campaign import DEFAULT_GAME,SCENES
from official_catalog import WORLDS
ROOT=Path(__file__).resolve().parents[1]

def native(game,scene):
    env=UnityPy.load(str(game/f'A Dance of Fire and Ice_Data/level{scene}'))
    gen=TypeTreeGenerator(env.objects[0].assets_file.unity_version);gen.load_local_game(str(game));env.typetree_generator=gen
    floors={};effects=[];initial={};hidden={}
    for o in env.objects:
        if o.type.name!='MonoBehaviour':continue
        b=o.read_typetree(nodes=get_typetree_node(114,o.version),wrap=True,check_read=False)
        cls=b.m_Script.deref().read().m_ClassName
        if cls not in ('scrFloor','ffxChangeTrack','ffxFloorAppearPlus','ffxFloorDisappearPlus','ffxMoveFloorPlus','ffxRecolorFloorPlus'):continue
        d=o.read_typetree()
        if cls=='scrFloor':
            floors[d['m_GameObject']['m_PathID']]=d['seqID']
            initial[d['seqID']]=d.get('opacityVal',1)
            hidden[d['seqID']]=bool(d.get('hideIcon',False) or d.get('floorIcon')==18)
        elif d.get('m_Enabled',1):effects.append(dict(type=cls,**d))
    return [dict(d,floor=floors[d['m_GameObject']['m_PathID']]) for d in effects if d['m_GameObject']['m_PathID'] in floors],[initial[i] for i in range(len(initial))],[hidden[i] for i in range(len(initial))]

def main():
    game=Path(DEFAULT_GAME)
    for meta in WORLDS:
        path=ROOT/f'assets/private/level{meta["id"]}.json'
        if not path.exists():continue
        data=json.loads(path.read_text())
        if meta.get('text'):
            source=json.loads((ROOT/f'build/catalog/text-{meta["text"]}.json').read_text(encoding='utf-8'))
            data['track_settings']=source['settings']
            data['track_actions']=[a for a in source.get('actions',[]) if a['eventType'] in ('AnimateTrack','MoveTrack','PositionTrack','RepeatEvents','Hide','ColorTrack','RecolorTrack','ChangeTrack','SetConditionalEvents')]
            hides={a['floor']:a['hideTileIcon'] for a in source.get('actions',[]) if a['eventType']=='Hide' and a.get('active',True) and 'hideTileIcon' in a}
            hidden=False;data['hidden_icons']=[]
            for i in range(len(data['floors'])):
                if i in hides:
                    v=hides[i];hidden=v.lower() in ('enabled','true','yes','on','1') if isinstance(v,str) else bool(v)
                data['hidden_icons'].append(hidden)
        else:
            scene=SCENES.get(meta['id'],meta.get('scene'))
            effects,initial,hidden=native(game,scene) if scene else ([],[1]*len(data['floors']),[False]*len(data['floors']))
            data['native_track_effects']=effects;data['native_track_initial']=initial;data['hidden_icons']=hidden
        path.write_text(json.dumps(data,indent=2),encoding='utf-8')
        print(meta['code'],len(data.get('native_track_effects',data.get('track_actions',[]))),'track effects',flush=True)

if __name__=='__main__':main()
