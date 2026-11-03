"""Repack UI/SPC changes without regenerating chart graphics or music."""
import json
from pathlib import Path
import campaign_assets as a
from official_catalog import PACKS
ROOT=Path(__file__).resolve().parents[1]

def main():
    for pack,meta in PACKS.items():
        out=ROOT/'build/campaign' if pack=='main' else ROOT/f'build/packs/{pack}'
        a.OUT=out
        charts=json.loads((out/'manifest.json').read_text())
        names=json.loads((out/'placements.json').read_text())
        assets={name:(out/(name+'.bin')).read_bytes() for name in names}
        assets.update(a.ui_assets(meta['title']))
        a.pack_payload(assets,charts);a.common_tables(charts)
        print(pack,'UI refreshed',flush=True)

if __name__=='__main__':main()
