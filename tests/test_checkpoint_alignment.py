"""Periodic first beats must not override later unambiguous audio evidence."""
import sys,unittest
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from verify_checkpoints import shared_audio_peaks

class CheckpointAlignment(unittest.TestCase):
    def test_repeated_first_tone_uses_the_common_measured_lag(self):
        curves=np.zeros((3,3001))
        curves[:,1668]=(.999,.999,.998)
        curves[:,168]=(1.,.2,.1)
        self.assertEqual(shared_audio_peaks(curves),[1668]*3)

    def test_real_large_offset_is_measured_without_clamping(self):
        curves=np.zeros((3,3001));curves[:,2100]=1.
        self.assertEqual(shared_audio_peaks(curves),[2100]*3)
        self.assertGreater((2100-1500)/12,30)

    def test_faster_playback_keeps_four_ms_physical_jitter(self):
        curves=np.zeros((3,3001))
        for row,peak in zip(curves,(1750,1790,1810)):row[peak]=.999
        self.assertEqual(shared_audio_peaks(curves,2),[1750,1790,1810])

    def test_corrupt_window_cannot_gain_correlation(self):
        curves=np.zeros((3,3001));curves[:,1750]=(.999,.4,.999)
        peaks=shared_audio_peaks(curves,2)
        self.assertLess(min(row[p] for row,p in zip(curves,peaks)),.9)

if __name__=='__main__':unittest.main()
