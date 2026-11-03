"""Import every Featured Tech main chart from the official installed catalog."""
import json,subprocess,sys
from pathlib import Path
from import_campaign import DEFAULT_GAME
from import_official import normalize_json
from official_catalog import load_game_json
ROOT=Path(__file__).resolve().parents[1]
TECH=json.loads((ROOT/'tools/tech_catalog.json').read_text())

def main():
    base=Path(DEFAULT_GAME).parents[1]/'workshop/content/977950'
    for meta in TECH:
        folder=base/meta['workshop'];source=folder/'main.adofai'
        assert source.exists(),f'Missing {meta["title"]}; run tools/download_tech.py'
        raw=load_game_json(source.read_text(encoding='utf-8-sig'))
        data=normalize_json(raw,dict(meta,text=meta['workshop']))
        data.update(source=str(source),track_settings=raw['settings'],track_actions=[a for a in raw['actions'] if a['eventType'] in ('AnimateTrack','MoveTrack','PositionTrack','RepeatEvents','Hide','ColorTrack','RecolorTrack','ChangeTrack','SetConditionalEvents')])
        hides={a['floor']:a['hideTileIcon'] for a in raw['actions'] if a['eventType']=='Hide' and a.get('active',True) and 'hideTileIcon' in a}
        hidden=False;data['hidden_icons']=[]
        for i in range(len(data['floors'])):
            if i in hides:
                v=hides[i];hidden=v.lower() in ('enabled','true','yes','on','1') if isinstance(v,str) else bool(v)
            data['hidden_icons'].append(hidden)
        n=meta['id'];out=ROOT/'assets/private';out.mkdir(parents=True,exist_ok=True)
        (out/f'level{n}.json').write_text(json.dumps(data,indent=2))
        audio=folder/raw['settings']['songFilename'];wav=out/f'{n}-X.wav'
        assert audio.exists(),audio
        if not wav.exists() or wav.stat().st_mtime<audio.stat().st_mtime:
            subprocess.run(['ffmpeg','-v','error','-y','-i',str(audio),'-c:a','pcm_s16le',str(wav)],check=True)
        print(meta['code'],meta['title'],len(data['floors'])-1,'tiles',flush=True)

if __name__=='__main__':main()
