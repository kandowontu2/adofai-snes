"""Neo Cosmos full-song stages; tutorials and playground are intentionally excluded."""

NEO = [dict(id=66 + i, code=code, title=title) for i, (code, title) in enumerate([
    ('T1-X', 'NEW LIFE'), ('T2-X', 'SING SING RED INDIGO'),
    ('T3-X', 'NO HINTS HERE!'), ('T4-X', 'THIRD SUN'),
    ('T5-X', 'DIVINE INTERVENTION'), ('T1EX-X', 'NEW LIFE'),
    ('T2EX-X', 'SING SING RED INDIGO'), ('T3EX-X', 'NO HINTS HERE!'),
    ('T4EX-X', 'THIRD SUN'),
])]

def display_code(code):
    """EX scene IDs differ from the labels used by the original game's UI."""
    return code[:2] + '-EX' if code in {m['code'] for m in NEO[5:]} else code
