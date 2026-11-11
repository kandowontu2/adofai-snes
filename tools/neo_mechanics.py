"""Native Neo Cosmos note semantics shared by the importer and compiler."""
HOLD = 0x8000
FREE_ROAM = 0x4000
PAUSE_MASK = 0x3fff


def duration_beats(floor, arc_beats):
    # scrLevelMaker.CalculateFloorEntryTimes adds two beats per hold turn.
    # A zero-length hold is still a press/release pair, with its normal arc.
    return arc_beats + 2 * max(0, floor.get('holdLength', -1)) + floor.get('extraBeats', 0)


def packed_pause(note):
    frames = note['pause_frames']
    if not 0 <= frames <= PAUSE_MASK:
        raise ValueError(f'Pause exceeds packed note range: {frames}')
    return frames | (HOLD if note.get('hold_length', -1) >= 0 else 0) | (FREE_ROAM if note.get('freeroam') else 0)


def release_required(current, following):
    """A chained hold changes floors on a new press, not on releasing."""
    return current.get('holdLength', -1) >= 0 and following.get('holdLength', -1) < 0
