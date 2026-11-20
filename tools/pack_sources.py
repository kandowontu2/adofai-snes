"""Use the imported source frozen with a compiled pack when available."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def source_path(folder,level):
    if folder is not None:
        frozen=Path(folder)/'source-imports'/f'level{level}.json'
        if frozen.exists():return frozen
    return ROOT/f'assets/private/level{level}.json'


def load_source(folder,level):
    return json.loads(source_path(folder,level).read_text())
