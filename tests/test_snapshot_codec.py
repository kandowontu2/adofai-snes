import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from snapshot_codec import encode, decode, encode_split, decode_split


def cartridge_decode(payload):
    """Independent byte-copy model of the cartridge token/literal/match loop."""
    result = bytearray()
    pos = 0
    while pos < len(payload):
        token = payload[pos]
        pos += 1
        literals = token >> 4
        if literals == 15:
            while True:
                extra = payload[pos]
                pos += 1
                literals += extra
                if extra != 255:
                    break
        result += payload[pos:pos + literals]
        pos += literals
        if pos == len(payload):
            return bytes(result)
        distance = int.from_bytes(payload[pos:pos + 2], 'little')
        pos += 2
        length = (token & 15) + 4
        if token & 15 == 15:
            while True:
                extra = payload[pos]
                pos += 1
                length += extra
                if extra != 255:
                    break
        assert 0 < distance <= len(result)
        for _ in range(length):
            result.append(result[-distance])
    raise AssertionError('Missing final literal sequence')


class SnapshotCodecTests(unittest.TestCase):
    def test_palette_map_and_atlas_round_trip(self):
        rng = random.Random(56302)
        for count in (0, 1, 127, 128, 255, 511):
            size = 1312 + count * 32
            for raw in (bytes(size), bytes(i % 256 for i in range(size)), rng.randbytes(size)):
                packed = encode(raw)
                self.assertEqual(decode(packed, count), raw)
                self.assertEqual(cartridge_decode(packed), raw)
                packed = encode_split(raw)
                self.assertEqual(decode_split(packed, count), raw)
                header = int.from_bytes(packed[:2], 'little')
                self.assertEqual(cartridge_decode(packed[2:2+header]) + cartridge_decode(packed[2+header:]), raw)

    def test_wrong_atlas_size_is_rejected(self):
        with self.assertRaises((ValueError, RuntimeError)):
            decode(encode(bytes(1312 + 32)), 0)


if __name__ == '__main__':
    unittest.main()
