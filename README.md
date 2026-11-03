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

See [BUILDING.md](docs/BUILDING.md). Source includes the engine, original port
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

Up/down select a song; left/right or L/R adjust applicable settings. START
starts or resumes play. X selects practice and Y selects autoplay on the menu.
SELECT opens calibration from the menu; B opens options. Gameplay buttons
provide rhythm input. Retry and result screens use START/SELECT to avoid an
extra rhythm tap accidentally restarting the song.

## Renderer status

Track rendering uses chart-derived geometry, authored visibility and movement,
a bounded texture cache, and synchronized camera/scene publication. Planets
scale with camera zoom. Hit sounds follow scheduled chart beats, independently
of manual tap timing and calibration.

Measured per-track percussion/music alignment corrections live in
`assets/audio/hit-timing.json`. For 1-X, percussion starts two chart frames
earlier with compressed music and one frame earlier with PCM. This corrects
the audible drum alignment without moving input judgments. The waveform check
`tools/verify_1x_music_alignment.py` compares isolated hit voices with the music.

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
