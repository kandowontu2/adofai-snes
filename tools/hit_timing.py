"""Compile explicit, measured track/music percussion corrections for SA-1 packs."""
import json
from pathlib import Path
from make_assets import FPS

ROOT = Path(__file__).resolve().parents[1]

def lead_frames(level, pcm=False):
    settings = json.loads((ROOT/'assets/audio/hit-timing.json').read_text())
    seconds = settings.get(str(level), {}).get('pcm_advance_seconds' if pcm else 'advance_seconds', 0)
    assert 0 <= seconds <= .12
    return round(seconds * FPS)

def patch_pack(out):
    out = Path(out)
    levels = json.loads((out/'pack.json').read_text())['levels']
    settings = json.loads((ROOT/'assets/audio/hit-timing.json').read_text())
    (out/'hit_timing.inc').write_text(
        '; Percussion only: chart times and input calibration are unchanged.\n'
        'hit_music_lead_frames: .word '+','.join(str(lead_frames(n)) for n in levels)+'\n'
        'hit_pcm_lead_frames: .word '+','.join(str(lead_frames(n, True)) for n in levels)+'\n'
        'hit_music_embedded: .word '+','.join('1' for n in levels)+'\n')
