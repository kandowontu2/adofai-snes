"""Import missing Firestix collection maps from the owner's Workshop files."""
import argparse,json
from pathlib import Path
from import_featured import ROOT,DEFAULT_GAME,import_chart

FIRESTIX=json.loads(Path(__file__).with_name('firestix_catalog.json').read_text())

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--levels',type=int,nargs='+')
    args=parser.parse_args()
    folder=Path(DEFAULT_GAME).parents[1]/'workshop/content/977950'
    out=ROOT/'assets/private';soundfile=out/'hitsound-levels.json'
    sounds=json.loads(soundfile.read_text())
    for meta in FIRESTIX:
        if args.levels and meta['id'] not in args.levels:continue
        data,sound=import_chart(meta,folder,out);sounds[str(meta['id'])]=sound
        print(meta['code'],len(data['floors'])-1,'floors',flush=True)
    soundfile.write_text(json.dumps(sounds,indent=2))

if __name__=='__main__':main()
