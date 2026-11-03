"""Prepare independent master audio encodes using a bounded process pool."""
import concurrent.futures,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def encode(n):
    import campaign_assets as a
    a.OUT=ROOT/'build/packs/master'
    c,_=a.compile_chart(json.loads((ROOT/f'assets/private/level{n}.json').read_text()))
    return n,len(a.encode_music(c))

def main():
    from official_catalog import PACKS
    out=ROOT/'build/packs/master';out.mkdir(exist_ok=True,parents=True)
    for pack,meta in PACKS.items():
        source=ROOT/'build/campaign' if pack=='main' else ROOT/f'build/packs/{pack}'
        for n in meta['levels']:
            for name in (f'level{n}.brr',f'level{n}-audio.json'):
                if not(out/name).exists() and (source/name).exists():shutil.copyfile(source/name,out/name)
    with concurrent.futures.ProcessPoolExecutor(max_workers=8) as pool:
        for result in pool.map(encode,range(40,62)):print(result,flush=True)

if __name__=='__main__':main()
