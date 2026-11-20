import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from pack_sources import load_source,source_path,ROOT


class PackSourceTests(unittest.TestCase):
    def test_frozen_source_wins_over_later_catalog_imports(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory)
            self.assertEqual(source_path(folder,999),ROOT/'assets/private/level999.json')
            frozen=folder/'source-imports';frozen.mkdir()
            (frozen/'level999.json').write_text(json.dumps(dict(id=999,tag='original')))
            self.assertEqual(load_source(folder,999),dict(id=999,tag='original'))
