"""Check SA-1 mappings and embedded bytes independently of emulator playback."""
import argparse,json,re,struct
from pathlib import Path
from verification_data import identity
ROOT=Path(__file__).resolve().parents[1]

def verify_cpu_scratch(twirl_begin,twirl_end):
    ranges=[('palette/roles',0x0580,0x05A2),('stream',0x05A2,0x0600),
            ('sprite bins',0x0600,0x0620),('exact budgets',0x0620,0x0760),
            ('exact temporaries',0x0768,0x0778),('DMA commands',0x0778,0x077E),
            ('math labels',0x0780,0x0794),('planet preview',0x07A0,0x07C8),
            ('twirl',twirl_begin,twirl_end)]
    ranges.sort(key=lambda r:r[1])
    assert all(a<b for _,a,b in ranges) and max(b for _,a,b in ranges)<=0x0800
    for left,right in zip(ranges,ranges[1:]):
        assert left[2]<=right[1],('CPU scratch overlap',left,right)

def verify(base,source):
    rom=(base/'adofai.sfc').read_bytes();pack=json.loads((base/'pack.json').read_text())
    loc=json.loads((base/'placements.json').read_text())
    build_flags=(base/'addresses.inc').read_text()
    msu_charts='MSU_CHART_TABLES = 1' in build_flags
    compressed_times='COMPRESSED_STREAM_INDEX = 1' in build_flags
    msu_descriptors=(base/'msu_descriptors.bin').read_bytes() if msu_charts else b''
    labels={name:int(value,16) for value,name in re.findall(r'al ([0-9A-Fa-f]+) \.([\w]+)',(base/'adofai.lbl').read_text())}
    if 'neo_twirl_state_begin' in labels:
        verify_cpu_scratch(labels['neo_twirl_state_begin'],labels['neo_twirl_state_end'])
        assert labels['neo_twirl_state_end']<=labels['__FASTNMI_RUN__']
    assert len(rom)==0x800000
    assert rom[0x7fd5:0x7fd8]==bytes([0x23,0x35,0x0d]) and rom[0x7fd8] in (7,8),rom[0x7fd5:0x7fd9]
    inverse,checksum=struct.unpack_from('<HH',rom,0x7fdc)
    assert inverse^checksum==65535 and sum(rom)&65535==checksum
    worker=(base/'sa1_worker.bin').read_bytes()
    assert len(worker) in (0x7000,0x8000)
    assert rom[0x8000:0x8000+len(worker)]==worker
    camera_state=('M7_RASTER_SHIFT','M7_RASTER_X','M7_RASTER_Y','M7_RASTER_DISPLAY_X','M7_RASTER_DISPLAY_Y','M7_ORIGIN_X','M7_ORIGIN_Y')
    diagnostics=('VBLANK_DIAG_ROWS','VBLANK_DIAG_SPAN','VBLANK_DIAG_SLOTS','VBLANK_DIAG_LIMIT')
    constants={name:int(value,16) for name,value in re.findall(r'^(\w+)=\$([0-9A-Fa-f]+)$',(base/'sa1_layout.inc').read_text(),re.M)}
    if all(name in constants for name in diagnostics):
        addresses=[constants[name] for name in (*camera_state,*diagnostics)]
        assert len(set(addresses))==len(addresses),'VBlank diagnostics overlap live camera state'
        assert all(0x41FCD0<=address<0x41FD00 and address%2==0 for address in addresses)
    helper_mirror='SA1_FASTROM_HELPERS = 1' in (base/'addresses.inc').read_text()
    if 'symbol_scale_frames' in loc:
        at=loc['symbol_scale_frames'];at=at-0xc00000 if at>=0xc00000 else at
        data=(base/'symbol_scale_frames.bin').read_bytes()
        assert rom[at:at+len(data)]==data,'Scaled symbol artwork differs from source'
        assert (at&65535)+len(data)<=65536,'Scaled symbol artwork crosses ROM bank'
    unmirror=lambda a:a&0x7fffff if helper_mirror else a
    if helper_mirror:
        code_size=re.search(r'NEO_CODE_BYTES = \$([0-9A-Fa-f]+)',(base/'addresses.inc').read_text())
        helper_end=0x10000+(int(code_size[1],16) if code_size else 0x2000)
        assert rom[0x20f000:0x200000+helper_end]==rom[0xf000:helper_end]
        assert 0x81f000<=labels['mode7_rotation_bounds']<0x820000
    if 'STREAM_ROUTE_LEFT' in constants:
        assert 0x42bc70<=constants['STREAM_ROUTE_BEGIN']<=constants['STREAM_ROUTE_LEFT']<0x42c000
        assert constants['STREAM_OAM_DIRECT']+2<=constants['STREAM_ROUTE_BEGIN']
        snapshot=constants['STREAM_SPILL_SNAPSHOT']
        assert constants['STREAM_DELTA_TARGET']+512<=snapshot
        assert constants['STREAM_SPILL_PALETTE_DIRTY']+2<=snapshot
        assert snapshot+512<=constants['STREAM_BUFFER']
    if '__FASTNMI_RUN__' in labels:
        for name in ('mode7_rotation_bounds','camera_scale_sprite'):
            assert 0x01F000<=unmirror(labels[name])<0x020000,(name,labels[name])
        projection=unmirror(labels['mode7_rotate_project'])
        assert labels['__FASTWRAM_RUN__']<=projection<0x1800 or 0x01f000<=projection<0x020000
        assert labels['__FASTNMI_RUN__']<=labels['camera_scale_offset']<labels['__FASTNMI_RUN__']+labels['__FASTNMI_SIZE__']
    nmi_start=labels['__FASTNMI_RUN__']
    nmi_end=labels['__FASTWRAM_RUN__'] if nmi_start==0x0800 else 0x3780
    assert nmi_start in (0x0800,0x3100) and nmi_start+labels['__FASTNMI_SIZE__']<=nmi_end
    assert 0x0e00<=labels['__FASTWRAM_RUN__'] and labels['__FASTWRAM_RUN__']+labels['__FASTWRAM_SIZE__']<=0x1800
    assert 0x01F000<=unmirror(labels['__FASTWRAM_LOAD__']) and unmirror(labels['__FASTWRAM_LOAD__'])+labels['__FASTWRAM_SIZE__']<=0x020000
    if labels.get('NOTE_X') == 0x7F8000:
        extended=labels.get('MAX_NOTE_CAPACITY',4352)>4352
        size=labels.get('MAX_NOTE_CAPACITY',4352)*2
        assert labels['NOTE_Y'] == (0x7FA800 if extended else 0x7FA200) and labels['M7_CHR_HIGH'] == 0x7F6800
        run=labels.get('M7_RUN_VALUES',0x7FC880)
        low_bytes=labels['M7_CHR_LOW_BYTES'];high_bytes=labels['M7_CHR_HIGH_BYTES']
        assert low_bytes+high_bytes==16384 and low_bytes==64*labels['M7_CHR_LOW_SLOTS']
        assert (labels['M7_CHR_LOW']&65535)+low_bytes<=65536,'Legacy CHR DMA wraps into CPU state'
        assert labels['M7_CHR_HIGH']+high_bytes<=0x7F7C00,'Legacy CHR shadow overlaps audio FIFO'
        ranges=[(0x7F0000,0x7F6600),(0x7F6800,0x7F6800+high_bytes),(0x7F7C00,0x7F8000),
                (labels['NOTE_X'],labels['NOTE_X']+size),
                (labels['NOTE_Y'],labels['NOTE_Y']+size),(run,run+128),(0x7FD800,0x7FDC00)]
        assert all(a[1]<=b[0] for a,b in zip(ranges,ranges[1:])), ranges
        if extended:
            count=labels['MAX_NOTE_CAPACITY'];symbols=labels['MAX_SYMBOL_CAPACITY']
            ram=[(labels[name],labels[name]+count*stride) for name,stride in
                 [('NOTE_TIME',2),('NOTE_ANGLE',1),('NOTE_FLAGS',1),('NOTE_RATE',2),
                  ('NOTE_PROGRESS',1),('NOTE_CCW',1),('FLOOR_ALPHA',1)]]
            ram += [(labels[name],labels[name]+span) for name,span in
                    [('M7_CHR_LOW',2048),('CELL_HASH_HEAD',2048),('CELL_HASH_NEXT',2048),('PATTERN_QUEUE_LOOKUP',1024)]]
            assert all(a[1]<=b[0] for a,b in zip(ram,ram[1:])) and ram[-1][1]<=0x7F0000,ram
            assert labels['TRACK_SYMBOL_FLOORS']+symbols*2<=labels['NOTE_PAUSE']
            assert labels['NOTE_PAUSE']+count*2<=labels['NOTE_JUDGMENTS']
            assert labels['NOTE_JUDGMENTS']+count<=0x410000
            assert labels['SYMBOL_X']+count*2<=labels['SYMBOL_Y']
            assert labels['SYMBOL_Y']+count*2<=labels['SYMBOL_VISIBLE']
            assert labels['SYMBOL_VISIBLE']+symbols*2<=0x416600
            assert labels['SYMBOL_SCREEN_X']+symbols*2<=labels['SYMBOL_SCREEN_Y']
            assert labels['SYMBOL_SCREEN_Y']+symbols*2<=0x43EF00
            if 'SNAPSHOT_ICON_INFO' in labels:
                assert labels['SYMBOL_SCREEN_Y']+symbols*2<=labels['SNAPSHOT_ICON_INFO']
                assert labels['SNAPSHOT_ICON_INFO']+count<=0x43E800
                # Largest independent LZ4 pose: header + 640 CHR chunks.
                assert 0x422000+1312+640*32<=labels['SNAPSHOT_ICON_PREFIX']
                assert labels['SNAPSHOT_ICON_PREFIX']+544<=0x428000
            assert 0x408200<=labels['NATIVE_ALPHA'] and labels['NATIVE_ALPHA']+count<=labels['TRACK_SYMBOL_FLOORS']
            assert labels['NATIVE_READY']==0x42B200
    offset=lambda addr:addr-0xc00000 if addr>=0xc00000 else addr
    checked=0;crossings=[]
    meter={name:int(value,16) for name,value in re.findall(r'(METER_\w+)=\$([0-9A-Fa-f]+)',(base/'game.lst').read_text())}
    if 'METER_HISTORY' in meter:
        assert meter['METER_HISTORY']+512*4<=meter['METER_PIXELS']
        assert meter['METER_PIXELS']+34<=meter['METER_LAST_PIXELS']
        assert meter['METER_LAST_PIXELS']+34<=0x404000
        assert 0x7FDC82<=meter['METER_BITMAP'] and meter['METER_BITMAP']+272<=0x7FE000
    for n in pack['levels']:
        chart=json.loads((base/f'level{n}.json').read_text())
        if 'symbol_scale_frames' in loc and chart.get('mode1_tracks')!=3:
            assert not chart.get('neo_cosmos') and all(q.get('planets',2)==2 and q.get('hold_length',-1)<0 for q in chart['notes']),(n,'Legacy symbol cache aliases active Neo graphics')
        if labels.get('MAX_NOTE_CAPACITY',4352)>4352:
            assert len(chart['notes'])<=labels['MAX_NOTE_CAPACITY']
            assert sum(not(q['flags']&128) and bool(q['flags']&119) for q in chart['notes'])<=labels['MAX_SYMBOL_CAPACITY']
        if 'stream_vfx_off_descriptors' in loc:
            row=pack['levels'].index(n)*32
            on=offset(loc['stream_descriptors'])+row
            off=offset(loc['stream_vfx_off_descriptors'])+row
            if chart.get('sa1_stream_format'):
                count,index,stream=struct.unpack_from('<HII',rom,on+2)
                assert (count,index,stream)==(chart['stream_packets'],loc[f'stream_index{n}'],chart['stream_msu_base'])
                seed=struct.unpack_from('<H',rom,on+14)[0]+(struct.unpack_from('<H',rom,on+18)[0]<<16)
                assert seed==chart.get('mode1_seed_base',0)
            if not chart.get('vfx_off'):
                assert rom[on:on+32]==rom[off:off+32],(n,'VFX toggle changed gameplay-only chart')
            else:
                assert n not in (68,73),'T3 gameplay effects must remain enabled'
                alt=chart['vfx_off']
                count,index,stream=struct.unpack_from('<HII',rom,off+2)
                assert (count,index,stream)==(alt['stream_packets'],loc[f'stream_index_vfx_off{n}'],alt['stream_msu_base'])
                seed=struct.unpack_from('<H',rom,off+14)[0]+(struct.unpack_from('<H',rom,off+18)[0]<<16)
                assert seed==alt['mode1_seed_base']
            checked+=1
        if labels.get('NOTE_X') == 0x7F8000:
            assert chart['visibility_cells'] <= 0x6600, (n, 'Cell state overlaps relocated CHR shadow')
        if chart.get('projection_source_only'):
            assert chart.get('mode1_snapshot') and not chart.get('snapshot_preview'),'Host-only pattern IDs cannot reach the old runtime'
        else:assert len((base/f'patterns{n}.bin').read_bytes())//64<=0xFE00,'Pattern IDs overlap checkpoint identities'
        for prefix in ('resident_raw','resident_future','resident_animation'):
            name=f'{prefix}{n}'
            if name not in loc:continue
            expected=(source/f'{name}.bin').read_bytes();start=offset(loc[name])
            assert rom[start:start+len(expected)]==expected,(n,prefix,start)
            checked+=1
        for prefix in ('chart','track_chr','track_map','visibility_index'):
            expected=(base/f'{prefix}{n}.bin').read_bytes();start=offset(loc[f'{prefix}{n}'])
            if prefix=='chart' and msu_charts:
                assert len(expected)==14*len(chart['notes'])
                descriptor=msu_descriptors[pack['levels'].index(n)*24:][:24]
                chart_offset=struct.unpack_from('<I',descriptor,20)[0]
                assert chart_offset>=32
                with (base/'adofai.msu').open('rb') as data:
                    data.seek(chart_offset)
                    assert data.read(len(expected))==expected,(n,'MSU chart arrays',chart_offset)
                checked+=1
                expected=bytes(2)
            if prefix=='track_map' and chart.get('mode1_snapshot') and 'SNAPSHOT_ONLY_MAPS = 1' in (base/'addresses.inc').read_text():
                assert not chart.get('fallback_stream_packets') and not chart.get('snapshot_preview')
                desc=(base/'descriptors.bin').read_bytes()[pack['levels'].index(n)*32:][:32]
                assert struct.unpack_from('<HH',desc,22)==(2,0),'Snapshot-only ROM still advertises a legacy map'
                expected=bytes(2)
            if prefix=='chart' and (base/'zero-pauses.json').exists() and json.loads((base/'zero-pauses.json').read_text()).get(str(n)):
                count=len(chart['notes']);assert not any(expected[-count*2:]);expected=expected[:-count*2]
            if prefix=='visibility_index' and chart.get('mode1_snapshot') and 'SNAPSHOT_ONLY_COORDS = 1' in (base/'addresses.inc').read_text():
                assert not chart.get('fallback_stream_packets') and not chart.get('snapshot_preview')
                expected=bytes(2)
            assert 0x10000<=start and start+len(expected)<=(0x300000 if pack.get('standalone') else 0x400000)
            assert rom[start:start+len(expected)]==expected,(n,prefix,start)
            checked+=1
        if compressed_times and chart.get('sa1_stream_format'):
            from sa1_stream import rom_index,unpack_time_index
            original=(base/f'stream_index{n}.bin').read_bytes()
            encoded=rom_index(original,compressed=True)
            start=offset(loc[f'stream_index{n}'])
            actual=rom[start:start+len(encoded)]
            assert actual==encoded,(n,'Compressed timestamp bytes')
            assert unpack_time_index(actual,len(original)//8)==rom_index(original)
            assert start%2==0,(n,'Unaligned timestamp word')
            checked+=1
        if not pack.get('standalone'):continue
        from animation_bulk import batch
        expected_stream=batch((source/f'animation{n}.bin').read_bytes())[0]
        snapshot_mapping=None
        source_chart=json.loads((source/f'level{n}.json').read_text())
        if chart.get('catchup_format') and not source_chart.get('catchup_format'):
            from animation_catchup import compile_stream
            expected_stream,snapshot_mapping,_=compile_stream(expected_stream,chart)
        if chart.get('compiled_reference_sets'):
            from animation_sparse import batch_sparse
            expected_stream=batch_sparse(expected_stream,chart)[0]
        for suffix,name in [('music',f'level{n}.brr'),('animation',f'animation{n}.bin')]+[(f'cp{i}',f'animation{n}-checkpoint-{i}.bin') for i in range(len(chart['checkpoints']))]:
            expected=(source/name).read_bytes();start=offset(loc[f'romdata{n}_{suffix}'])
            if suffix=='animation':
                expected=expected_stream
            elif suffix.startswith('cp') and snapshot_mapping is not None:
                expected=bytearray(expected);cursor=struct.unpack_from('<I',expected,4)[0]
                struct.pack_into('<I',expected,4,snapshot_mapping[cursor])
            assert rom[start:start+len(expected)]==expected,(n,suffix,hex(start),'embedded data differs from source')
            if start//0x100000!=(start+len(expected)-1)//0x100000:crossings.append([n,suffix,start,len(expected)])
            checked+=1
        if pack.get('fast_audio_rate'):
            fast=(base/f'level{n}-fast.brr').read_bytes();start=offset(loc[f'romdata{n}_fastmusic'])
            assert rom[start:start+len(fast)]==fast
            assert loc[f'fastseeks{n}']<0xF00000 and loc[f'fastseeks{n}']>=0xC00000
            seeks=[round(cp['block']*pack['fast_audio_rate']/12000)*9 for cp in chart['checkpoints']]
            assert all((fast[pos]&12)==0 for pos in seeks),'BRR checkpoint must reset prediction'
            expected=b''.join(struct.pack('<I',pos) for pos in seeks) or bytes(4)
            start=offset(loc[f'fastseeks{n}']);assert rom[start:start+len(expected)]==expected
            descriptor=(base/'msu_descriptors.bin').read_bytes()[pack['levels'].index(n)*24:][:24]
            assert struct.unpack_from('<I',descriptor,4)[0]==offset(loc[f'romdata{n}_fastmusic'])
            assert struct.unpack_from('<I',descriptor,20)[0]==loc[f'fastseeks{n}']
            checked+=2
        pointers=struct.pack('<'+'I'*len(chart['checkpoints']),*[offset(loc[f'romdata{n}_cp{i}']) for i in range(len(chart['checkpoints']))])
        start=offset(loc[f'romdata{n}_table']);assert rom[start:start+len(pointers)]==pointers
    if 'level_titles' in loc:
        from campaign_assets import title_text
        expected=b''.join(title_text(json.loads((base/f'level{n}.json').read_text())).encode('ascii').ljust(29,b'\0') for n in pack['levels'])
        start=offset(loc['level_titles']);assert rom[start:start+len(expected)]==expected,'Banked menu titles differ from the catalog'
        checked+=1
    report=dict(passed=True,**identity(base/'adofai.sfc'),checked_blobs=checked,window_crossings=crossings,iram_code_bytes=labels['__FASTNMI_SIZE__'])
    (base/'verification').mkdir(exist_ok=True);(base/'verification/sa1-layout.json').write_text(json.dumps(report,indent=2))
    print(base.name,checked,'blobs match;',len(crossings),'1 MiB window crossings',flush=True)
    return report

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--pack',default='sa1-release');ap.add_argument('--standalone',action='store_true')
    ap.add_argument('--source',type=Path,default=ROOT/'build/packs/sa1-release');ap.add_argument('--catalog',type=Path,default=ROOT/'build/sa1-standalone-catalog.json');args=ap.parse_args()
    source=args.source.resolve()
    packs=[r['key'] for r in json.loads(args.catalog.read_text())['roms']] if args.standalone else [args.pack]
    for name in packs:verify(ROOT/'build/packs'/name,source)

if __name__=='__main__':main()
