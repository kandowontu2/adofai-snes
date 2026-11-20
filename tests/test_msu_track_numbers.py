import struct,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from msu_assets import checkpoint_track_base,validate_track_numbers,generate

class TrackNumberTests(unittest.TestCase):
    def test_extended_replacement_keeps_the_complete_note_seek_table(self):
        with tempfile.TemporaryDirectory() as directory:
            out=Path(directory);notes=bytes(range(56))
            (out/'animation1.bin').write_bytes(b'animation')
            (out/'chart1.bin').write_bytes(notes)
            chart=dict(id=1,code='TEST',title='TEST',checkpoints=[])
            generate(out,[chart],{1:b'music'},generate_pcm=False,extended_catalog=True)
            descriptor=struct.unpack('<IHHIIHHI',(out/'msu_descriptors.bin').read_bytes())
            data=(out/'adofai.msu').read_bytes()
            self.assertEqual(struct.unpack_from('<H',data,12)[0],21)
            self.assertEqual(data[descriptor[7]:descriptor[7]+len(notes)],notes)

    def test_released_track_numbers_are_preserved(self):
        self.assertEqual(checkpoint_track_base(1),1032)
        self.assertEqual(checkpoint_track_base(284),10088)

    def test_new_charts_do_not_overlap_overclocked(self):
        validate_track_numbers([dict(id=284,checkpoints=[0]*34),
                                dict(id=285,checkpoints=[0]*2),
                                dict(id=286,checkpoints=[0]*5)])

    def test_overlapping_ranges_fail_before_writing_audio(self):
        with self.assertRaisesRegex(AssertionError,'Overlapping MSU tracks'):
            validate_track_numbers([dict(id=1,checkpoints=[0]*33),dict(id=2,checkpoints=[0])])

if __name__=='__main__':unittest.main()
