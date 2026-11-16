"""Import mariokirby1703's authored Triple Planet Workshop collection."""
import argparse,json
from pathlib import Path
from import_featured import ROOT,DEFAULT_GAME,import_chart

TRIPLE_PLANET=json.loads(Path(__file__).with_name('triple_planet_catalog.json').read_text())

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--levels',type=int,nargs='+')
    args=parser.parse_args()
    folder=Path(DEFAULT_GAME).parents[1]/'workshop/content/977950'
    out=ROOT/'assets/private';soundfile=out/'hitsound-levels.json'
    sounds=json.loads(soundfile.read_text())
    for meta in TRIPLE_PLANET:
        if args.levels and meta['id'] not in args.levels:continue
        data,sound=import_chart(meta,folder,out)
        data.update(featured_classic=False,triple_planet=True)
        if any(f.get('freeroam') for f in data['floors']):
            data['decoration_hitboxes_all_regions']=True
        (out/f"level{meta['id']}.json").write_text(json.dumps(data,indent=2))
        sounds[str(meta['id'])]=sound
        soundfile.write_text(json.dumps(sounds,indent=2))
        print(meta['code'],len(data['floors'])-1,'floors',flush=True)

if __name__=='__main__':main()
