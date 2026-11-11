"""Prepare an immutable event stream for the SA-1 animation decoder."""
import argparse
import collections
import json
import struct
from pathlib import Path
from animation_bulk import records

KINDS={0,1,2,3,6,7,8,9,10,11,12,13,14,15,23,27,28,255}


def prepare(source, level=23):
    source=Path(source);path=source/f'level{level}.json';c=json.loads(path.read_text())
    assert c.get('resident_pattern_format') and c.get('compiled_reference_sets')
    assert not c.get('catchup_format') and not c.get('state_span_format')
    stream=(source/f'animation{level}.bin').read_bytes()
    assert {r[3] for r in records(stream)}<=KINDS
    (source/f'resident_animation{level}.bin').write_bytes(stream)
    c.update(native_stream_format=1,wrapped_mode7_map=1,catchup_disabled=True)
    path.write_text(json.dumps(c,indent=2))


def prepare_ar_pack(source):
    """Apply the release's AR-X cache schedule to freshly compiled charts."""
    from fixed_prefetch import prepare as schedule_prefetch
    from msu_assets import generate
    from resident_patterns import prepare as prepare_patterns

    level=23
    levels=json.loads((source/'pack.json').read_text())['levels']
    if level not in levels:
        raise ValueError('The chart cache must include AR-X (level 23)')
    chart_path=source/f'level{level}.json'
    chart=json.loads(chart_path.read_text())
    if not chart.get('native_stream_format'):
        if not chart.get('compiled_reference_sets') or chart.get('adaptive_raster'):
            raise ValueError('Compile a full-resolution AR-X chart cache first')
        chart=prepare_patterns(source,level)
        versions=chart['bitmap_prefetch_versions']
        loads=collections.Counter(row[2] for row in versions)
        future=sorted([max(1,deadline-160),raw,deadline,end]
                      for _,raw,deadline,end in versions if loads[deadline]>=100)
        (source/f'resident_future{level}.bin').write_bytes(b''.join(
            struct.pack('<HHHH',frame,raw,end,deadline) for frame,raw,deadline,end in future))
        chart.update(bitmap_prefetch_versions=future,bitmap_prefetch_enabled=False,direct_pattern_until=1800)
        chart_path.write_text(json.dumps(chart,indent=2))
        schedule_prefetch(source,level)
        prepare(source,level)
    charts=[json.loads((source/f'level{n}.json').read_text()) for n in levels]
    music={n:(source/f'level{n}.brr').read_bytes() for n in levels}
    generate(source,charts,music,generate_pcm=False)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description='Prepare full-detail AR-X assets for the SA-1 master and standalone.')
    parser.add_argument('--source',type=Path,required=True,help='Fresh chart-cache directory from campaign_assets.py')
    prepare_ar_pack(parser.parse_args().source)
