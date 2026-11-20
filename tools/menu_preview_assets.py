"""Compile original chart preview art and credits for the song browser."""
import html
import json
import re
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps
from make_assets import tile_bytes

ROOT = Path(__file__).resolve().parents[1]
ART_BYTES = 12 * 8 * 32
FOOTER_BYTES = 32 * 2 * 32


def plain(value):
    return ' '.join(html.unescape(re.sub(r'<[^>]*>', '', str(value or ''))).split())


def metadata(level,folder=None):
    from pack_sources import load_source
    data=load_source(folder,level)
    settings = data.get('track_settings', {})
    author = plain(data.get('author') or settings.get('author')) or 'UNLISTED'
    difficulty = settings.get('difficulty')
    difficulty = str(difficulty) if isinstance(difficulty, (int, float)) and difficulty > 0 else 'UNRATED'
    image = None
    source = Path(data.get('source', ''))
    preview = settings.get('previewImage')
    if source.is_file() and preview:
        candidate = source.parent / preview
        if candidate.is_file():
            image = candidate
    return dict(id=level, author=author, difficulty=difficulty,
                preview=str(image) if image else None)


def footer_line(text):
    """Use the game's font, with a system font for authored Unicode names."""
    image = Image.new('L', (256, 8))
    text = text.upper()
    if all(ord(c) < 128 for c in text):
        if len(text) > 32:
            text = text[:29] + '...'
        pixels = np.asarray(image).copy()
        font=(ROOT/'assets/graphics/mode7/font.chr').read_bytes()
        punctuation=(ROOT/'assets/graphics/campaign/stage-punctuation.chr').read_bytes()
        for i, char in enumerate(text):
            glyph=punctuation["&'".index(char)*16:("&'".index(char)+1)*16] if char in "&'" else font[ord(char)*16:(ord(char)+1)*16]
            for y in range(8):
                ink=glyph[y*2]|glyph[y*2+1]
                for x in range(8):
                    if ink&(128>>x):pixels[y,i*8+x]=15
        return pixels
    host = Path('C:/Windows/Fonts/msgothic.ttc')
    if not host.exists():
        raise FileNotFoundError('Unicode menu credits need MS Gothic (C:/Windows/Fonts/msgothic.ttc)')
    font = ImageFont.truetype(str(host), 8)
    draw = ImageDraw.Draw(image)
    while draw.textlength(text, font=font) > 254:
        text = text[:-4] + '...'
    draw.text((1, -1), text, font=font, fill=15, stroke_width=0)
    return np.where(np.asarray(image) >= 7, 15, 0).astype(np.uint8)


def compile_preview(row):
    art = Image.new('RGB', (96, 64), (7, 9, 22))
    if row['preview']:
        with Image.open(row['preview']) as original:
            original = ImageOps.exif_transpose(original).convert('RGB')
            fitted = ImageOps.contain(original, art.size, Image.Resampling.LANCZOS)
            art.paste(fitted, ((96-fitted.width)//2, (64-fitted.height)//2))
    else:
        draw = ImageDraw.Draw(art)
        draw.rectangle((0, 0, 95, 63), outline=(75, 98, 116))
        draw.text((15, 26), 'NO PREVIEW', fill=(167, 194, 218), font=ImageFont.load_default(size=9))
    indexed = art.quantize(colors=14, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    colors = indexed.getpalette()
    colors = [tuple(colors[i:i+3]) for i in range(0, 42, 3)]
    colors += [(246, 250, 255)]
    palette = bytes(2) + b''.join(((r>>3)|((g>>3)<<5)|((b>>3)<<10)).to_bytes(2, 'little') for r,g,b in colors)
    pixels = np.asarray(indexed).astype(np.uint8) + 1
    footer = np.concatenate((footer_line('BY: '+row['author']),
                             footer_line('DIFFICULTY: '+row['difficulty'])), axis=0)
    chr_data = b''.join(tile_bytes(image[y:y+8, x:x+8], 4)
                        for image in (pixels, footer)
                        for y in range(0, image.shape[0], 8)
                        for x in range(0, image.shape[1], 8))
    assert len(palette) == 32 and len(chr_data) == ART_BYTES + FOOTER_BYTES
    return palette + chr_data


def build(out, charts):
    rows = [metadata(c['id'],out) for c in charts]
    blobs = {f'menu_preview{row["id"]}': compile_preview(row) for row in rows}
    blobs['menu_preview_descriptors'] = bytes(3*len(charts))
    # Static PPU data belongs in the asset arena, outside executable banks.
    # The full catalog leaves too little room for a 2-KiB map in bank zero.
    blobs['menu_preview_map'] = b''.join(
        (0x2B00+(y-6)*12+x-19 if 6 <= y < 14 and 19 <= x < 31
         else 0x2B60+(y-26)*32+x if 26 <= y < 28
         else 0x2BA0).to_bytes(2, 'little')
        for y in range(32) for x in range(32))
    (out / 'menu-previews.json').write_text(json.dumps(rows, indent=2), encoding='utf-8')
    return blobs
