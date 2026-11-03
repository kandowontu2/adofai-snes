"""Build native official-world SNES packs and the MSU-1 master cartridge."""
import os
import shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def command(name):
    suffix='.exe' if os.name=='nt' else ''
    candidates=[ROOT/'.tools/cc65'/(name+suffix)]
    if os.environ.get('CC65_HOME'): candidates.insert(0,Path(os.environ['CC65_HOME'])/'bin'/(name+suffix))
    for p in candidates:
        if p.exists(): return str(p)
    p=shutil.which(name)
    if p:return p
    raise SystemExit(f'{name} not found. Set CC65_HOME or place cc65 binaries in .tools/cc65/.')


def main():
    from build_campaign import main as build_campaign
    build_campaign()

if __name__=='__main__':main()
