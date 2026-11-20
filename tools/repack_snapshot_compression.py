"""Losslessly migrate cached snapshot streams to the shared LZ4 format."""
import argparse
import json
import struct
from pathlib import Path
from animation_bulk import HEADER, records
from projected_tracks import snapshot_pose, raw_seeds
from snapshot_codec import encode, decode, encode_split, decode_split
from sa1_stream import SNAPSHOT_LIMIT


def replace(path, data):
    temporary = path.with_suffix(path.suffix + '.new')
    temporary.write_bytes(data)
    temporary.replace(path)


def repack(folder, level, *, split=False):
    chart_path = folder / f'level{level}.json'
    chart = json.loads(chart_path.read_text())
    assert chart.get('mode1_snapshot'), level
    map_top = chart.get('snapshot_map_top', 32)
    header_bytes = 96 + (184 - map_top) * 8
    stream = (folder / f'stream_data{level}.bin').read_bytes()
    index = (folder / f'stream_index{level}.bin').read_bytes()
    refs, seen = {}, set()
    for _, _, choice in struct.iter_unpack('<HHI', index):
        for j in range(4):
            _, size, offset = struct.unpack_from('<HHI', stream, choice + j * 8)
            while size:
                length = size & 32767
                if offset not in seen:
                    seen.add(offset)
                    for a, b, t, kind, i, v in records(stream[offset:offset + length]):
                        if kind == 42:
                            refs[offset + a] = struct.unpack_from('<I', stream, offset + a + 7)[0]
                if not size & 32768:
                    break
                offset += length
                size = struct.unpack_from('<H', stream, offset)[0]
                offset += 2
    assert refs
    output = bytearray(stream[:min(refs.values())])
    mapping = {}
    for offset in sorted(set(refs.values())):
        t, kind, count, size = HEADER.unpack_from(stream, offset)
        body = stream[offset + 7:offset + 7 + size]
        if kind == 41:
            palette, tilemap, glyphs = snapshot_pose(body, count, map_top=map_top)
            raw = palette + tilemap + b''.join(glyphs)
        elif kind == 44:
            raw = body
        elif kind in (46,47,48,49):
            raw = decode_split(body, count, header_bytes=header_bytes)
        else:
            assert kind == 45, kind
            raw = decode(body, count, header_bytes=header_bytes)
        packed = encode_split(raw, header_bytes=header_bytes) if split or kind in (47,48,49) else encode(raw)
        assert (decode_split if split or kind in (47,48,49) else decode)(packed, count, header_bytes=header_bytes) == raw
        packet = HEADER.pack(t, kind if kind in (48,49) else 47 if kind==47 else 46 if split else 45, count, len(packed)) + packed + HEADER.pack(65535, 255, 0, 0)
        assert len(packet) <= SNAPSHOT_LIMIT, (level, t, len(packet))
        mapping[offset] = len(output), len(packet)
        output += packet
    for ref, offset in refs.items():
        dest, size = mapping[offset]
        struct.pack_into('<H', output, ref + 5, size)
        struct.pack_into('<I', output, ref + 7, dest)
    # Checkpoint reconstruction must be byte-identical, not merely visually close.
    seeds = raw_seeds(index, output, snapshot=True, clone_state=bool(chart.get('mawaru_copy_world')),
                      wide=bool(chart.get('wide_snapshot_atlas')), map_top=map_top)
    assert seeds == (folder / f'mode1_seeds{level}.bin').read_bytes(), level
    replace(folder / f'stream_data{level}.bin', output)
    chart['snapshot_compression'] = 'lz4-split' if split else 'lz4'
    replace(chart_path, json.dumps(chart, indent=2).encode())
    print(level, len(mapping), 'pixel-exact poses;', len(stream), '->', len(output), 'bytes', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--levels', type=int, nargs='+', required=True)
    parser.add_argument('--split', action='store_true')
    args = parser.parse_args()
    for level in args.levels:
        repack(args.source, level, split=args.split)
