"""Private SA-1 temporaries and the public CPU-to-worker mailbox layout."""
import re

HOT_NAMES = (
    'pattern_queue_count', 'pattern_slot', 'm7_row_count', 'm7_row_span',
    'pattern_peak_queued', 'msu_pcm', 'event_count', 'pattern_hi',
    'map_scan_x', 'm7_run_index',
)
HOT_BASE = 0x700
PRIVATE_NAMES = (
    'M7_CACHE_FREE','M7_CACHE_SCAN','M7_CACHE_FINAL','M7_CACHE_LOGICAL',
    'M7_CACHE_PHYSICAL','M7_CACHE_BUDGET','M7_CACHE_ACTIVE_CURSOR',
    'M7_BITMAP_TAG','M7_BITMAP_DEADLINE','M7_BITMAP_CURSOR','M7_BITMAP_CHOICE',
    'M7_BITMAP_BEST','M7_BITMAP_EXPIRES','M7_BITMAP_WORK','M7_BITMAP_WORK_LIMIT',
    'M7_BITMAP_TARGET','M7_BITMAP_URGENT',
    'SPILL_CHOICE','SPILL_BEST','SPILL_SCAN','SPILL_PLANE0','SPILL_PLANE1',
    'SPILL_X','SPILL_Y','SPILL_COL','SPILL_ROW','SPILL_REMAIN','SPILL_TILE',
    'M7_CACHE_MISSING_COUNT',
    'SPILL_LIVE_COUNT',
    'M7_CACHE_SERIAL_SEEN',
    'SPILL_MAP_ACTIVE',
    'ROM_SOURCE_PAGE',
    'M7_MAP_PREPARED',
    'M7_CACHE_CODE_VALID',
    'M7_ROW_CODE_VALID',
    'NATIVE_SOURCE_PAGE',
    'NATIVE_ROW_TAIL','NATIVE_ROW_BASE','NATIVE_ROW_UNDO',
    'M7_BULK_ROWS',
)
PRIVATE_BASE=HOT_BASE+2*len(HOT_NAMES)


def worker_config():
    return '''MEMORY {
 ROM: start=$8000,size=$6000,type=ro,file=%O,fill=yes;
 HOTROM: start=$E000,size=$1000,type=ro,file=%O,fill=yes;
 HOTRAM: start=$0500,size=$0200,type=rw;
 CACHEIRAM: start=$0500,size=$0200,type=rw;
 FIXEDIRAM: start=$0500,size=$0180,type=rw;
 MODE1IRAM: start=$0500,size=$0200,type=rw;
 PROJECTEDIRAM: start=$0500,size=$0200,type=rw;
 SNAPSHOTIRAM: start=$0500,size=$0200,type=rw;
 COPYIRAM: start=$0100,size=$0400,type=rw;
 ROWIRAM: start=$0680,size=$0080,type=rw;
 COMPAREIRAM: start=$0680,size=$0080,type=rw;
}
SEGMENTS {
 CODE: load=ROM,type=ro;
 HOTOBJECTS: load=HOTROM,run=HOTRAM,type=ro,define=yes,optional=yes;
 HOTCACHE: load=HOTROM,run=CACHEIRAM,type=ro,define=yes,optional=yes;
 HOTFIXED: load=HOTROM,run=FIXEDIRAM,type=ro,define=yes,optional=yes;
 HOTMODE1: load=HOTROM,run=MODE1IRAM,type=ro,define=yes,optional=yes;
 HOTPROJECTED: load=HOTROM,run=PROJECTEDIRAM,type=ro,define=yes,optional=yes;
 HOTSNAPSHOT: load=HOTROM,run=SNAPSHOTIRAM,type=ro,define=yes,optional=yes;
 HOTCOPIES: load=HOTROM,run=COPYIRAM,type=ro,define=yes,optional=yes;
 HOTROWS: load=HOTROM,run=ROWIRAM,type=ro,define=yes,optional=yes;
 HOTCOMPARE: load=HOTROM,run=COMPAREIRAM,type=ro,define=yes,optional=yes;
}
'''


def worker_symbols(label_text):
    rows = [(name, int(value, 16)) for value, name in
            re.findall(r'al ([0-9A-Fa-f]+) \.([\w]+)', label_text)]
    labels = dict(rows)
    relocated = {labels[name]: HOT_BASE + 2*i for i, name in enumerate(HOT_NAMES)}
    assert HOT_BASE + 2*len(HOT_NAMES) <= 0x780
    tables={'orbit_arc_x','orbit_arc_y','orbit_arc_tiles','orbit_arc_flips'}
    return '\n'.join(f'{name} = ${relocated.get(value, value):04X}'
                     for name, value in rows if value < 0x100 or 0x1800 <= value < 0x2000 or name in tables)


def worker_layout(source):
    text=source.split('.segment "ZEROPAGE"')[0].replace(
        'M7_CACHE_READY=M7_SHARED_BASE+$FC46', 'M7_CACHE_READY=$000784')
    assert PRIVATE_BASE+2*len(PRIVATE_NAMES)<=0x780
    for i,name in enumerate(PRIVATE_NAMES):
        text,count=re.subn(r'^'+name+r'=[^\n]+',f'{name}=${PRIVATE_BASE+2*i:06X}',text,flags=re.M)
        assert count==1,name
    arrays={'M7_PATTERN_SELECTED':0x100,'M7_NEW_VISIBLE':0x200,
            'M7_OLD_VISIBLE':0x300,'M7_LOGICAL_TO_PPU':0x400}
    for name,address in arrays.items():
        text,count=re.subn(r'^'+name+r'=[^\n]+',
                          lambda m:f'.ifdef SA1_WRAM_RENDERER\n{name}=${address:06X}\n.else\n{m[0]}\n.endif',
                          text,flags=re.M)
        assert count==1,name
    name='M7_RESIDENT_HASH'
    text,count=re.subn(r'^'+name+r'=[^\n]+',
        lambda m:f'.ifdef SA1_WRAM_RENDERER\n.ifndef ROM_PATTERN_COUNT\n{name}=$000500\n.else\n{m[0]}\n.endif\n.else\n{m[0]}\n.endif',text,flags=re.M)
    assert count==1,name
    return text
