"""Measure audible 1-X kick attacks against music, isolating DSP hit voices."""
import argparse
import ctypes as C
import json
from pathlib import Path

import numpy as np
from scipy.io import wavfile

from emulate import Emulator, ROOT
from input_helpers import press


def capture(base, out, mode, muted):
    em = Emulator(rom=base/'adofai.sfc', mute_taps=muted)
    try:
        for _ in range(120):
            em.run()
        press(em, 1 if mode == 'auto' else 9)
        press(em, 3)
        em.audio.clear()
        events = []
        count = 0
        for frame in range(850):
            em.run([8] if mode == 'manual' and frame % 19 == 0 else [])
            new = C.c_uint16.from_address(em.ram+0x1fc36).value
            if new != count:
                assert new == count+1, 'Duplicate or batched opening hit'
                events.append(sum(len(block)//4 for block in em.audio))
            count = new
        name = f'{mode}-{"music" if muted else "mix"}.wav'
        em.save_audio(out/name)
        return events, em.evidence()
    finally:
        em.close()


def check(base, out):
    assert json.loads((base/'pack.json').read_text())['levels'][0] == 1
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for mode in ('manual', 'auto'):
        events, evidence = capture(base, out, mode, False)
        muted_events, _ = capture(base, out, mode, True)
        assert events == muted_events
        rate, mix = wavfile.read(out/f'{mode}-mix.wav')
        _, music = wavfile.read(out/f'{mode}-music.wav')
        assert mix.shape == music.shape
        drums = mix.astype(float)-music
        wavfile.write(out/f'{mode}-drums.wav', rate, drums.astype(np.int16))
        def envelope(pcm):
            return np.convolve(abs(pcm.astype(float).mean(axis=1)), np.ones(100)/100, 'same')
        song = envelope(music)
        hits = envelope(drums)
        attacks = []
        # These opening notes coincide with strong, isolated drums in the song.
        # Compare actual waveforms, not just command times or gameplay clocks.
        for i in (0, 3, 6, 8):
            start = max(0, events[i]-round(.07*rate))
            end = events[i]+round(.06*rate)
            song_peak = start+int(np.argmax(song[start:end]))
            hit_peak = start+int(np.argmax(hits[start:end]))
            difference = (hit_peak-song_peak)*1000/rate
            assert abs(difference) < 8, (mode, i+1, difference)
            attacks.append(dict(note=i+1, difference_ms=difference))
        rows.append(dict(mode=mode, commands=len(events), attacks=attacks, **evidence))
    report = dict(passed=True, scope='1-X opening music/drum attacks at 1.0x, calibration 0', cases=rows)
    (out/'result.json').write_text(json.dumps(report, indent=2))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', type=Path, default=ROOT/'build/packs/sa1-scheduled-hits')
    args = parser.parse_args()
    print(json.dumps(check(args.base, args.base/'verification/1x-music-alignment'), indent=2))
