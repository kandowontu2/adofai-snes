"""One lossless, independent LZ4 block per complete screen pose."""
import lz4.block
import struct


def encode(raw):
    return lz4.block.compress(raw, mode='high_compression', compression=12, store_size=False)


def decode(payload, glyph_count):
    expected = 1312 + glyph_count * 32
    try:
        raw = lz4.block.decompress(payload, uncompressed_size=expected)
    except lz4.block.LZ4BlockError as exc:
        raise ValueError('Invalid compressed snapshot or atlas size') from exc
    if len(raw) != expected:
        raise ValueError('Snapshot decompressed size differs')
    return raw


def encode_split(raw):
    """Decode the header to bank 42 and pixels straight into bank 43."""
    header = encode(raw[:1312])
    return struct.pack('<H', len(header)) + header + encode(raw[1312:])


def decode_split(payload, glyph_count):
    size = struct.unpack_from('<H', payload)[0]
    try:
        header = lz4.block.decompress(payload[2:2+size], uncompressed_size=1312)
        pixels = lz4.block.decompress(payload[2+size:], uncompressed_size=glyph_count*32)
    except lz4.block.LZ4BlockError as exc:
        raise ValueError('Invalid split snapshot') from exc
    if len(header) != 1312 or len(pixels) != glyph_count*32:
        raise ValueError('Split snapshot decompressed size differs')
    return header + pixels
