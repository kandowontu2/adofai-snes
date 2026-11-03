"""Read default and per-floor hit sounds without modifying imported charts."""
import argparse,json,re
from pathlib import Path
import UnityPy
from UnityPy.helpers.TypeTreeGenerator import TypeTreeGenerator
from UnityPy.files.ObjectReader import get_typetree_node
from import_campaign import DEFAULT_GAME,SCENES
from official_catalog import WORLDS,load_game_json

ROOT=Path(__file__).resolve().parents[1]
SOUNDS=['Hat','Kick','Shaker','Sizzle','Chuck','ShakerLoud','None','Hammer','KickChroma',
        'SnareAcoustic2','Sidestick','Stick','ReverbClack','Squareshot','PowerDown','PowerUp',
        'KickHouse','KickRupture','HatHouse','SnareHouse','SnareVapor','ClapHit','ClapHitEcho',
        'ReverbClap','FireTile','IceTile','VehiclePositive','VehicleNegative']

def native(scene):
    game=Path(DEFAULT_GAME);env=UnityPy.load(str(game/f'A Dance of Fire and Ice_Data/level{scene}'))
    gen=TypeTreeGenerator(env.objects[0].assets_file.unity_version);gen.load_local_game(str(game));env.typetree_generator=gen
    floors={};effects=[];conductor=None
    for obj in env.objects:
        if obj.type.name!='MonoBehaviour':continue
        base=obj.read_typetree(nodes=get_typetree_node(114,obj.version),wrap=True,check_read=False)
        cls=base.m_Script.deref().read().m_ClassName
        if cls not in ('scrFloor','scrConductor','ffxSetHitsound'):continue
        data=obj.read_typetree()
        if cls=='scrFloor':floors[data['m_GameObject']['m_PathID']]=data['seqID']
        elif cls=='scrConductor':conductor=data
        elif data.get('m_Enabled',1):effects.append(data)
    assert conductor is not None,scene
    events=[dict(floor=floors[e['m_GameObject']['m_PathID']],gameSound='Midspin' if e['gameSound']==1 else 'Hitsound',
                 hitsound=SOUNDS[e['hitSound']],hitsoundVolume=e['volume']*100) for e in effects]
    return dict(hitsound=SOUNDS[conductor['hitSound']],hitsoundVolume=conductor['hitSoundVolume']*100,
                countdownSpeedMultiplier=conductor.get('countdownSpeedMultiplier',1),events=events)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--levels',type=int,nargs='+',choices=range(1,62),default=list(range(1,62)))
    args=ap.parse_args()
    rows={}
    for n in args.levels:
        data=json.loads((ROOT/f'assets/private/level{n}.json').read_text());raw=None
        if n<=39:
            meta=WORLDS[n-1]
            if meta.get('text'):raw=json.loads((ROOT/f'build/catalog/text-{meta["text"]}.json').read_text(encoding='utf8'))
            elif n in SCENES or meta.get('scene') is not None:rows[str(n)]=native(SCENES.get(n,meta.get('scene')))
            else:
                # The two JSON-authored main worlds identify their source asset.
                song=data['source'].removeprefix('Native JSON ')
                for path in (ROOT/'build/catalog').glob('text-*.json'):
                    candidate=json.loads(path.read_text(encoding='utf8'))
                    if isinstance(candidate,dict) and candidate.get('settings',{}).get('song')==song:
                        raw=candidate;break
                assert raw is not None,(n,song)
        else:raw=load_game_json(Path(data['source']).read_text(encoding='utf-8-sig'))
        if raw:
            s=raw['settings'];rows[str(n)]=dict(hitsound=s.get('hitsound','Kick'),hitsoundVolume=s.get('hitsoundVolume',100),
                countdownSpeedMultiplier=s.get('countdownSpeedMultiplier',1),
                events=[a for a in raw.get('actions',[]) if a['eventType']=='SetHitsound' and a.get('active',True)])
        print(n,rows[str(n)]['hitsound'],len(rows[str(n)]['events']),flush=True)
    path=ROOT/'assets/private/hitsound-levels.json'
    if path.exists():
        previous=json.loads(path.read_text())
        rows={**previous,**rows}
    path.write_text(json.dumps(rows,indent=2))

if __name__=='__main__':main()
