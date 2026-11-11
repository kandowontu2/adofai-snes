"""Batch sparse map writes on SA-1 without moving checkpoint offsets."""
import json
import os
import struct
from pathlib import Path
from animation_bulk import HEADER, records, semantic_digest


def batch_sparse(data, chart):
    rows = list(records(data))
    result = bytearray(data)
    groups = []
    i = 0
    while i < len(rows):
        start, end, frame, kind, _, _ = rows[i]
        j = i + 1
        if kind == 0:
            while j < len(rows) and j-i < 128 and rows[j][2:4] == (frame, 0):
                j += 1
        if j-i >= 4:
            end = rows[j-1][1]
            payload = bytearray()
            for _, _, _, _, cell, value in rows[i:j]:
                x, y = chart['cell_coordinates'][cell]
                payload += struct.pack('<HHB', cell, (y & 127)*128+(x & 127), value)
            span = end-start-7
            assert len(payload) <= span <= 889
            result[start:end] = HEADER.pack(frame, 29, j-i, span)+payload+bytes(span-len(payload))
            groups.append((start, end, j-i))
        i = j
    assert len(result) == len(data)
    assert semantic_digest(result) == semantic_digest(data)
    return bytes(result), groups


def patch_pack(out):
    out = Path(out)
    addresses = (out/'addresses.inc').read_text()
    if 'SA1_BUILD' not in addresses:
        return
    standalone = 'ROM_DATA_BUILD' in addresses
    target = out/('sa1_payload.bin' if standalone else 'adofai.msu')
    image = bytearray(target.read_bytes())
    descriptors = (out/'msu_descriptors.bin').read_bytes()
    levels = json.loads((out/'pack.json').read_text())['levels']
    reports = []
    for index, level in enumerate(levels):
        chart = json.loads((out/f'level{level}.json').read_text())
        if not chart.get('compiled_reference_sets'):
            continue
        stream, table = struct.unpack_from('<II', descriptors, index*24+8)
        bias = 0x10000 if standalone else 0
        before = bytes(image[stream-bias:stream-bias+chart['animation_bytes']])
        after, groups = batch_sparse(before, chart)
        for checkpoint in range(len(chart['checkpoints'])):
            snapshot = struct.unpack_from('<I', image, table-bias+checkpoint*4)[0]-bias
            cursor = struct.unpack_from('<I', image, snapshot+4)[0]
            assert not any(a < cursor < b for a, b, _ in groups), (level, checkpoint, cursor)
        image[stream-bias:stream-bias+len(after)] = after
        loose = out/f'animation{level}.bin'
        if loose.exists():
            assert loose.read_bytes() in (before, after)
            loose.write_bytes(after)
        reports.append(dict(level=level, groups=len(groups),
                            dispatches_removed=sum(n-1 for _, _, n in groups),
                            semantic_sha256=semantic_digest(after)))
    if image != target.read_bytes():
        temporary = target.with_suffix(target.suffix+'.sparse-tmp')
        temporary.write_bytes(image)
        os.replace(temporary, target)
    report = out/'animation-sparse.json'
    if any(row['groups'] for row in reports) or not report.exists():
        report.write_text(json.dumps(dict(passed=True, levels=reports), indent=2))
    return reports
