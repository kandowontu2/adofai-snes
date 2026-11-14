"""Batch contiguous floor updates without relocating any checkpoint or audio data."""
import hashlib
import json
import os
import struct
from pathlib import Path

HEADER = struct.Struct('<HBHH')

def records(data):
    pos = 0
    while pos + 7 <= len(data):
        frame, kind, index, value = HEADER.unpack_from(data, pos)
        extra = (value if kind in (22,25,26,28,29,30,31,33,34,36,37,39,41,43,44) else 4 if kind == 42 else 2 if kind == 35 else 66 if kind == 24 else 68 if kind == 4 else value if kind in (5, 14) else
                 value * 3 if kind == 8 else value + 4 if kind == 9 else
                 7 * (value - 1) if kind in (17, 18, 19) else
                 75 * value - 7 if kind == 20 else
                 value + 7 if kind == 21 else 0)
        end = pos + 7 + extra
        assert end <= len(data), (pos, kind, end, len(data))
        yield pos, end, frame, kind, index, value
        pos = end
        if kind == 255:
            assert pos == len(data), (pos, len(data))
            return
    raise ValueError('Missing animation terminator')

def semantic_digest(data):
    h = hashlib.sha256()
    for pos, end, frame, kind, index, value in records(data):
        if kind in (21,26):
            continue # Optional catch-up branch; canonical stream follows it.
        if kind == 29:
            for i in range(index):
                cell,_,v=struct.unpack_from('<HHB',data,pos+7+5*i)
                h.update(HEADER.pack(frame,0,cell,v))
        elif kind == 25:
            for i in range(index):
                slot,tag=struct.unpack_from('<HH',data,pos+7+4*i)
                h.update(HEADER.pack(frame,27,slot,tag))
        elif kind in (17, 18, 19):
            size = 1 if kind == 19 else 2
            original = {17: 2, 18: 3, 19: 1}[kind]
            for i in range(value):
                v = int.from_bytes(data[pos+7+i*size:pos+7+(i+1)*size], 'little')
                h.update(HEADER.pack(frame, original, index+i, v))
        elif kind == 20:
            for i in range(value):
                at=pos+7+68*i
                slot,tag=struct.unpack_from('<HH',data,at)
                hints=data[pos+7+68*value+4*i:pos+7+68*value+4*(i+1)]
                h.update(HEADER.pack(frame,4,slot,tag)+hints+data[at+4:at+68])
        else:
            h.update(data[pos:end])
    return h.hexdigest()

def batch(data):
    rows = list(records(data)); output = bytearray(data); groups = []; i = 0
    while i < len(rows):
        pos, end, frame, kind, index, value = rows[i]
        j = i + 1
        if kind in (1, 2, 3):
            while j < len(rows) and j-i < 4096:
                other = rows[j]
                if other[2:5] != (frame, kind, index+j-i): break
                j += 1
        elif kind == 4:
            while j < len(rows) and j-i < 16 and rows[j][2:4] == (frame,kind):
                j += 1
        elif kind == 27:
            while j < len(rows) and j-i < 256 and rows[j][2:4] == (frame,kind):
                j += 1
        count = j-i
        if kind == 27 and count >= 3:
            end=rows[j-1][1]
            body=b''.join(struct.pack('<HH',r[4],r[5]) for r in rows[i:j])
            span=end-pos-7
            output[pos:end]=HEADER.pack(frame,25,count,span)+body+bytes(span-len(body))
            groups.append((pos,end,count))
        elif kind == 4 and count >= 3:
            end=rows[j-1][1]
            body=b''.join(struct.pack('<HH',r[4],r[5])+data[r[0]+11:r[1]] for r in rows[i:j])
            hints=b''.join(data[r[0]+7:r[0]+11] for r in rows[i:j])
            replacement=HEADER.pack(frame,20,0,count)+body+hints
            output[pos:end]=replacement+bytes(end-pos-len(replacement))
            groups.append((pos,end,count))
        elif count >= 3:
            end = rows[j-1][1]
            values = [r[5] for r in rows[i:j]]
            payload = bytes(values) if kind == 1 else struct.pack('<'+'H'*count, *values)
            replacement = HEADER.pack(frame, {1:19, 2:17, 3:18}[kind], index, count)+payload
            output[pos:end] = replacement + bytes(end-pos-len(replacement))
            groups.append((pos, end, count))
        i = j
    assert len(output) == len(data)
    assert semantic_digest(output) == semantic_digest(data)
    return bytes(output), groups

def patch_pack(out):
    out = Path(out)
    pack = json.loads((out/'pack.json').read_text())
    standalone = 'ROM_DATA_BUILD' in (out/'addresses.inc').read_text()
    target = out/('sa1_payload.bin' if standalone else 'adofai.msu')
    data = bytearray(target.read_bytes())
    descriptors = (out/'msu_descriptors.bin').read_bytes()
    reports = []
    for i, n in enumerate(pack['levels']):
        chart = json.loads((out/f'level{n}.json').read_text())
        _, _, _, offset, table, _, _, _ = struct.unpack_from('<IHHIIHHI', descriptors, i*24)
        bias = 0x10000 if standalone else 0
        offset -= bias; table -= bias
        length = chart['animation_bytes']
        before = bytes(data[offset:offset+length])
        after, groups = batch(before)
        for c in range(len(chart['checkpoints'])):
            snapshot = struct.unpack_from('<I', data, table+c*4)[0]-bias
            cursor = struct.unpack_from('<I', data, snapshot+4)[0]
            assert not any(a < cursor < b for a,b,_ in groups), (n,c,cursor)
        data[offset:offset+length] = after
        loose = out/f'animation{n}.bin'
        if loose.exists():
            assert loose.read_bytes() in (before, after), (n, 'stream mismatch')
            loose.write_bytes(after)
        reports.append(dict(level=n, groups=len(groups), dispatches_removed=sum(c-1 for _,_,c in groups), semantic_sha256=semantic_digest(after)))
    if not standalone:
        assert data[:12] == b'ADOFAI-MSU1\0'
        data[12:14] = bytes([23, 0])
        addresses = out/'addresses.inc'
        import re
        addresses.write_text(re.sub(r'MSU_DATA_VERSION = \d+', 'MSU_DATA_VERSION = 23', addresses.read_text()))
    # Atomic replacement also breaks any hard link to the published dataset.
    if data != target.read_bytes():
        temporary = target.with_suffix(target.suffix+'.bulk-tmp')
        temporary.write_bytes(data); os.replace(temporary, target)
    report = out/'animation-bulk.json'
    if any(r['groups'] for r in reports) or not report.exists():
        report.write_text(json.dumps(dict(passed=True, levels=reports), indent=2))
    return reports
