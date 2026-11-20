"""Import explicitly selected community charts from the local Steam workshop."""
import argparse,json,subprocess,hashlib
from pathlib import Path
from import_campaign import DEFAULT_GAME
from import_official import normalize_json
from official_catalog import load_game_json
ROOT=Path(__file__).resolve().parents[1]
COMMUNITY=json.loads((ROOT/'tools/community_catalog.json').read_text())

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--levels',type=int,nargs='+');args=parser.parse_args()
    folder=Path(DEFAULT_GAME).parents[1]/'workshop/content/977950'
    soundfile=ROOT/'assets/private/hitsound-levels.json'
    sounds=json.loads(soundfile.read_text())
    for meta in COMMUNITY:
        if args.levels and meta['id'] not in args.levels:continue
        if meta.get('neo_cosmos'):
            from import_featured import import_chart
            data,sound=import_chart(meta,folder,ROOT/'assets/private')
            data['community']=True
            (ROOT/f'assets/private/level{meta["id"]}.json').write_text(json.dumps(data,indent=2))
            sounds[str(meta['id'])]=sound
            print(meta['code'],len(data['floors'])-1,'tiles',flush=True)
            continue
        source=ROOT/meta['source'] if 'source' in meta else folder/meta['workshop']/meta.get('chart_file','main.adofai')
        text=source.read_text(encoding='utf-8-sig')
        # Original archived v2 file omits one separator between floors 431/432.
        # Keep source bytes intact and record this syntax-only repair.
        old='"angleOffset": 0 }\n\t\t{ "floor": 432'
        repairs=[]
        if old in text:
            text=text.replace(old,'"angleOffset": 0 },\n\t\t{ "floor": 432',1)
            repairs.append('Inserted missing action separator between floors 431 and 432')
        raw=load_game_json(text)
        data=normalize_json(raw,dict(meta,text=meta.get('workshop',meta.get('archive'))))
        settings=raw['settings'];actions=raw['actions']
        data.update(source=str(source),artist=meta['artist'],author=meta['author'],source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),source_repairs=repairs,
                    community=not meta.get('featured_classic',False),featured_classic=meta.get('featured_classic',False),track_settings=settings,track_color_import=1,
                    camera_rotation_initial=settings.get('rotation',0),
                    camera_actions=[a for a in actions if a['eventType'] in ('MoveCamera','RepeatEvents','SetConditionalEvents')],
                    track_actions=[a for a in actions if a['eventType'] in ('AnimateTrack','MoveTrack','PositionTrack','RepeatEvents','Hide','ColorTrack','RecolorTrack','ChangeTrack','SetConditionalEvents')])
        hides={a['floor']:a['hideTileIcon'] for a in actions if a['eventType']=='Hide' and a.get('active',True) and 'hideTileIcon' in a}
        hidden=False;data['hidden_icons']=[]
        for i in range(len(data['floors'])):
            if i in hides:
                v=hides[i];hidden=v.lower() in ('enabled','true','yes','on','1') if isinstance(v,str) else bool(v)
            data['hidden_icons'].append(hidden)
        n=meta['id'];out=ROOT/'assets/private'
        (out/f'level{n}.json').write_text(json.dumps(data,indent=2))
        subprocess.run(['ffmpeg','-v','error','-y','-i',str(source.parent/settings['songFilename']),'-c:a','pcm_s16le',str(out/f'{n}-X.wav')],check=True)
        sounds[str(n)]=dict(hitsound=settings.get('hitsound','Kick'),hitsoundVolume=settings.get('hitsoundVolume',100),
                           countdownSpeedMultiplier=settings.get('countdownSpeedMultiplier',1),
                           events=[a for a in actions if a['eventType']=='SetHitsound' and a.get('active',True)])
        print(meta['code'],len(data['floors'])-1,'tiles',flush=True)
    soundfile.write_text(json.dumps(sounds,indent=2))

if __name__=='__main__':main()
