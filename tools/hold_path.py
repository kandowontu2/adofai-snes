"""Hold orbit shared by the rasterizer and planet animation tables."""
import math


def sweep(note):
    entry=note.get('angle',0)*math.pi/128
    sign=-1 if note.get('ccw') else 1
    arc=((note['exit_angle']-entry)*sign)%(2*math.pi)
    if arc<.00001:arc=2*math.pi
    return sign*(arc+2*math.pi*note['hold_length'])
