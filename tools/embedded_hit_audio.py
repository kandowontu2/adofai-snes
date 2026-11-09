"""Mix scheduled hits at sample precision, reusing verified source-embedded hits."""
import hashlib
import json
import math
import re
import struct
import subprocess
from pathlib import Path

import numpy as np
from scipy.io import wavfile
from scipy.signal import resample_poly

ROOT = Path(__file__).resolve().parents[1]


def settings(level):
    return json.loads((ROOT/'assets/audio/hit-timing.json').read_text()).get(str(level), {})


def fingerprint(chart):
    from hit_sound_assets import selections
    source = json.loads((ROOT/'assets/private/hitsound-levels.json').read_text())[str(chart['id'])]
    selected = selections(chart, source)
    samples = {name:hashlib.sha256((ROOT/f'assets/private/hitsounds/snd{name}.wav').read_bytes()).hexdigest()
               for name, volume in selected if name != 'None' and volume}
    data = dict(version=2, settings=settings(chart['id']), samples=samples,
                offsets=json.loads((ROOT/'assets/audio/hit-sound-offsets.json').read_text()),
                notes=[(n['time'], n['flags'], selected[i]) for i,n in enumerate(chart['notes'])])
    return hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest()


def mix_hits(pcm, chart, rate):
    """Place each hit once, on the same sample clock as music (already at .78 gain)."""
    from hit_sound_assets import selections
    source = json.loads((ROOT/'assets/private/hitsound-levels.json').read_text())[str(chart['id'])]
    selected = selections(chart, source)
    config = settings(chart['id'])
    offsets = json.loads((ROOT/'assets/audio/hit-sound-offsets.json').read_text())
    if config.get('source_sha256'):
        original = ROOT/f'assets/private/{chart["id"]}-X.wav'
        assert hashlib.sha256(original.read_bytes()).hexdigest() == config['source_sha256']
    embedded = set(config.get('embedded_hit_notes', []))
    samples = {}
    inserted = []
    reused = []
    for note, (sound, volume) in zip(chart['notes'][1:], selected[1:]):
        if note['flags'] & 8 or sound == 'None' or not volume:
            continue
        if note['step'] in embedded:
            assert sound == config['sample']
            reused.append(note['step'])
            continue
        if sound not in samples:
            hit_rate, hit = wavfile.read(ROOT/f'assets/private/hitsounds/snd{sound}.wav')
            assert hit.dtype == np.int16
            hit = hit.astype(float)
            if hit.ndim > 1:
                hit = hit.mean(axis=1)
            samples[sound] = resample_poly(hit, rate, hit_rate)
        # Match the original sample-specific lead (real seconds at 1x), rather
        # than rounding it to SNES video frames. The embedded tracks use their
        # independently verified source alignment for the same sample.
        lead = offsets.get(sound, 0)
        gain = (volume//2)/112
        if sound == config.get('sample'):
            lead = -config['alignment_samples']/config['alignment_rate']
            gain = config['intro_gain']*.78*volume/76
        exact = (note['time']-lead)*rate
        start = round(exact)
        hit = samples[sound]*gain
        source_start = max(0,-start)
        target_start = max(0,start)
        count = min(len(hit)-source_start, len(pcm)-target_start)
        assert count > 0, ('Hit outside audio',chart['id'],note['step'])
        addition = hit[source_start:source_start+count]
        pcm[target_start:target_start+count] += addition[:,None] if pcm.ndim > 1 else addition
        inserted.append(dict(note=note['step'],sound=sound,start_sample=start,
                             rounding_error_samples=start-exact))
    gain = min(1.,32700/max(1.,float(np.max(abs(pcm)))))
    pcm *= gain
    return dict(fingerprint=fingerprint(chart),rate=rate,inserted=inserted,reused=reused,
                gain=gain,peak=float(np.max(abs(pcm))))


def file_offset(address):
    return address-0xC00000 if address >= 0xC00000 else address


def patch_pack(out, *, generate_pcm=True):
    """Upgrade frozen audio in place without changing the animation layout."""
    out = Path(out)
    pack = json.loads((out/'pack.json').read_text())
    levels = pack['levels']
    if not levels:
        return
    import campaign_assets as assets
    previous_out = assets.OUT
    assets.OUT = out
    try:
        descriptors = (out/'msu_descriptors.bin').read_bytes()
        placements = json.loads((out/'placements.json').read_text())
        for n in levels:
            chart = json.loads((out/f'level{n}.json').read_text())
            old = (out/f'level{n}.brr').read_bytes()
            updated = assets.encode_music(chart)
            assert len(old) == len(updated), 'Music patch would move animation data'
            if pack.get('standalone'):
                variants = [('music', updated)]
                if pack.get('fast_audio_rate'):
                    old_fast = (out/f'level{n}-fast.brr').read_bytes()
                    fast = assets.encode_music(chart, rate=pack['fast_audio_rate'], suffix='-fast')
                    assert len(old_fast) == len(fast)
                    variants.append(('fastmusic', fast))
                payload = out/'sa1_payload.bin'
                with payload.open('r+b') as f:
                    for suffix, blob in variants:
                        at = file_offset(placements[f'romdata{n}_{suffix}'])-0x10000
                        assert at >= 0 and at+len(blob) <= payload.stat().st_size
                        f.seek(at)
                        f.write(blob)
            else:
                at = struct.unpack_from('<I', descriptors, pack['levels'].index(n)*24)[0]
                with (out/'adofai.msu').open('r+b') as f:
                    f.seek(at)
                    existing = f.read(len(updated))
                    assert existing in (old, updated), 'Music descriptor does not match source bytes'
                    f.seek(at)
                    f.write(updated)
                if not generate_pcm:
                    continue
                # Rebuild only this PCM track, preserving every other song.
                pcm_root = out/'sample-clock-pcm'
                pcm_root.mkdir(exist_ok=True)
                targets = [(n,0)]+[(1000+n*32+i,cp['block']*16/12000) for i,cp in enumerate(chart['checkpoints'])]
                pcm_stamp = out/f'level{n}-pcm-mix-cache.json'
                pcm_key = dict(fingerprint=fingerprint(chart),duration=chart['duration'],
                               prefix=chart['countdown']*60/chart['bpm'] if chart['separate_countdown'] else 0,
                               targets=targets)
                if pcm_stamp.exists() and json.loads(pcm_stamp.read_text()) == json.loads(json.dumps(pcm_key)) and all((pcm_root/f'adofai-{track}.pcm').exists() for track,_ in targets):
                    continue
                source = ROOT/f'assets/private/{n}-X.wav'
                raw = out/f'embedded-{n}.raw'
                subprocess.run(['ffmpeg','-v','error','-y','-i',str(source),'-af','volume=0.78',
                                '-ac','2','-ar','44100','-f','s16le',str(raw)],check=True)
                pcm = np.fromfile(raw,dtype='<i2').reshape(-1,2)
                prefix = chart['countdown']*60/chart['bpm'] if chart['separate_countdown'] else 0
                pcm = np.vstack((np.zeros((round(prefix*44100),2)),pcm)).astype(float)
                length = math.ceil(chart['duration']*44100)
                if len(pcm) < length:
                    pcm = np.pad(pcm,((0,length-len(pcm)),(0,0)))
                if prefix:
                    rng = np.random.default_rng(75)
                    count = round(44100*.045)
                    hat = rng.uniform(-1,1,count)*np.exp(-np.arange(count)/(44100*.008))*6500
                    for k in range(chart['countdown']):
                        start = round((chart['offset']+k*60/chart['bpm'])*44100)
                        if start >= 0:
                            pcm[start:start+count] += hat[:,None]
                report = mix_hits(pcm, chart, 44100)
                (out/f'level{n}-pcm-hit-mix.json').write_text(json.dumps(report,indent=2))
                pcm = np.clip(pcm[:length],-32768,32767).astype('<i2')
                targets = [(n,0)]+[(1000+n*32+i,cp['block']*16/12000) for i,cp in enumerate(chart['checkpoints'])]
                for track, start in targets:
                    target = pcm_root/f'adofai-{track}.pcm'
                    temp = target.with_suffix('.pcm.new')
                    temp.write_bytes(b'MSU1'+bytes(4)+pcm[round(start*44100):].tobytes())
                    temp.replace(target)
                raw.unlink()
                pcm_stamp.write_text(json.dumps(pcm_key))
        if not pack.get('standalone'):
            with (out/'adofai.msu').open('r+b') as f:
                f.seek(12)
                f.write(struct.pack('<H',24))
            addresses = out/'addresses.inc'
            addresses.write_text(re.sub(r'MSU_DATA_VERSION = \d+', 'MSU_DATA_VERSION = 24', addresses.read_text()))
        addresses = out/'addresses.inc'
        text = addresses.read_text()
        if 'HITS_IN_MUSIC = 1' not in text:
            addresses.write_text(text+'\nHITS_IN_MUSIC = 1\n')
    finally:
        assets.OUT = previous_out
