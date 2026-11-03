"""Authoritative, editable graphics shared by clean and cached builds."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / 'assets' / 'graphics'
FILES = {'objects': 'objects.chr', 'palette': 'palette.bin',
         'background_chr': 'background.chr', 'background_map': 'background.map',
         'font': 'font.chr'}


def read_graphics(variant):
    folder = ROOT / variant
    manifest = json.loads((ROOT / 'manifest.json').read_text())
    result = {}
    for key, filename in FILES.items():
        data = (folder / filename).read_bytes()
        expected = manifest[variant][filename]
        if len(data) != expected:
            raise ValueError(f'{folder / filename}: expected {expected} bytes, got {len(data)}')
        result[key] = data
    return result


def write_graphics(out, variant):
    result = read_graphics(variant)
    for key, filename in FILES.items():
        (out / filename).write_bytes(result[key])
    return result


def patch_sa1_pack(out):
    """Refresh cached payloads too, without regenerating user-edited artwork."""
    graphics = write_graphics(out, 'mode7')
    placements = json.loads((out / 'placements.json').read_text())
    with (out / 'sa1_payload.bin').open('r+b') as payload:
        for key, data in graphics.items():
            address = placements[key]
            offset = address - 0xc00000 if address >= 0xc00000 else address
            payload.seek(offset - 0x10000)
            payload.write(data)
