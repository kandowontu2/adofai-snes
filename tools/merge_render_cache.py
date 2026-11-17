"""Replace complete rendered charts without replacing their pack or music."""
import argparse
import json
import re
import shutil
from pathlib import Path


def merge(source, target, level, *, preserve_vfx_off=False):
    source, target = Path(source), Path(target)
    old = json.loads((target / f'level{level}.json').read_text())
    new = json.loads((source / f'level{level}.json').read_text())
    assert new.get('mode1_snapshot') and not new.get('snapshot_preview')
    assert new.get('snapshot_postroll', 0) >= 120
    assert new['snapshot_frames'] == new['last_frame'] + new['snapshot_postroll'] + 1
    # Rendering must not silently change the already distributed music or
    # checkpoint entry points. Such changes need a separate audio rebuild.
    for key in ('id', 'steps', 'hits', 'checkpoints', 'offset', 'duration'):
        assert old[key] == new[key], (level, key)
    assert [n['frame'] for n in old['notes']] == [n['frame'] for n in new['notes']]
    assert (target / f'level{level}.brr').read_bytes() == (source / f'level{level}.brr').read_bytes()
    alternate = old.get('vfx_off')
    if preserve_vfx_off and alternate is None:
        assert level not in (68, 73), 'T3 gameplay effects are never optional'
        alternate = {key: old[key] for key in
                     ('stream_packets', 'stream_msu_base', 'mode1_seed_base', 'mode1_glyph_count')}
        reference=target/f'vfx-off-{level}';reference.mkdir(exist_ok=True)
        shutil.copyfile(target/f'level{level}.json',reference/f'level{level}.json')
        for prefix in ('patterns','timeline','track_map'):
            shutil.copyfile(target/f'{prefix}{level}.bin',reference/f'{prefix}{level}.bin')
        alternate['verification_source']=reference.name
        alternate['wide_snapshot_atlas']=bool(old.get('wide_snapshot_atlas'))
        assert old.get('compact_snapshot_seeds')
        alternate['compact_snapshot_seeds']=old['compact_snapshot_seeds']
        for key in ('snapshot_packet_sharing','snapshot_shared_bytes'):
            if key in old:alternate[key]=old[key]
        for prefix in ('stream_index', 'stream_data', 'mode1_seeds'):
            shutil.copyfile(target / f'{prefix}{level}.bin', target / f'{prefix}_vfx_off{level}.bin')
    for path in source.iterdir():
        if path.is_file() and re.fullmatch(r'[a-z][a-z0-9_]*[a-z_]%d(?:-checkpoint-\d+)?\.bin' % level, path.name):
            shutil.copyfile(path, target / path.name)
    if alternate:
        new['vfx_off'] = alternate
    (target / f'level{level}.json').write_text(json.dumps(new, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--target', type=Path, required=True)
    parser.add_argument('--level', type=int, required=True)
    parser.add_argument('--preserve-vfx-off', action='store_true')
    args = parser.parse_args()
    merge(args.source, args.target, args.level, preserve_vfx_off=args.preserve_vfx_off)
