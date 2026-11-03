import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import graphics_sources as graphics


class GraphicsSourcesTest(unittest.TestCase):
    def test_all_variants_match_manifest(self):
        for variant in ('demo', 'campaign', 'mode7'):
            self.assertEqual(len(graphics.read_graphics(variant)['objects']), 8192)

    def test_edited_chr_reaches_cached_payload(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'source'
            (source / 'mode7').mkdir(parents=True)
            assets = graphics.read_graphics('mode7')
            edited = bytearray(assets['objects'])
            edited[42] ^= 1
            assets['objects'] = bytes(edited)
            manifest = {}
            placements = {}
            offset = 0x10000
            for key, filename in graphics.FILES.items():
                (source / 'mode7' / filename).write_bytes(assets[key])
                manifest[filename] = len(assets[key])
                placements[key] = 0xc00000 + offset
                offset += len(assets[key])
            (source / 'manifest.json').write_text(json.dumps({'mode7': manifest}))
            (root / 'placements.json').write_text(json.dumps(placements))
            (root / 'sa1_payload.bin').write_bytes(bytes(offset - 0x10000))
            with patch.object(graphics, 'ROOT', source):
                graphics.patch_sa1_pack(root)
            payload = (root / 'sa1_payload.bin').read_bytes()
            self.assertEqual(payload[:8192], bytes(edited))
            self.assertEqual((root / 'objects.chr').read_bytes(), bytes(edited))


if __name__ == '__main__':
    unittest.main()
