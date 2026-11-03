"""Screen every source song for hit samples already embedded in the music.

Correlation is a review signal, not authorization to remove unmatched sounds.
The complete matching waveform and a stable lag across many notes matter;
comparing the tallest music peak with the tallest sample peak is insufficient.
"""
import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

import numpy as np
from scipy.io import wavfile
from scipy.signal import correlate, resample_poly

from hit_sound_assets import selections

ROOT = Path(__file__).resolve().parents[1]
RATE = 8000


def mono(path):
    rate, audio = wavfile.read(path)
    audio = audio.astype(float)
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    return resample_poly(audio, RATE, rate)


def audit(base, out):
    catalog = json.loads((base/'pack.json').read_text())['levels']
    sources = json.loads((ROOT/'assets/private/hitsound-levels.json').read_text())
    offsets = json.loads((ROOT/'assets/audio/hit-sound-offsets.json').read_text())
    templates = {}
    rows = []
    for level in catalog:
        chart = json.loads((base/f'level{level}.json').read_text())
        source = ROOT/f'assets/private/{level}-X.wav'
        music = mono(source)
        prefix = chart['countdown']*60/chart['bpm'] if chart['separate_countdown'] else 0
        matches = []
        checked = 0
        for note, (sound, volume) in zip(chart['notes'][1:], selections(chart,sources[str(level)])[1:]):
            if note['flags'] & 8 or sound == 'None' or not volume:
                continue
            if sound not in templates:
                template = mono(ROOT/f'assets/private/hitsounds/snd{sound}.wav')[:round(.18*RATE)]
                templates[sound] = (template, float(np.dot(template,template)))
            template, energy = templates[sound]
            second = note['time']-prefix
            scheduled = second-offsets.get(sound,0)
            start = round((scheduled-.1)*RATE)
            stop = round((scheduled+.1)*RATE)+len(template)
            if start < 0 or stop > len(music) or energy == 0:
                continue
            candidate = music[start:stop]
            correlation = correlate(candidate,template,mode='valid',method='fft')
            cumulative = np.r_[0,np.cumsum(candidate*candidate)]
            local_energy = cumulative[len(template):]-cumulative[:-len(template)]
            scores = correlation/np.sqrt(np.maximum(local_energy*energy,1))
            peak = int(np.argmax(scores))
            score = float(scores[peak])
            checked += 1
            if score >= .85:
                matches.append(dict(note=note['step'],sound=sound,time=second,
                                    lag_ms=((start+peak)/RATE-second)*1000,
                                    score=score,gain=float(correlation[peak]/energy)))
        clusters = Counter((m['sound'],round(m['lag_ms'])) for m in matches)
        strongest = [dict(sound=s,lag_ms=lag,count=count) for (s,lag),count in clusters.most_common(5)]
        rows.append(dict(level=level,code=chart['code'],checked=checked,matches=matches,
                         strongest_clusters=strongest,source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                         review='potential embedded percussion' if len(matches)>=5 else 'no repeated strong match detected'))
        out.write_text(json.dumps(dict(completed=len(rows)==len(catalog),levels=rows,
            scope='All hittable notes screened against their selected original sample within +/-100 ms of the original sample-specific scheduled time. Strong matches require review; absence of matches does not establish runtime timing.'),indent=2))
        print(chart['code'],checked,'notes;',len(matches),'strong matches;',strongest[:2],flush=True)
    return rows


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--base',type=Path,default=ROOT/'build/packs/sa1-scheduled-hits')
    parser.add_argument('--out',type=Path,default=ROOT/'build/all-song-hit-audit.json')
    args = parser.parse_args()
    audit(args.base,args.out)
