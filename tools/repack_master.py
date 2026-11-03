"""Link a frozen set of compiled charts without rasterizing them again."""
import argparse,json
from pathlib import Path
import campaign_assets as assets
from animation_assets import generate
from msu_assets import generate as msu_generate

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);args=ap.parse_args()
    out=args.out;assets.OUT=out
    pack=json.loads((out/'pack.json').read_text());assert pack['levels']==list(range(1,62))
    charts=[];blobs=assets.ui_assets(pack['title'],mode7=True);music={}
    for n in pack['levels']:
        chart=json.loads((out/f'level{n}.json').read_text());charts.append(chart)
        for prefix in ('chart','track_chr','track_map','timeline','visibility_index','checkpoints'):
            name=f'{prefix}{n}';blobs[name]=(out/f'{name}.bin').read_bytes()
        generate(out,chart,blobs[f'timeline{n}'],(out/f'patterns{n}.bin').read_bytes())
        blobs[f'track_map{n}']=(out/f'track_map{n}.bin').read_bytes()
        blobs[f'timeline{n}']=bytes(2)
        music[n]=assets.encode_music(chart);blobs[f'music{n}']=bytes(2)
        (out/f'level{n}.json').write_text(json.dumps(chart,indent=2))
    (out/'manifest.json').write_text(json.dumps(charts,indent=2))
    for name,blob in blobs.items():
        if not name.startswith('timeline'):(out/f'{name}.bin').write_bytes(blob)
    assets.pack_payload(blobs,charts,msu=True);assets.common_tables(charts)
    msu_generate(out,charts,music)

if __name__=='__main__':main()
