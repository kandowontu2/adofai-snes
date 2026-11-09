"""Read-only import of every additional base-game official world."""
import argparse,hashlib,json,math,subprocess,sys
from pathlib import Path
from collections import defaultdict
import UnityPy
from official_catalog import WORLDS,load_game_json
from import_campaign import DEFAULT_GAME,FLOOR_FIELDS,json_checkpoints
ROOT=Path(__file__).resolve().parents[1]

def normalize_json(d,meta):
    settings=d['settings'];angles=d.get('angleData');floors=[];entry=math.pi*1.5
    if angles is None:
        keys='RpJEToUqGQHWLxNZFVDYBCMA'
        # FloorHelper.MigratePathData, including legacy relative polygon steps.
        # The original migration uses 52 degrees for '7', not an exact seventh.
        relative={'5':72,'6':-72,'7':52,'8':-52,'9':-30,'h':120,'j':-120,'t':60,'y':300}
        angles=[];previous=0
        for c in d['pathData']:
            a=999 if c=='!' else previous+relative[c] if c in relative else keys.index(c)*15
            angles.append(a);previous=a
    for i,a in enumerate(angles):
        exit=entry if a==999 else math.radians(90-a)
        floors.append(dict(seqID=i,entryangle=entry,exitangle=exit,midSpin=int(a==999),
                           speed=1.0,isCCW=0,extraBeats=0.0,holdLength=-1,numPlanets=2,auto=0))
        entry=(exit+math.pi)%(math.pi*2)
    floors.append(dict(seqID=len(angles),entryangle=entry,exitangle=entry+math.pi,midSpin=0,
                       speed=1.0,isCCW=0,extraBeats=0.0,holdLength=-1,numPlanets=2,auto=0))
    events=defaultdict(list)
    for a in d.get('actions',[]):
        if a.get('active',True):events[a['floor']].append(a)
    speed=1.0;ccw=False;auto=False;planets=2;margin=100;bpm=settings['bpm']
    for i,f in enumerate(floors):
        f['auto']=int(auto)
        changes=[a for a in events[i] if a['eventType']=='SetSpeed']
        for a in events[i]:
            kind=a['eventType']
            if kind=='Twirl':ccw=not ccw
            elif kind=='Pause':f['extraBeats']+=a['duration']
            elif kind=='Hold':assert a['duration']<=0,'Active hold requires explicit support'
            elif kind=='Multitap':f['tapsNeeded']=int(a['taps'])
            elif kind=='MultiPlanet':
                planets={'TwoPlanets':2,'ThreePlanets':3}[a['planets']]
                if i and floors[i-1]['midSpin']:floors[i-1]['numPlanets']=planets
            elif kind=='AutoPlayTiles':auto=bool(a['enabled'])
            elif kind=='ScaleMargin':margin=a['scale']
        f['isCCW']=int(ccw)
        f['numPlanets']=planets
        f['margin']=margin
        # The official core uses the last speed event at each angle offset;
        # zero-offset changes are the only active form in these main charts.
        for a in changes:
            assert a.get('angleOffset',0)==0,('Mid-floor speed change',meta['code'],i,a)
            speed=a['beatsPerMinute']/bpm if a['speedType']=='Bpm' else speed*a['bpmMultiplier']
        f['speed']=speed
    return dict(id=meta['id'],code=meta['code'],title=meta['title'],bpm=bpm,offset=settings['offset']/1000,
                countdown=settings.get('countdownTicks',4),separate_countdown=settings.get('separateCountdownTime',True),
                floors=floors,checkpoints=json_checkpoints(d),source=f'Official JSON TextAsset {meta["text"]}',
                camera_initial=settings.get('zoom',100)/100,
                camera_actions=[a for a in d.get('actions',[]) if a['eventType'] in ('MoveCamera','RepeatEvents')],native_camera_effects=[])

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--game',type=Path,default=Path(DEFAULT_GAME));args=ap.parse_args()
    data=args.game/'A Dance of Fire and Ice_Data';out=ROOT/'assets/private';out.mkdir(exist_ok=True,parents=True)
    source=dict(path=str(args.game.resolve()),build_sha256=hashlib.sha256((data/'globalgamemanagers').read_bytes()).hexdigest())
    marker=ROOT/'build/catalog/source.json'
    if not marker.exists() or json.loads(marker.read_text())!=source or 'checkpoints' not in json.loads((ROOT/'build/catalog/scene-12.json').read_text()):
        subprocess.run([sys.executable,str(ROOT/'tools/audit_catalog.py'),'--game',str(args.game)],check=True)
    resources=UnityPy.load(str(data/'resources.assets'));texts={};audio={}
    needed={m['text'] for m in WORLDS[12:] if m['text']}
    for o in resources.objects:
        if o.type.name=='TextAsset' and o.path_id in needed:
            texts[o.path_id]=load_game_json(o.read().m_Script)
        if o.type.name=='AudioClip':
            clip=o.read();audio[clip.m_Name]=clip
    for meta in WORLDS[12:]:
        n=meta['id'];scene=meta['scene']
        if scene:
            d=json.loads((ROOT/f'build/catalog/scene-{scene}.json').read_text());cond=d['conductors'][0]
            c=dict(id=n,code=meta['code'],title=meta['title'],bpm=cond['bpm'],offset=cond['addoffset'],
                   countdown=cond['countdownTicks'],separate_countdown=bool(cond['separateCountdownTime']),
                   floors=[{k:f[k] for k in FLOOR_FIELDS+('auto',)} for f in d['floors']],checkpoints=d['checkpoints'],source=f'Unity scene {scene}')
        else:c=normalize_json(texts[meta['text']],meta)
        (out/f'level{n}.json').write_text(json.dumps(c,indent=2),encoding='utf8')
        wav=out/f'{n}-X.wav'
        if not wav.exists():
            clip=audio.get(meta['audio'])
            if clip is None:
                env=UnityPy.load(str(data/f'sharedassets{scene}.assets'))
                clip=next(o.read() for o in env.objects if o.type.name=='AudioClip' and o.read().m_Name==meta['audio'])
            wav.write_bytes(next(iter(clip.samples.values())))
        print(meta['code'],len(c['floors'])-1,'floors',sum(f['midSpin'] for f in c['floors']),'midspins',flush=True)
    (out/'official-catalog.json').write_text(json.dumps(WORLDS,indent=2))

if __name__=='__main__':main()
