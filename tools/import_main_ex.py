"""Import the twelve Team Vega main-world EX remakes selected by the user."""
import argparse,json
from pathlib import Path
from import_featured import ROOT,DEFAULT_GAME,import_chart
MAIN_EX=json.loads(Path(__file__).with_name('main_ex_catalog.json').read_text())
def main():
 p=argparse.ArgumentParser();p.add_argument('--levels',type=int,nargs='+');args=p.parse_args()
 folder=Path(DEFAULT_GAME).parents[1]/'workshop/content/977950';out=ROOT/'assets/private'
 target=out/'hitsound-levels.json';sounds=json.loads(target.read_text())
 for entry in MAIN_EX:
  if args.levels and entry['id'] not in args.levels:continue
  data,sound=import_chart(entry,folder,out);sounds[str(entry['id'])]=sound
  target.write_text(json.dumps(sounds,indent=2));print(entry['code'],len(data['floors'])-1,'floors',flush=True)
if __name__=='__main__':main()
