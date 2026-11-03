"""Check SA-1 mappings and embedded bytes independently of emulator playback."""
import argparse,json,re,struct
from pathlib import Path
from verification_data import identity
ROOT=Path(__file__).resolve().parents[1]

def verify(base,source):
    rom=(base/'adofai.sfc').read_bytes();pack=json.loads((base/'pack.json').read_text())
    loc=json.loads((base/'placements.json').read_text())
    labels={name:int(value,16) for value,name in re.findall(r'al ([0-9A-Fa-f]+) \.([\w]+)',(base/'adofai.lbl').read_text())}
    assert len(rom)==0x800000
    assert rom[0x7fd5:0x7fd9]==bytes([0x23,0x35,0x0d,7]),rom[0x7fd5:0x7fd9]
    inverse,checksum=struct.unpack_from('<HH',rom,0x7fdc)
    assert inverse^checksum==65535 and sum(rom)&65535==checksum
    worker=(base/'sa1_worker.bin').read_bytes()
    assert len(worker) in (0x7000,0x8000)
    assert rom[0x8000:0x8000+len(worker)]==worker
    if len(worker)==0x7000:
        for name in ('mode7_rotation_bounds','camera_scale_sprite'):
            assert 0x01F000<=labels[name]<0x020000,(name,labels[name])
        assert 0x1000<=labels['mode7_rotate_project']<0x1800
        assert 0x3100<=labels['camera_scale_offset']<0x3780
    assert 0x3100<=labels['__FASTNMI_RUN__'] and labels['__FASTNMI_RUN__']+labels['__FASTNMI_SIZE__']<=0x3780
    assert 0x1000<=labels['__FASTWRAM_RUN__'] and labels['__FASTWRAM_RUN__']+labels['__FASTWRAM_SIZE__']<=0x1800
    assert 0x01F000<=labels['__FASTWRAM_LOAD__'] and labels['__FASTWRAM_LOAD__']+labels['__FASTWRAM_SIZE__']<=0x020000
    if labels.get('NOTE_X') == 0x7F8000:
        assert labels['NOTE_Y'] == 0x7FA200 and labels['M7_CHR_HIGH'] == 0x7F6800
        ranges=[(0x7F0000,0x7F6600),(0x7F6800,0x7F7000),(0x7F7C00,0x7F8000),
                (labels['NOTE_X'],labels['NOTE_X']+0x2200),
                (labels['NOTE_Y'],labels['NOTE_Y']+0x2200),(0x7FC880,0x7FC900)]
        assert all(a[1]<=b[0] for a,b in zip(ranges,ranges[1:])), ranges
    offset=lambda addr:addr-0xc00000 if addr>=0xc00000 else addr
    checked=0;crossings=[]
    for n in pack['levels']:
        chart=json.loads((base/f'level{n}.json').read_text())
        if labels.get('NOTE_X') == 0x7F8000:
            assert chart['visibility_cells'] <= 0x6600, (n, 'Cell state overlaps relocated CHR shadow')
        assert len((base/f'patterns{n}.bin').read_bytes())//64<=0xFE00,'Pattern IDs overlap checkpoint identities'
        for prefix in ('chart','track_chr','track_map','visibility_index'):
            expected=(base/f'{prefix}{n}.bin').read_bytes();start=offset(loc[f'{prefix}{n}'])
            if prefix=='chart' and (base/'zero-pauses.json').exists() and json.loads((base/'zero-pauses.json').read_text()).get(str(n)):
                count=len(chart['notes']);assert not any(expected[-count*2:]);expected=expected[:-count*2]
            assert 0x10000<=start and start+len(expected)<=(0x300000 if pack.get('standalone') else 0x400000)
            assert rom[start:start+len(expected)]==expected,(n,prefix,start)
            checked+=1
        if not pack.get('standalone'):continue
        for suffix,name in [('music',f'level{n}.brr'),('animation',f'animation{n}.bin')]+[(f'cp{i}',f'animation{n}-checkpoint-{i}.bin') for i in range(len(chart['checkpoints']))]:
            expected=(source/name).read_bytes();start=offset(loc[f'romdata{n}_{suffix}'])
            if suffix=='animation':
                from animation_bulk import batch
                expected=batch(expected)[0]
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
