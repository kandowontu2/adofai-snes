# Building from source

This repository contains the port's assembly, asset generators, importers and
tests. It does not contain the commercial game's music, extracted chart data,
hit samples, third-party community charts, or generated song assets. Editable original port graphics are included under
`assets/graphics/`.

The current toolchain is developed on Windows with Python 3. Other platforms
may need adjustments to emulator paths and executable names in the tools.

## Tools

- Python with the packages in `requirements.txt`.
- cc65's `ca65` and `ld65` assemblers/linker, available on PATH, under
  `$env:CC65_HOME/bin`, or in `.tools/cc65/`.
- FFmpeg on PATH for audio preparation.
- GCC on PATH for the BRR encoder.
- A locally installed, legally obtained copy of A Dance of Fire and Ice for
  importing its charts and audio.
- An emulator supporting SA-1; MSU packs also require MSU-1 support.

```powershell
python -m pip install -r requirements.txt
New-Item -ItemType Directory -Force .tools | Out-Null
```

## Small first build

Import the installed game's main campaign:

```powershell
python tools/import_campaign.py --game "C:/Program Files (x86)/Steam/steamapps/common/A Dance of Fire and Ice"
```

The importers write their output under ignored `assets/private/`. Additional
importers add visibility, colors, camera and hit sounds from the same installed
game. Several importers use `DEFAULT_GAME` in `tools/import_campaign.py`; change
that default if the installation is elsewhere. Featured Tech importers expect
the relevant subscribed Workshop charts in the local Steam library. Community
charts must be obtained separately from their authors.

Build a master containing only the first level, then convert its compiled data
into an SA-1 cartridge:

```powershell
python tools/campaign_assets.py --pack master --levels 1 --out build/demo-assets
python tools/build_sa1.py --source build/demo-assets --out build/sa1-demo
```

Keep `adofai.sfc`, `adofai.msu`, and any `adofai-*.pcm` files together. Omitting
PCM files selects the compressed-audio fallback; the `.msu` data file is still
required. These are generated/private artifacts and must not be committed.

A self-contained cartridge can be generated from the compiled song:

```powershell
python tools/build_standalone.py --sa1 --source build/sa1-demo --levels 1 --key standalone-demo --title "FIRST LEVEL DEMO"
```

## Renderer options

Chart compilation supports `--camera-rotation`, `--camera-position`,
`--camera-zoom`, `--adaptive-raster`, `--adaptive-motion-raster`, `--shared-contours`, and
`--motion-step`.
These options affect compiled geometry and cache pressure. Their use in a
release is chart-specific; enabling every effect for every chart is not a
validated release configuration. The current R build additionally compiles
MoveTrack tile rotations. Gradual per-tile scaling is not implemented.

Build one chart before attempting the full catalog. Full music and texture
generation can require substantial time and disk space. The `dist/` archives
and historical build caches are not necessary for source development.

## Checks

Pure compiler tests include:

```powershell
python -m unittest discover -s tests -p test_tile_rotation.py
python -m unittest discover -s tests -p test_camera_rotation.py
```

The emulator runners in `tools/` have additional local dependencies. In
particular, `emulate.py` uses a Snes9x libretro core, and the Mesen runners use a
Mesen executable. Adjust those paths for your installation. Graphics checks
should cover a full song, checkpoints, and more than one playback speed.

Running the entire historical unittest suite also requires legacy ROM fixtures
at `build/campaign/` and other older pack paths. Those fixtures are not shipped;
use the targeted compiler tests above and the current-pack verification runners
unless you have built those legacy fixtures.
