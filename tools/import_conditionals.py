"""Restore conditional event declarations dropped by earlier imports."""
import json
from pathlib import Path
from official_catalog import WORLDS,load_game_json
from import_tech import TECH
ROOT=Path(__file__).resolve().parents[1]
KINDS=('AnimateTrack','MoveTrack','PositionTrack','RepeatEvents','Hide','ColorTrack','RecolorTrack','ChangeTrack','SetConditionalEvents')

def main():
    for meta in WORLDS+TECH:
        if not(meta.get('text') or meta['id']>=40):continue
        path=ROOT/f'assets/private/level{meta["id"]}.json';data=json.loads(path.read_text())
        source=Path(data['source']) if meta['id']>=40 else ROOT/f'build/catalog/text-{meta["text"]}.json'
        raw=load_game_json(source.read_text(encoding='utf-8-sig'))
        data['track_actions']=[a for a in raw['actions'] if a['eventType'] in KINDS]
        path.write_text(json.dumps(data,indent=2),encoding='utf-8')
        print(meta['code'],sum(a['eventType']=='SetConditionalEvents' for a in data['track_actions']),'conditions',flush=True)

if __name__=='__main__':main()
