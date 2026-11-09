# ADOFAI SNES

A native SNES adaptation of A Dance of Fire and Ice, using the SA-1, Mode 7,
and SPC700. The master also uses MSU-1 for chart data and optional PCM music.
This is an unofficial project; it is not affiliated with 7th Beat Games.

## Contributing graphics

Editable CHR, tilemaps and palettes are in [`assets/graphics`](assets/graphics/).
The build reads these files directly, including on cached SA-1 rebuilds.
See [the graphics guide](docs/GRAPHICS.md) for tile assignments, formats and
the JSON shape definitions used for chart-generated track tiles.
Submit a pull request with your edited assets and screenshots.

## Building

Start with [Build your first ROM on Windows](docs/BUILDING.md): numbered setup,
one-song import, copy-and-paste build commands, and exact output paths.
Source includes the engine, original port
artwork, compilers, importers and verification tools. Commercial chart data,
music and hit samples are not included; import these from your own local game
installation. Community charts require the corresponding authors' files.
Do not commit extracted assets, generated song caches, ROMs or emulator binaries.

The toolchain is developed on Windows, using Python, cc65, FFmpeg and GCC.
Some importers and emulator tests still have machine-specific paths; see the
build guide before attempting a full catalog build.

## Playback formats

- **Full PCM master:** ROM plus matching MSU data and PCM music files.
- **Hybrid master:** selected PCM files; other songs use compressed audio.
- **Compressed master:** ROM plus MSU data, without PCM music files.
- **Standalone cartridges:** self-contained 8-MiB ROMs in smaller song groups.

Keep master files together and extract archives before playing. Revisions may
change the MSU dataset: replace both `adofai.sfc` and `adofai.msu` when instructed.
Start a fresh session instead of loading save states from an older build.

PCM plays at 1.0x. Other speeds use compressed music; standalone cartridges
use lower-rate compressed music above 1.0x. Tempo and pitch change together.
An emulator must support SA-1, and master builds additionally require MSU-1.
Physical-cartridge compatibility has not been established.

## Controls

Up/down select a set or song; START opens the selected set. B returns from a
song list to the set list and opens options from the set list. Single-set
cartridges open directly to their songs. Left/right or L/R adjust applicable
settings, including playback speed from 0.5x to 4.0x in 0.1x steps. START
starts or resumes play. X selects practice and Y selects autoplay on the menu.
SELECT opens calibration from the menu. Gameplay buttons
provide rhythm input. Retry and result screens use START/SELECT to avoid an
extra rhythm tap accidentally restarting the song.

Normal runs and speed trials do not display elapsed time. The playfield is
up to 144 pixels tall (Mad Piano Party retains 128 to fit the hardware tile cache).
The timing meter shows independently fading hit positions and a latest-hit
arrow; the center line is perfect timing. Each hit lasts three seconds, with
up to 512 records retained; neighboring markers do not erase one another.

## Renderer status

Track rendering uses chart-derived geometry, authored visibility and movement,
a bounded texture cache, and synchronized camera/scene publication. Planets
scale with camera zoom. Hit sounds follow scheduled chart beats, independently
of manual tap timing and calibration.

Scheduled hit sounds are mixed into the music at sample precision, so rendering
stalls and video-frame rounding cannot separate them from the song. Original
per-sample advances are in `assets/audio/hit-sound-offsets.json`. Confirmed
source-embedded kicks in 1-X, 2-X, 1J-X and 2J-X are listed in
`assets/audio/hit-timing.json`; those hits are reused instead of doubled.
Missing hits in those four tracks use their measured source alignment; other
tracks retain authored timing with the original sample-specific advances.
Playback speed changes affect
the complete mix, including percussion pitch. Input judgments remain separate.

Current builds require dataset 25: replace both the ROM and `.msu` data file.
PCM tracks from the dataset-24 audio release are unchanged and can be kept.
`tools/audit_music_hits.py` screens every source song,
`tools/verify_sample_mixes.py` checks every hit's placement, and
`tools/verify_music_locked_hits.py` compares whole-run emulator audio with the
mixed reference through the later 1-X sections.

Camera zoom and rotation support is chart-specific. R additionally imports
MoveTrack tile rotations. Gradual individual-tile scaling is not implemented.
Dense motion can use half-resolution track textures to reduce transfer cost;
planet sprites retain their own artwork. Extreme scenes can still stutter.
The current AR-X release measures about 54.2 delivered fps near 13% in
MesenCE, compared with 45.7 in the previous release; it is not locked at 60 fps.

## Verification

Compiler unit tests are in `tests/`. Tools under `tools/` check full-song PPU
output, cache state, checkpoint restoration, scheduled audio, zoomed planets,
SA-1 memory layout and ROM payloads. Test reports bind to ROM/data hashes.
Emulator binaries and private chart assets are local dependencies, not included
in this repository.
