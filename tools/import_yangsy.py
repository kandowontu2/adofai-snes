"""Import Yangsy-authored cursed charts from the owner's Workshop downloads."""
import argparse
import json
from pathlib import Path
from import_featured import ROOT, DEFAULT_GAME, import_chart, read_chart

YANGSY = json.loads(Path(__file__).with_name('yangsy_catalog.json').read_text())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--levels', type=int, nargs='+')
    args = parser.parse_args()
    folder = Path(DEFAULT_GAME).parents[1] / 'workshop/content/977950'
    out = ROOT / 'assets/private'
    soundfile = out / 'hitsound-levels.json'
    sounds = json.loads(soundfile.read_text())
    for entry in YANGSY:
        if args.levels and entry['id'] not in args.levels:
            continue
        source = folder / entry['workshop'] / 'main.adofai'
        raw, _ = read_chart(source)
        meta = dict(entry, artist=raw['settings'].get('artist', ''))
        data, sound = import_chart(meta, folder, out)
        sounds[str(meta['id'])] = sound
        # Preserve completed imports if a later chart exposes an unsupported event.
        soundfile.write_text(json.dumps(sounds, indent=2))
        print(meta['code'], len(data['floors']) - 1, 'floors', flush=True)


if __name__ == '__main__':
    main()
