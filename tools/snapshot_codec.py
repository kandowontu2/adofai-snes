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


def encode_ordered_split(raw, *, indexed=False):
    """Choose the smaller of two exact atlas orders; remap every map cell."""
    original = encode_split(raw)
    stride = 64 if indexed else 32
    prefix = 32 if indexed else 0
    atlas = raw[1312+prefix:]
    assert len(atlas) % stride == 0
    glyphs = [atlas[i:i+stride] for i in range(0, len(atlas), stride)]
    order = sorted(range(len(glyphs)), key=lambda i: glyphs[i])
    if order == list(range(len(glyphs))):
        return original
    remap = {old+1:new+1 for new,old in enumerate(order)}
    header = bytearray(raw[:1312])
    for cell in range(608):
        word = struct.unpack_from('<H', header, 96+cell*2)[0]
        slot = word & 1023
        if slot:
            struct.pack_into('<H', header, 96+cell*2, (word & ~1023) | remap[slot])
    changed = bytes(header)+raw[1312:1312+prefix]+b''.join(glyphs[i] for i in order)
    candidate = encode_split(changed)
    return candidate if len(candidate) < len(original) else original


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
