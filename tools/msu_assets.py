"""MSU-1 data and 44.1 kHz signed stereo PCM, with checkpoint entry tracks."""
import hashlib,json,math,struct,subprocess
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
RATE=44100

def generate(out,charts,music,*,generate_pcm=True):
    descriptors=bytearray();manifest=[];stem=out/'adofai'
    with stem.with_suffix('.msu').open('wb') as data:
        data.write(b'ADOFAI-MSU1\0'+struct.pack('<H',20 if any(c["id"]>=62 for c in charts) else 19 if any(c.get('adaptive_raster') for c in charts) else 18 if any(c.get('mode7_zoom_enabled') for c in charts) else 17 if any(c.get('camera_position_events',0) for c in charts) else 16 if any(c.get('native_layout_version',0)>=2 for c in charts) else 15 if any(c.get('track_separators_version') for c in charts) else 14 if any(c.get('opacity_curve_version') for c in charts) else 13 if any(c.get('camera_rotation_versions') for c in charts) else 12)+bytes(18))
        for c in charts:
            n=c['id'];offset=data.tell();data.write(music[n]);track=n
            animation_offset=data.tell();data.write((out/f'animation{n}.bin').read_bytes())
            # Sequential animation and the ROM coordinate index replace the
            # old random-access timelines. Retain the descriptor field.
            timeline_offset=data.tell();data.write(bytes(2))
            table_offset=data.tell();data.write(bytes(4*len(c['checkpoints'])))
            snapshots=[]
            for i,cp in enumerate(c['checkpoints']):
                snapshots.append(data.tell());data.write((out/f'animation{n}-checkpoint-{i}.bin').read_bytes())
            end=data.tell();data.seek(table_offset)
            data.write(b''.join(struct.pack('<I',s) for s in snapshots));data.seek(end)
            descriptors+=struct.pack('<IHHIIHHI',offset,track,1000+n*32,animation_offset,table_offset,c.get('visibility_cells',0),int(bool(c.get('pattern_versions'))),timeline_offset)
            if c.get('sa1_stream_format'):
                c['stream_msu_base']=data.tell()
                data.write((out/f'stream_data{n}.bin').read_bytes())
                if c.get('mode1_tracks'):
                    if not c.get('mode1_projected'):
                        c['mode1_icon_base']=data.tell()
                        data.write((out/f'mode1_icons{n}.bin').read_bytes())
                    c['mode1_seed_base']=data.tell()
                    data.write((out/f'mode1_seeds{n}.bin').read_bytes())
                    if c.get('fallback_stream_packets'):
                        c['fallback_stream_msu_base']=data.tell()
                        data.write((out/f'stream_data_fallback{n}.bin').read_bytes())
                (out/f'level{n}.json').write_text(json.dumps(c,indent=2))
            if not generate_pcm:
                manifest.append(dict(id=n,code=c['code'],title=c['title'],data_offset=offset,brr_bytes=len(music[n])))
                continue
            from embedded_hit_audio import mix_hits, fingerprint
            wav=ROOT/f'assets/private/{n}-X.wav'
            prefix=c['countdown']*60/c['bpm'] if c['separate_countdown'] else 0
            settings=dict(source=hashlib.sha256(wav.read_bytes()).hexdigest(),percussion_mix=fingerprint(c),prefix=prefix,end=c['duration'],offset=c['offset'],checkpoints=c['checkpoints'],format=1)
            stamp=out/f'msu-{n}.json';targets=[(track,0)]+[(1000+n*32+i,cp['block']*16/12000) for i,cp in enumerate(c['checkpoints'])]
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
            manifest.append(dict(id=n,code=c['code'],title=c['title'],data_offset=offset,brr_bytes=len(music[n]),tracks=[dict(track=t,origin_seconds=s,bytes=(out/f'adofai-{t}.pcm').stat().st_size) for t,s in targets]))
            print(c['code'],len(targets),'PCM entries',flush=True)
    (out/'msu_descriptors.bin').write_bytes(descriptors)
    (out/'msu-manifest.json').write_text(json.dumps(dict(format='MSU1 44100 Hz signed 16-bit stereo',normal_speed='PCM',other_speeds='12 kHz BRR from MSU data',levels=manifest),indent=2))
