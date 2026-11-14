"""Resuming verified emulator evidence must retain its hardware captures."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import run_mesen_campaign as runner


class ResumeEvidenceTests(unittest.TestCase):
    def test_verified_resume_keeps_hardware_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);base=root/'build/packs/cache';out=base/'verification/mesen-1-autoplay'
            out.mkdir(parents=True)
            rom=b'unchanged test ROM';digest=hashlib.sha256(rom).hexdigest()
            (base/'adofai.sfc').write_bytes(rom);(base/'adofai.lbl').write_text('')
            (base/'pack.json').write_text(json.dumps(dict(levels=[1])))
            (base/'level1.json').write_text(json.dumps(dict(code='1-X',checkpoints=[])))
            (out/'result.txt').write_text('PASS\n')
            (out/'manifest.json').write_text(json.dumps(dict(passed=True,sha256=digest,
                msu_sha256=None,suite_digest='current',suite_version=2,graphics_dumps=True)))
            names=('ppu-1.bin','screen-1.png','step-1.png','hold-orbits.txt',
                   'hold-planets.txt','screen-registers.txt','mode1-icon-jobs.txt','ppu-verification.json')
            for name in names:(out/name).write_bytes(b'verified evidence')
            args=['run_mesen_campaign.py','--pack','cache','--levels','1',
                  '--autoplay','--graphics-dumps','--resume']
            with patch.object(runner,'ROOT',root),patch.object(runner,'suite_digest',return_value='current'), \
                 patch.object(runner,'identity',return_value=dict(rom_sha256=digest,msu_sha256=None)), \
                 patch.object(sys,'argv',args),patch.object(runner.subprocess,'run') as emulator:
                runner.main()
            emulator.assert_not_called()
            for name in names:self.assertEqual((out/name).read_bytes(),b'verified evidence',name)


if __name__=='__main__':unittest.main()
