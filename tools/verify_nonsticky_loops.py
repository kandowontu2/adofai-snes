"""Check that repeated physical loop positions ignore spreading tile artwork."""
import argparse,collections,json,struct
from pathlib import Path
from verification_data import identity
ROOT=Path(__file__).resolve().parents[1]

def check(base,n,start,end):
    c=json.loads((base/f'level{n}.json').read_text());blob=(base/f'chart{n}.bin').read_bytes()
    count=len(c['notes']);groups=collections.defaultdict(list)
    for i in range(start,end):
        note=c['notes'][i];assert not note['stick_to_floor']
        groups[note['x'],note['y']].append(i)
    pairs=[];bad=[]
    for indices in groups.values():
        first=indices[0]
        a=tuple(struct.unpack_from('<H',blob,2*(first+axis*count))[0] for axis in range(2))
        for i in indices[1:]:
            b=tuple(struct.unpack_from('<H',blob,2*(i+axis*count))[0] for axis in range(2))
            pairs.append([first,i])
            if a!=b:bad.append([first,i,a,b])
    assert len(pairs)>=10,(n,'Insufficient repeated-position coverage')
    return dict(id=n,compared_pairs=len(pairs),displaced_pairs=bad,passed=not bad)

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--pack',required=True)
    ap.add_argument('--before',type=Path);args=ap.parse_args()
    base=ROOT/'build/packs'/args.pack;frozen=identity(base/'adofai.sfc',fresh=True);rows=[]
    for n,start,end in ((159,477,567),(90,949,1249)):
        row=check(base,n,start,end);assert row['passed'],row
        if args.before:
            control=check(args.before,n,start,end)
            assert not control['passed'],(n,'Fault control did not expose displaced loops')
            row['before_displaced_pairs']=len(control['displaced_pairs'])
        rows.append(row)
    report=dict(passed=True,**frozen,results=rows)
    (base/'verification/nonsticky-loops.json').write_text(json.dumps(report,indent=2))
    print('NONSTICKY LOOPS PASS',[(r['id'],r['compared_pairs']) for r in rows],flush=True)

if __name__=='__main__':main()
