"""Bind emulator evidence to the ROM and its external MSU data."""
import hashlib,json,os
from pathlib import Path

def file_sha256(path):
    with Path(path).open('rb') as source:return hashlib.file_digest(source,'sha256').hexdigest()

def data_stamp(path):
    s=path.stat()
    return [str(path.resolve()),s.st_size,s.st_mtime_ns,s.st_ino,s.st_dev]


def freeze_data_identity(rom, frozen):
    """Let child replays reuse a batch's already-hashed immutable MSU file.

    The parent must hash again with fresh=True before accepting the batch.
    ROMs are always hashed; this avoids terabytes of redundant MSU reads.
    """
    path=Path(rom).with_suffix('.msu')
    if path.exists():
        os.environ['ADOFAI_FROZEN_MSU']=json.dumps(dict(stamp=data_stamp(path),sha256=frozen['msu_sha256']))


def data_sha256(directory, *, fresh=False):
    path=Path(directory)/'adofai.msu'
    if not path.exists():return None
    if not fresh:
        try:
            frozen=json.loads(os.environ.get('ADOFAI_FROZEN_MSU','{}'))
            if frozen.get('stamp')==data_stamp(path):return frozen['sha256']
        except (ValueError,KeyError,TypeError):pass
    return file_sha256(path)

def identity(rom, *, fresh=False):
    rom=Path(rom)
    return dict(rom_sha256=file_sha256(rom),msu_sha256=data_sha256(rom.parent,fresh=fresh))
