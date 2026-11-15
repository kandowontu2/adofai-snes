"""Compile authored PNG track replacement and its live-actor projection."""
import argparse
import json
import re
import shutil
from pathlib import Path

from decoration_tracks import DecorationTracks, actor_camera_events
from projected_tracks import compile_section, share_flipped_glyphs
from projected_snapshots import write

ROOT=Path(__file__).resolve().parents[1]


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--level',type=int,required=True)
    ap.add_argument('--end',type=int,help='Preview only; cannot be packaged')
    args=ap.parse_args();out=args.out;out.mkdir(parents=True,exist_ok=True);n=args.level
    if args.source.resolve()!=out.resolve():
        for path in args.source.iterdir():
            if path.is_file() and re.search(r'(?<!\d)'+str(n)+r'(?:[.-])',path.name):
                shutil.copyfile(path,out/path.name)
    chart=json.loads((out/f'level{n}.json').read_text())
    data=json.loads((ROOT/f'assets/private/level{n}.json').read_text())
    renderer=DecorationTracks(data,chart)
    if renderer.pending:raise ValueError(('Unimplemented authored decoration effects',renderer.pending))
    end=args.end if args.end is not None else chart['notes'][-1]['frame']+120
    actors,versions=actor_camera_events(data,chart,end)
    chart.update(decoration_tracks=True,decoration_tracks_preview=args.end is not None,
                 actor_projection_versions=versions,decoration_text_font='assets/graphics/campaign/font.chr')
    (out/f'level{n}.json').write_text(json.dumps(chart,indent=2))
    colors=[]
    glyphs,frames=compile_section(out,n,0,end,extra_colors=colors)
    glyphs,frames=share_flipped_glyphs(glyphs,frames)
    import pickle
    with (out/f'decoration-frames{n}.pickle').open('wb') as f:pickle.dump((glyphs,frames,colors,actors),f)
    write(out,out,n,glyphs,frames,preview=args.end is not None,extra_colors=colors,actor_events=actors)


if __name__=='__main__':
    main()
