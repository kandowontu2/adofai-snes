"""Measure shipped PCM/BRR alignment against the author's decoded music.

This checks assets, not emulator output latency. Added hit sounds are treated
as interference; several independent music windows must agree on the delay.
"""
import argparse
import json
import subprocess
from pathlib import Path

import numpy as np
from scipy.signal import correlate, resample_poly
from scipy.io import wavfile

from check_campaign_audio import decode_brr
from import_featured import read_chart

ROOT = Path(__file__).resolve().parents[1]
RATE = 12000


def alignment(reference, encoded, prefix, times):
    rows = []
    margin = RATE // 5
    for seconds in times:
        start = round(seconds * RATE)
        sample = reference[start:start + RATE * 3]
        at = start + round(prefix * RATE)
        window = encoded[at-margin:at+len(sample)+margin]
        if len(sample) != RATE * 3 or len(window) != len(sample)+2*margin:
            continue
        a = sample - sample.mean()
        b = window - window.mean()
        scores = correlate(b, a, mode='valid', method='fft')
        index = int(np.argmax(scores))
        selected = b[index:index+len(a)]
        correlation = float(np.dot(a, selected) / np.sqrt(np.dot(a, a)*np.dot(selected, selected)))
        rows.append(dict(source_seconds=seconds, delay_ms=(index-margin)*1000/RATE,
                         correlation=correlation))
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--pack', type=Path, required=True)
    ap.add_argument('--level', type=int, required=True)
    ap.add_argument('--pcm-folder', type=Path)
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    data = json.loads((ROOT/f'assets/private/level{args.level}.json').read_text())
    chart = json.loads((args.pack/f'level{args.level}.json').read_text())
    native, _ = read_chart(Path(data['source']))
    source = Path(data['source']).parent/native['settings']['songFilename']
    decoded = subprocess.check_output(['ffmpeg', '-v', 'error', '-i', str(source),
                                      '-f', 's16le', '-ac', '1', '-ar', str(RATE), '-'])
    reference = np.frombuffer(decoded, dtype='<i2').astype(float)
    rate, imported = wavfile.read(ROOT/f'assets/private/{args.level}-X.wav')
    imported = imported.astype(float)
    if imported.ndim > 1:
        imported = imported.mean(axis=1)
    imported = resample_poly(imported, RATE, rate)
    prefix = chart['countdown']*60/chart['bpm'] if chart['separate_countdown'] else 0
    times = np.linspace(3, len(reference)/RATE-6, 12).tolist()
    result = dict(level=args.level, native_offset_ms=native['settings']['offset'],
                  imported_offset_ms=data['offset']*1000, compiled_offset_ms=chart['offset']*1000,
                  prefix_seconds=prefix, scope='Asset alignment; emulator latency not measured',
                  imported=alignment(reference, imported, 0, times))
    brr = (args.pack/f'level{args.level}.brr').read_bytes()
    result['brr'] = alignment(reference, decode_brr(brr), prefix, times)
    pcm = (args.pcm_folder or args.pack)/f'adofai-{args.level}.pcm'
    if pcm.exists():
        raw = np.fromfile(pcm, dtype='<i2', offset=8).reshape(-1, 2).mean(axis=1)
        result['pcm'] = alignment(reference, resample_poly(raw, RATE, 44100), prefix, times)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
