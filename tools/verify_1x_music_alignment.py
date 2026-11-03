"""Compatibility entry point for the full-run, sample-locked audio check."""
import argparse
from pathlib import Path
from emulate import ROOT
from verify_music_locked_hits import check

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', type=Path, default=ROOT/'build/packs/sa1-scheduled-hits')
    args = parser.parse_args()
    reference = ROOT/'build/packs/sa1-scheduled-hits/sample-clock-pcm/adofai-1.pcm'
    result = check(args.base, reference, args.base/'verification/music-locked-hits')
    print('PASS full-song music-locked percussion')
