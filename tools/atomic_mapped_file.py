"""Bounded-memory, atomic fixed-size edits to large cartridge data files."""
from contextlib import contextmanager
import mmap
import os
from pathlib import Path
import shutil

@contextmanager
def atomic_mapped_file(path, suffix):
    path=Path(path);temporary=path.with_suffix(path.suffix+suffix)
    try:
        shutil.copyfile(path,temporary)
        with temporary.open('r+b') as file:
            with mmap.mmap(file.fileno(),0,access=mmap.ACCESS_WRITE) as image:
                yield image
                image.flush()
        os.replace(temporary,path)
    finally:
        temporary.unlink(missing_ok=True)
