"""Build PCM music separately, leaving verified ROM/MSU data untouched."""
import argparse
import json
from pathlib import Path
from msu_assets import generate_pcm_tracks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--levels', type=int, nargs='+')
    args = parser.parse_args()
    catalog = json.loads((args.source / 'pack.json').read_text())['levels']
    levels = args.levels or catalog
    assert set(levels) <= set(catalog), 'Requested chart is not in this pack'
    args.out.mkdir(parents=True, exist_ok=True)
    manifest = []
    for level in levels:
        chart = json.loads((args.source / f'level{level}.json').read_text())
        tracks = generate_pcm_tracks(args.out, chart)
        manifest.append(dict(id=level, code=chart['code'], tracks=tracks))
        print(chart['code'], len(tracks), 'PCM entries', flush=True)
    (args.out / 'pcm-manifest.json').write_text(json.dumps(dict(
        format='MSU1 44100 Hz signed 16-bit stereo', levels=manifest), indent=2))


if __name__ == '__main__':
    main()
