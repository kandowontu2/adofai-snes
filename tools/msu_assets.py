"""MSU-1 data and optional song-start PCM for the hybrid edition."""
import hashlib,json,math,struct,subprocess,tempfile
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
RATE=44100

def checkpoint_track_base(level):
    # Preserve released track numbers. Overclocked has 34 checkpoints and
    # extends past its old 32-track slot; new charts use a separate 64-slot area.
    base=1000+level*32 if level<=284 else 12000+(level-285)*64
    assert base<=65535,'MSU track number capacity'
    return base

def validate_track_numbers(charts):
    used={}
    for chart in charts:
        n=chart['id'];base=checkpoint_track_base(n)
        for track in [n,*range(base,base+len(chart['checkpoints']))]:
            assert 0<track<=65535 and track not in used,('Overlapping MSU tracks',track,used.get(track),n)
            used[track]=n

def generate(out,charts,music,*,generate_pcm=True,extended_catalog=False):
    extended_catalog=extended_catalog or len(charts)>=200
    validate_track_numbers(charts)
    descriptors=bytearray();manifest=[];stem=out/'adofai'
    from msu_snapshot_pool import SnapshotPool
    with tempfile.TemporaryFile(dir=out) as scratch,stem.with_suffix('.msu').open('w+b') as data:
        shared=SnapshotPool(scratch)
        data.write(b'ADOFAI-MSU1\0'+struct.pack('<H',21 if extended_catalog else 20 if any(c["id"]>=62 for c in charts) else 19 if any(c.get('adaptive_raster') for c in charts) else 18 if any(c.get('mode7_zoom_enabled') for c in charts) else 17 if any(c.get('camera_position_events',0) for c in charts) else 16 if any(c.get('native_layout_version',0)>=2 for c in charts) else 15 if any(c.get('track_separators_version') for c in charts) else 14 if any(c.get('opacity_curve_version') for c in charts) else 13 if any(c.get('camera_rotation_versions') for c in charts) else 12)+bytes(18))
        for c in charts:
            n=c['id'];offset=data.tell();data.write(music[n]);track=n
            animation_offset=data.tell();data.write((out/f'animation{n}.bin').read_bytes())
            # Sequential animation and the ROM coordinate index replace the
            # old random-access timelines. Retain the descriptor field.
            timeline_offset=data.tell();data.write((out/f'chart{n}.bin').read_bytes() if extended_catalog else bytes(2))
            table_offset=data.tell();data.write(bytes(4*len(c['checkpoints'])))
            snapshots=[]
            for i,cp in enumerate(c['checkpoints']):
                snapshots.append(data.tell());data.write((out/f'animation{n}-checkpoint-{i}.bin').read_bytes())
            end=data.tell();data.seek(table_offset)
            data.write(b''.join(struct.pack('<I',s) for s in snapshots));data.seek(end)
            descriptors+=struct.pack('<IHHIIHHI',offset,track,checkpoint_track_base(n),animation_offset,table_offset,c.get('visibility_cells',0),int(bool(c.get('pattern_versions'))),timeline_offset)
            if c.get('sa1_stream_format'):
                if c.get('mode1_snapshot') and c.get('compact_snapshot_seeds')==4:
                    def variant(meta,suffix=''):
                        meta['stream_msu_base'],meta['mode1_seed_base']=shared.write_variant(data,
                            (out/f'stream_index{suffix}{n}.bin').read_bytes(),
                            (out/f'stream_data{suffix}{n}.bin').read_bytes(),
                            (out/f'mode1_seeds{suffix}{n}.bin').read_bytes())
                    variant(c)
                    if c.get('vfx_off'):variant(c['vfx_off'],'_vfx_off')
                    assert not c.get('fallback_stream_packets'),'Snapshot pools require independent poses'
                    (out/f'level{n}.json').write_text(json.dumps(c,indent=2))
                else:
                    write_stream_assets(out,data,c,n)
            if not generate_pcm:
                manifest.append(dict(id=n,code=c['code'],title=c['title'],data_offset=offset,brr_bytes=len(music[n])))
                continue
            tracks=generate_pcm_tracks(out,c)
            manifest.append(dict(id=n,code=c['code'],title=c['title'],data_offset=offset,brr_bytes=len(music[n]),tracks=tracks))
            print(c['code'],len(tracks),'PCM entries',flush=True)
        sharing=shared.finish(data)
        (out/'msu-snapshot-sharing.json').write_text(json.dumps(sharing,indent=2))
    (out/'msu_descriptors.bin').write_bytes(descriptors)
    (out/'msu-manifest.json').write_text(json.dumps(dict(format='MSU1 44100 Hz signed 16-bit stereo',normal_speed='PCM',other_speeds='12 kHz BRR from MSU data',levels=manifest),indent=2))


