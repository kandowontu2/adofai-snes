import hashlib,os,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from verification_data import identity,freeze_data_identity


class FrozenDataTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.env=patch.dict(os.environ,{},clear=False);self.env.start()
        self.addCleanup(self.env.stop)
        os.environ.pop('ADOFAI_FROZEN_MSU',None)
        self.rom=Path(self.tmp.name)/'adofai.sfc';self.rom.write_bytes(b'engine')
        self.data=self.rom.with_suffix('.msu');self.data.write_bytes(b'first')

    def test_children_reuse_only_matching_immutable_data(self):
        original=identity(self.rom,fresh=True)
        freeze_data_identity(self.rom,original)
        with patch('verification_data.file_sha256',wraps=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()) as digest:
            self.assertEqual(identity(self.rom),original)
            self.assertEqual([call.args[0] for call in digest.call_args_list],[self.rom])
        self.data.write_bytes(b'changed data')
        self.assertNotEqual(identity(self.rom),original)

    def test_final_fresh_hash_detects_even_restored_timestamp(self):
        original=identity(self.rom,fresh=True);stamp=self.data.stat()
        freeze_data_identity(self.rom,original)
        self.data.write_bytes(b'other')
        os.utime(self.data,ns=(stamp.st_atime_ns,stamp.st_mtime_ns))
        self.assertNotEqual(identity(self.rom,fresh=True),original)

    def test_other_pack_does_not_inherit_cached_digest(self):
        freeze_data_identity(self.rom,identity(self.rom,fresh=True))
        other=Path(self.tmp.name)/'other';other.mkdir()
        rom=other/'adofai.sfc';rom.write_bytes(b'engine')
        rom.with_suffix('.msu').write_bytes(b'other')
        self.assertNotEqual(identity(rom),identity(self.rom))


if __name__=='__main__':unittest.main()
