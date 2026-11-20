import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from plan_catalog_storage import native_signature


class StoragePlanCacheTests(unittest.TestCase):
    def test_seed_and_index_changes_invalidate_an_unchanged_stream(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            files={'stream_index7.bin':b'index','stream_data7.bin':b'stream','mode1_seeds7.bin':b'seed'}
            for name,data in files.items():(root/name).write_bytes(data)
            before=native_signature(root,7,'')
            stream_stamp=(root/'stream_data7.bin').stat().st_mtime_ns
            for name in ('stream_index7.bin','mode1_seeds7.bin'):
                (root/name).write_bytes(files[name]+b'changed')
                self.assertNotEqual(native_signature(root,7,''),before)
                self.assertEqual((root/'stream_data7.bin').stat().st_mtime_ns,stream_stamp)
                (root/name).write_bytes(files[name])
                self.assertEqual(native_signature(root,7,''),before)