def write_stream_assets(out,data,c,n):
    c['stream_msu_base']=data.tell()
    data.write((out/f'stream_data{n}.bin').read_bytes())
    if c.get('mode1_tracks'):
        if not c.get('mode1_projected'):
            c['mode1_icon_base']=data.tell()
            data.write((out/f'mode1_icons{n}.bin').read_bytes())
        c['mode1_seed_base']=data.tell()
        data.write((out/f'mode1_seeds{n}.bin').read_bytes())
        if c.get('vfx_off'):
            c['vfx_off']['stream_msu_base']=data.tell()
            data.write((out/f'stream_data_vfx_off{n}.bin').read_bytes())
            c['vfx_off']['mode1_seed_base']=data.tell()
            data.write((out/f'mode1_seeds_vfx_off{n}.bin').read_bytes())
        if c.get('fallback_stream_packets'):
            c['fallback_stream_msu_base']=data.tell()
            data.write((out/f'stream_data_fallback{n}.bin').read_bytes())
    (out/f'level{n}.json').write_text(json.dumps(c,indent=2))

def generate_pcm_tracks(out, c):
    """Generate hybrid song-start PCM; checkpoint retries use BRR."""
    n=c['id'];track=n
    from embedded_hit_audio import mix_hits, fingerprint
    wav=ROOT/f'assets/private/{n}-X.wav'
    prefix=c['countdown']*60/c['bpm'] if c['separate_countdown'] else 0
    settings=dict(source=hashlib.sha256(wav.read_bytes()).hexdigest(),percussion_mix=fingerprint(c),prefix=prefix,end=c['duration'],offset=c['offset'],checkpoints=c['checkpoints'],format=1)
    stamp=out/f'msu-{n}.json';targets=[(track,0)]
    if not(stamp.exists() and json.loads(stamp.read_text())==settings and all((out/f'adofai-{t}.pcm').exists() for t,_ in targets)):
        raw=out/f'msu-{n}.raw'
        subprocess.run(['ffmpeg','-v','error','-y','-i',str(wav),'-af','volume=0.78','-ac','2','-ar',str(RATE),'-f','s16le',str(raw)],check=True)
        pcm=np.fromfile(raw,dtype='<i2').reshape(-1,2).astype(float)
        pcm=np.vstack((np.zeros((round(prefix*RATE),2)),pcm))
        length=math.ceil(c['duration']*RATE)
        if len(pcm)<length:pcm=np.pad(pcm,((0,length-len(pcm)),(0,0)))
        if prefix:
            rng=np.random.default_rng(75);count=round(RATE*.045)
            hat=rng.uniform(-1,1,count)*np.exp(-np.arange(count)/(RATE*.008))*6500
            for k in range(c['countdown']):
                start=round((c['offset']+k*60/c['bpm'])*RATE)
                if start>=0:pcm[start:start+count]+=hat[:,None]
        hit_report=mix_hits(pcm,c,RATE)
        (out/f'level{n}-pcm-hit-mix.json').write_text(json.dumps(hit_report,indent=2))
        pcm=np.clip(pcm[:length],-32768,32767).astype('<i2')
        for t,start in targets:
            target=out/f'adofai-{t}.pcm'
            target.unlink(missing_ok=True)
            with target.open('wb') as f:
                f.write(b'MSU1'+struct.pack('<I',0));f.write(pcm[round(start*RATE):].tobytes())
        stamp.write_text(json.dumps(settings,indent=2))
        raw.unlink()
    return [dict(track=t,origin_seconds=start,bytes=(out/f'adofai-{t}.pcm').stat().st_size) for t,start in targets]
