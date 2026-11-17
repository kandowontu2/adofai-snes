"""Import and rasterize Mawaru's native, camera-anchored section headings.

The command schedule follows Mawaru.Start/DoText; the words come from the
installed NeoCosmos English TextAsset. These are gameplay instructions and
remain enabled independently of the optional background VFX switch.
"""
import bisect
import json
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image

from make_assets import FPS

# Native chapter beats, localization key, hang beats, persistent beats.
COMMANDS = (
    (42, 'warmUp', 5, 12), (66, 'holdsAndMidspins', 4, 13),
    (92, 'soccer', 5, 12), (124, 'triangles', 5, 12),
    (148, 'highFives', 5, 12), (170, 'collect', 5, 28),
    (218, 'backtrack', 5, 24), (259, 'warpTile', 5, 28),
    (299, 'math', 5, 28), (353, 'hardstyle', 8, 28),
    (401, 'drift', 8, 28), (449, 'drunk', 8, 28),
    (497, 'defend', 8, 60), (577, 'fog', 8, 28),
    (625, 'psytrance', 8, 28), (673, 'math2', 8, 28),
    (737, 'stealth', 8, 36), (794, 'triangles2', 8, 28),
    (842, 'victoryLap', 8, 28),
)


def extract(game):
    """Read only the English strings required by these two native scenes."""
    import UnityPy
    env = UnityPy.load(str(Path(game) / 'A Dance of Fire and Ice_Data/resources.assets'))
    for obj in env.objects:
        if obj.type.name != 'TextAsset':
            continue
        text = obj.read()
        if text.m_Name == 'NeoCosmos':
            # The asset starts with an export date before the JSON object.
            localized = json.loads(text.m_Script[text.m_Script.index('{'):])
            keys = {key for _, key, _, _ in COMMANDS} | {'soccer2'}
            return {key: localized['mawaru.' + key][0] for key in sorted(keys)}
    raise ValueError('The installed NeoCosmos English localization asset was not found')


def commands(strings, ex=False):
    return [dict(beat=b, key='mawaru.' + ('soccer2' if ex and key == 'soccer' else key),
                 text=strings['soccer2' if ex and key == 'soccer' else key],
                 hang=hang, persist=persist)
            for b, key, hang, persist in COMMANDS]


class Headings:
    def __init__(self, chart):
        from neo_visuals import chapter_time
        self.rows = []
        for command in chart.get('mawaru_headings', []):
            start, hang, persist = command['beat'], command['hang'], command['persist']
            self.rows.append((chapter_time(chart, start)*FPS,
                              chapter_time(chart, start+hang)*FPS,
                              chapter_time(chart, start+hang+2)*FPS,
                              chapter_time(chart, start+hang+2+persist)*FPS,
                              command['text']))
        self.starts = [row[0] for row in self.rows]

    def pose(self, frame):
        i = bisect.bisect_right(self.starts, frame)-1
        if i < 0:
            return None
        start, hang, settled, fade, text = self.rows[i]
        if frame >= fade+FPS:
            return None
        entrance = min(1, max(0, (frame-start)/(.3*FPS)))
        p = min(1, max(0, (frame-hang)/(settled-hang)))
        ease = 4*p**3 if p < .5 else 1-(-2*p+2)**3/2
        # Keep the settled heading at an eight-pixel font on the SNES.
        # The native text moves upward and shrinks after its initial hang.
        height = round((16-8*ease)*(2-entrance**3))
        y = round(84-40*ease)
        alpha = entrance*(1-.4*p)*max(0, min(1, 1-(frame-fade)/FPS))
        return text, height, y, max(0, min(31, round(alpha*31)))

    @staticmethod
    @lru_cache(maxsize=512)
    def mask(text, height):
        from decoration_tracks import text_image
        raw = Image.fromarray(text_image(text,stage_punctuation=True)[:, :, 3])
        lines = text.count('\n')+1
        width = min(240, max(1, round(raw.width*height/64)))
        return np.asarray(raw.resize((width, height*lines), Image.Resampling.NEAREST)) > 0

    def draw(self, frame, image, palette):
        pose = self.pose(frame)
        if pose is None:
            return image
        text, height, y, shade = pose
        if not shade:
            return image
        mask = self.mask(text, height)
        y = max(33, y-mask.shape[0]//2)
        x = (256-mask.shape[1])//2
        color = shade*1057
        used = set(map(int, np.unique(image)))
        index = next((i for i in range(32, 128) if int(palette[i]) == color), None)
        if index is None:
            index = next(i for i in range(32, 128) if i not in used)
            palette[index] = color
        output = image.copy()
        part = output[y:y+mask.shape[0], x:x+mask.shape[1]]
        part[mask] = index
        return output
