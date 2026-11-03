"""Import color/style events from the user's installed official charts."""
import argparse,json
from pathlib import Path
import UnityPy
from UnityPy.helpers.TypeTreeGenerator import TypeTreeGenerator
from UnityPy.files.ObjectReader import get_typetree_node
from import_campaign import DEFAULT_GAME,SCENES
from official_catalog import WORLDS,load_game_json
from import_tech import TECH
ROOT=Path(__file__).resolve().parents[1]

def native(game,scene,count):
    env=UnityPy.load(str(game/f'A Dance of Fire and Ice_Data/level{scene}'))
    gen=TypeTreeGenerator(env.objects[0].assets_file.unity_version);gen.load_local_game(str(game));env.typetree_generator=gen
    floors={};effects=[];renderers={};styles={};glows={};meshes=[]
    for o in env.objects:
        if o.type.name=='SpriteRenderer':
            d=o.read_typetree();renderers[d['m_GameObject']['m_PathID']]=d['m_Color']
        elif o.type.name=='MeshRenderer':meshes.append(o)
        elif o.type.name=='MonoBehaviour':
            b=o.read_typetree(nodes=get_typetree_node(114,o.version),wrap=True,check_read=False)
            cls=b.m_Script.deref().read().m_ClassName
            if cls not in ('scrFloor','ffxRecolorFloorPlus'):continue
            d=o.read_typetree();go=d['m_GameObject']['m_PathID']
            if cls=='scrFloor':
                floors[go]=d['seqID'];styles[go]=d.get('initialTrackStyle',0)
                glows[go]=dict(glow=d.get('glowMultiplier',1),disableGlow=d.get('disableGlow',False))
            elif d.get('m_Enabled',1):effects.append(dict(type=cls,**d))
    materials={}
    for o in meshes:
        d=o.read_typetree();go=d['m_GameObject']['m_PathID']
        if go not in floors or not d['m_Materials']:continue
        ref=d['m_Materials'][0];key=(ref['m_FileID'],ref['m_PathID'])
        if key not in materials:
            material=o.read().m_Materials[0].deref().read_typetree()
            materials[key]=dict(material['m_SavedProperties']['m_Colors']).get('_Color','a7c2da')
        renderers[go]=materials[key]
    initial=[dict(color='a7c2da',style='Standard') for _ in range(count)]
    for go,i in floors.items():
        if 0<=i<count:initial[i]=dict(color=renderers.get(go,'a7c2da'),style=styles[go],**glows[go])
    return initial,[dict(e,floor=floors[e['m_GameObject']['m_PathID']]) for e in effects if e['m_GameObject']['m_PathID'] in floors]

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--levels',type=int,nargs='+');args=ap.parse_args()
    for meta in WORLDS+TECH:
        if args.levels and meta['id'] not in args.levels:continue
        path=ROOT/f'assets/private/level{meta["id"]}.json'
        if not path.exists():continue
        data=json.loads(path.read_text())
        if meta.get('text') or meta['id']>=40:
            source=Path(data['source']) if meta['id']>=40 else ROOT/f'build/catalog/text-{meta["text"]}.json'
            raw=load_game_json(source.read_text(encoding='utf-8-sig'))
            data['track_settings']=raw['settings']
            data['track_actions']=[a for a in raw['actions'] if a['eventType'] in ('AnimateTrack','MoveTrack','PositionTrack','RepeatEvents','Hide','ColorTrack','RecolorTrack','ChangeTrack','SetConditionalEvents')]
        else:
            scene=SCENES.get(meta['id'],meta.get('scene'))
            if scene:
                initial,effects=native(Path(DEFAULT_GAME),scene,len(data['floors']))
                data['native_track_colors']=initial
                data['native_track_effects']=[e for e in data.get('native_track_effects',[]) if e['type']!='ffxRecolorFloorPlus']+effects
                # Legacy Color.clear means "use this floor's material", not
                # an authored black tile (scnGame.InitFloorsNative).
                for e in data['native_track_effects']:
                    if e['type']!='ffxChangeTrack':continue
                    for key in ('color1','color2'):
                        value=e.get(key,{})
                        if isinstance(value,dict) and all(value.get(k,0)==0 for k in ('r','g','b','a')):
                            e[key]=initial[e['floor']]['color']
        data['track_color_import']=1
        path.write_text(json.dumps(data,indent=2),encoding='utf-8')
        print(meta['code'],'colors imported',flush=True)

if __name__=='__main__':main()
