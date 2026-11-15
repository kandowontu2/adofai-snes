"""User-requested restart points for charts shipped without checkpoints.

These are port additions, not events attributed to the original authors.
Floors were selected near phrase boundaries with at least a full beat before
the next required tap. Existing authored checkpoints always take precedence.
"""

# Curated rather than evenly spaced at runtime. Times are approximate seconds
# in the normal-speed chart, including its lead-in.
FLOORS = {
    62: (245, 591),          # Mad Piano Party II: 42.5, 87.1
    239: (135,),             # 1-EX: 34.2
    240: (115, 297, 412),    # 2-EX: 36.7, 75.2, 114.2
    241: (135, 251),         # 3-EX: 38.7, 76.0
    242: (97, 169, 237),     # 4-EX: 36.6, 77.7, 112.0
    243: (119,),             # 5-EX: 39.8
    244: (111, 241, 347),    # 6-EX: 40.7, 82.5, 124.3
    246: (193,),             # 8-EX: 45.0
    247: (119, 266),         # 9-EX: 37.5, 74.7
}
EXPECTED_STEPS = {62: 976, 239: 281, 240: 479, 241: 338, 242: 304,
                  243: 234, 244: 432, 246: 341, 247: 397}


def events(data):
    authored = data.get('checkpoints', [])
    if authored:
        return authored
    level = data.get('id')
    if level in EXPECTED_STEPS:
        assert len(data['floors']) == EXPECTED_STEPS[level] + 1, (
            'Chart layout changed; review supplemental checkpoint placements', level)
    result = []
    for index in FLOORS.get(data.get('id'), ()):
        assert 0 < index < len(data['floors']) - 1
        floor = data['floors'][index]
        assert not floor['midSpin'] and not floor.get('auto', False)
        assert floor.get('holdLength', -1) <= 0
        result.append(dict(floor=index, tileOffset=0))
    return result
