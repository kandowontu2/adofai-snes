"""Bind emulator evidence to the ROM and its external MSU data."""
import hashlib
from pathlib import Path

def file_sha256(path):
    with Path(path).open('rb') as source:return hashlib.file_digest(source,'sha256').hexdigest()

def data_sha256(directory):
    path=Path(directory)/'adofai.msu'
    return file_sha256(path) if path.exists() else None

def identity(rom):
    rom=Path(rom)
    return dict(rom_sha256=file_sha256(rom),msu_sha256=data_sha256(rom.parent))
