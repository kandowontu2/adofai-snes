import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from verify_sa1_layout import verify_cpu_scratch

class CpuScratchLayout(unittest.TestCase):
    def test_old_twirl_cache_collides_with_stream_cursor(self):
        with self.assertRaisesRegex(AssertionError,'CPU scratch overlap'):
            verify_cpu_scratch(0x05A2,0x05B8)

    def test_twirl_cache_fits_between_preview_and_nmi(self):
        verify_cpu_scratch(0x07C8,0x07DE)

    def test_cache_cannot_cross_into_nmi_code(self):
        with self.assertRaises(AssertionError):verify_cpu_scratch(0x07F0,0x0806)

if __name__=='__main__':unittest.main()
