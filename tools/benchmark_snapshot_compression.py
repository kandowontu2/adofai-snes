"""Compare lossless independent-pose codecs without modifying release assets."""
import argparse
import json
import struct
import zlib
from pathlib import Path
import lz4.block
from animation_bulk import HEADER, records


def poses(folder, level):
    chart = json.loads((folder / f'level{level}.json').read_text())
    header_bytes = 96 + (184 - chart.get('snapshot_map_top', 32)) * 8
    stream = (folder / f'stream_data{level}.bin').read_bytes()
    index = (folder / f'stream_index{level}.bin').read_bytes()
    refs, seen = set(), set()
    for _, _, choice in struct.iter_unpack('<HHI', index):
        for j in range(4):
            _, size, offset = struct.unpack_from('<HHI', stream, choice + j * 8)
            while size:
                length = size & 32767
                if offset not in seen:
                    seen.add(offset)
                    for a, b, t, kind, i, v in records(stream[offset:offset + length]):
                        if kind == 42:
                            refs.add(struct.unpack_from('<I', stream, offset + a + 7)[0])
                if not size & 32768:
                    break
                offset += length
                size = struct.unpack_from('<H', stream, offset)[0]
                offset += 2
    for offset in sorted(refs):
        t, kind, count, size = HEADER.unpack_from(stream, offset)
        body = stream[offset + 7:offset + 7 + size]
        if kind == 44:
            raw = body
        elif kind in (45,46,47):
            from snapshot_codec import decode,decode_split
            raw=(decode_split if kind in (46,47) else decode)(body,count,header_bytes=header_bytes)
        else:
            assert kind == 41, kind
            raw, pos = bytearray(body[:header_bytes]), header_bytes
            for _ in range(count):
                tag = body[pos]
                pos += 1
                assert tag in (0, 1, 2), tag
                n = 32 if tag == 0 else 16
                glyph = body[pos:pos + n]
                raw += glyph if tag == 0 else glyph + bytes(16) if tag == 1 else bytes(16) + glyph
                pos += n
            assert pos == len(body)
        assert len(raw) == header_bytes + count * 32
        yield size, bytes(raw)


def benchmark(folder, levels):
    results = []
    for level in levels:
        chart = json.loads((folder / f'level{level}.json').read_text())
        if not chart.get('mode1_snapshot'):
            raise ValueError(f'Level {level} is not an independent-pose stream')
        totals = dict(current=0, raw=0, lz4=0, lz4_split=0, deflate=0)
        count = 0
        header_bytes = 96 + (184 - chart.get('snapshot_map_top', 32)) * 8
        for current, raw in poses(folder, level):
            count += 1
            totals['current'] += current
            totals['raw'] += len(raw)
            packed = lz4.block.compress(raw, mode='high_compression', compression=12, store_size=False)
            assert lz4.block.decompress(packed, uncompressed_size=len(raw)) == raw
            totals['lz4'] += 2 + min(len(packed), len(raw))
            for part in (raw[:header_bytes], raw[header_bytes:]):
                packed = lz4.block.compress(part, mode='high_compression', compression=12, store_size=False)
                assert lz4.block.decompress(packed, uncompressed_size=len(part)) == part
                totals['lz4_split'] += 2 + min(len(packed), len(part))
            packed = zlib.compress(raw, level=9)
            assert zlib.decompress(packed) == raw
            totals['deflate'] += len(packed)
        row = dict(level=level, poses=count, bytes=totals)
        results.append(row)
        print(json.dumps(row), flush=True)
    return results


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--levels', type=int, nargs='+', required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    args.report.write_text(json.dumps(benchmark(args.source, args.levels), indent=2))
