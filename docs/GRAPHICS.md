# Editing graphics

Static artwork lives in `assets/graphics/`. Edit these files and submit them in
your PR; builds read them directly and never regenerate them. CHR is raw SNES
 planar tile data, with no header. Palette files contain little-endian BGR555
 colors. Keep file sizes and tile positions unchanged (validated by
 `assets/graphics/manifest.json`).

| Folder | Used by |
| --- | --- |
| `mode7/` | SA-1 master and current standalone ROMs |
| `campaign/` | Legacy non-Mode-7 campaign builds |
| `demo/` | Original first-level demo |

| File | Format |
| --- | --- |
| `objects.chr` | 4bpp, 256 tiles, 128 by 128 pixels; planets, icons and trails |
| `font.chr` | 2bpp, 8 by 8 character tiles, ASCII indexing |
| `background.chr` | 2bpp background tiles |
| `background.map` | SNES tilemap words |
| `palette.bin` | 256 BGR555 colors (512 bytes) |

In `font.chr`, tiles 1–2 are the menu arrows, 3–4 are the timing bar and
perfect-center line, tile 8 is the hit tick (9–15 are legacy shifted copies),
and 16–23 are the latest-hit arrow. These glyphs are read directly
from the CHR file, so a graphics PR can change the meter without editing code.
Tile 8 supplies the tick silhouette; the runtime composites independent fading
columns into VRAM glyphs 128–144 so neighboring hits remain visible.
The two dim tick shades derive from palette 7’s bright color (index 31);
CGRAM entries 29–30 are reserved for those runtime fade shades.
Printable characters retain their ASCII tile numbers.

The Mode-7 OBJ sheet includes every planet zoom size. These are editable
artwork, not regenerated thumbnails. The original-size planet occupies tile
6 (a 16 by 16 sprite). Additional radius/starting-tile assignments are:

| Radius | Starting tile(s) |
| --- | --- |
| 5 | 0 |
| 6 | 2 |
| 8 | 4 |
| 10 | 10, 14, 40, 42 |
| 12 | 44, 46, 70, 78 |
| 14 | 96, 98, 100, 102 |

Each starting tile addresses a 16 by 16 OBJ block (two adjacent tiles on two
atlas rows). Four-block sizes use top-left, top-right, bottom-left, bottom-right
order. Trails occupy tiles 128 through 255. Preserve transparent pixel index 0.

Track graphics are procedural: charts can use arbitrary angles, tile rotations,
movement and zoom. Edit `assets/graphics/track-shapes.json` for the normal track
width/half-segment length and the midspin/full-turn local polygon outlines.
These definitions are rasterized at each chart angle; changing them invalidates
chart caches automatically. Keep landing centers and the existing maximum shape
extent unchanged: rotation cache footprints assume the current tile envelope.
Padding controls raster bounds, not a decorative border.

Generated track CHR caches in `build/` are not source artwork and are overwritten.
The rasterization algorithm is in `tools/track_geometry.py`; occlusion and
separation logic is in `tools/track_visibility.py`. Track colors still follow
chart events through `tools/track_colors.py`, rather than a global artwork palette.

## Hardware constraints

Planet color presets are defined by `COLOR_RGB` in
[`tools/presentation_assets.py`](../tools/presentation_assets.py), in the order
shown by `COLOR_NAMES`. Edit those RGB triples to change the selectable colors;
the build generates their dark-to-light shading. Cached SA-1 engine rebuilds
refresh these presets too. The in-game fire/ice color settings override the
static planet palette entries in `palette.bin`.

OBJ sprites use 4-bit indexed pixels. Pixel index 0 is transparent. A sprite
uses one 16-color palette; the two planets can select different palettes.
The source atlas is a 128-by-128 sheet of 8-by-8 tiles. Tile numbers in the
renderer refer to positions in that sheet: moving artwork to another slot
requires updating the corresponding renderer constants/tables.

Mode 7 track graphics are generated separately from the OBJ atlas. There are
256 physical 8-by-8 patterns, including the blank pattern. Track animation
reuses those slots. A shape that looks fine in an isolated PNG may require too
many distinct patterns when hundreds of animated pieces overlap. The compiler
checks capacity; emulator checks also verify that the displayed pixels match
the compiled scene and transfers finish within VBlank.

Keep tile landing centers fixed. Visual changes must not move the targets away
from the planets or change musical timing. Preserve individual separation
lines, including on moving pieces. Track appearance/disappearance comes from
the chart, not a fixed number of past or future notes.

## Iteration

Start with the [one-song build guide](BUILDING.md). Changing the
track generators requires recompiling chart assets, then rebuilding the ROM.
For static CHR/palette edits, rebuild the SA-1 engine: its cached payload is
refreshed from `assets/graphics/mode7/` before assembly.

For a precompiled SA-1 pack, rebuild engine code with:

```powershell
.\.venv\Scripts\python.exe -c "import sys; from pathlib import Path; sys.path.insert(0,'tools'); from build_sa1 import compile_engine; compile_engine(Path('build/sa1-demo'))"
```

For track edits, rerun chart compilation and pack generation into fresh output
folders, as described in the build guide. Existing SA-1 output packs reuse
their chart data even when the source folder has changed.
Use a fresh emulator boot after rebuilding; old save states retain obsolete
RAM, cache contents and animation pointers.

When submitting graphics changes, include screenshots and identify the chart,
speed, emulator, and section tested. Do not include extracted music, original
game assets, private chart data, build directories, or emulator binaries.
