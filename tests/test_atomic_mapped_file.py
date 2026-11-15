import os,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from atomic_mapped_file import atomic_mapped_file

class AtomicMappedFileTests(unittest.TestCase):
    def test_published_hardlink_is_not_modified(self):
        with tempfile.TemporaryDirectory() as directory:
            original=Path(directory)/'published.bin';original.write_bytes(b'unchanged')
            candidate=Path(directory)/'candidate.bin';os.link(original,candidate)
            with atomic_mapped_file(candidate,'.tmp') as image:image[0:3]=b'NEW'
            self.assertEqual(candidate.read_bytes(),b'NEWhanged')
            self.assertEqual(original.read_bytes(),b'unchanged')

    def test_failed_patch_leaves_source_intact(self):
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/'data.bin';source.write_bytes(b'original')
            with self.assertRaises(ValueError):
                with atomic_mapped_file(source,'.tmp') as image:
                    image[:3]=b'NEW';raise ValueError('failed validation')
            self.assertEqual(source.read_bytes(),b'original')
            self.assertEqual(list(Path(directory).iterdir()),[source])

if __name__=='__main__':unittest.main()
