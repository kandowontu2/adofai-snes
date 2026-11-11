import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from animation_bulk import HEADER, records, semantic_digest
from animation_sparse import batch_sparse


class SparseAnimation(unittest.TestCase):
    def test_sparse_aliases_keep_order_and_checkpoint_offsets(self):
        chart = dict(cell_coordinates=[[0, 0], [128, 0], [7, 5], [135, 5], [1, 1]])
        original = b''.join(HEADER.pack(12, 0, i, v)
                            for i, v in enumerate((0, 3, 0, 8, 9)))
        original += HEADER.pack(13, 10, 40, 50)+HEADER.pack(65535, 255, 0, 0)
        packed, groups = batch_sparse(original, chart)
        self.assertEqual(len(packed), len(original))
        self.assertEqual(semantic_digest(packed), semantic_digest(original))
        self.assertEqual(groups, [(0, 35, 5)])
        self.assertEqual(packed[35:], original[35:])
        row = next(records(packed))
        self.assertEqual(row[3:6], (29, 5, 28))
        decoded = [struct.unpack_from('<HHB', packed, 7+i*5) for i in range(5)]
        self.assertEqual(decoded, [(0, 0, 0), (1, 0, 3), (2, 647, 0), (3, 647, 8), (4, 129, 9)])

    def test_batches_fit_the_fixed_transfer_buffer(self):
        chart = dict(cell_coordinates=[[i, 1] for i in range(260)])
        original = b''.join(HEADER.pack(4, 0, i, 1) for i in range(260))
        original += HEADER.pack(65535, 255, 0, 0)
        packed, groups = batch_sparse(original, chart)
        self.assertEqual([n for _, _, n in groups], [128, 128, 4])
        self.assertEqual(semantic_digest(packed), semantic_digest(original))
        self.assertLessEqual(max(v for _, _, _, k, _, v in records(packed) if k == 29), 889)

    def test_three_changes_and_different_timestamps_remain_original(self):
        chart = dict(cell_coordinates=[[i, 0] for i in range(5)])
        original = b''.join(HEADER.pack(0 if i < 3 else 1, 0, i, i) for i in range(5))
        original += HEADER.pack(65535, 255, 0, 0)
        self.assertEqual(batch_sparse(original, chart), (original, []))


if __name__ == '__main__':
    unittest.main()
