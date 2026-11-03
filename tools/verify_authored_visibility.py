"""Verify original floor visibility separately from camera-only culling."""
import argparse,json
from pathlib import Path
from track_visibility import visibility_schedule
from verification_data import identity
ROOT=Path(__file__).resolve().parents[1]

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--pack',default='master');args=ap.parse_args()
    base=ROOT/'build/packs'/args.pack;rows=[]
    for n in json.loads((base/'pack.json').read_text())['levels']:
        c=json.loads((base/f'level{n}.json').read_text())
        d=json.loads((ROOT/f'assets/private/level{n}.json').read_text())
        initial,changes=visibility_schedule(d,c)
        expected=[[(0,a)] for a in initial]
        for frame,updates in changes.items():
            for i,value in updates.items():
                if expected[i][-1][0]==frame:expected[i][-1]=(frame,value)
                elif expected[i][-1][1]!=value:expected[i].append((frame,value))
        actual=[list(map(tuple,v)) for v in c['visibility_floor_versions']]
        assert actual==expected,(n,'Original opacity/appearance/disappearance was changed')
        assert c.get('authored_visibility') and c.get('global_pattern_references')
        assert not c.get('readability_compact_preview')
        assert c['readability_window']['seconds'] is c['readability_window']['preview'] is None
        rows.append(dict(level=n,code=c['code'],floors=len(initial),authored_changes=sum(map(len,expected)),
                         material_capacity=c['track_color_slots'],full_silhouettes=True,artificial_reveal_window=False))
    report=dict(passed=True,**identity(base/'adofai.sfc'),worlds=rows)
    (base/'verification').mkdir(exist_ok=True)
    (base/'verification/authored-visibility.json').write_text(json.dumps(report,indent=2))
    print(f'PASS: {len(rows)} charts retain original visibility, full silhouettes and no invented musical reveal window')

if __name__=='__main__':main()
