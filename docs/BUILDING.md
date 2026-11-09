# Build a ROM on Windows

Start with **1-X only**. The steps below produce a playable SA-1 ROM without
needing the full catalog or anyone else's build cache. Run commands in
**PowerShell**, from the repository's top folder (the folder containing
`README.md`). Stop if a command reports an error; fix it before continuing.

## 1. Install the tools once

You need:

| Tool | What to install / check |
| --- | --- |
| [Git for Windows](https://git-scm.com/install/windows) | Install Git for Windows. `git --version` should work afterward. |
| [Python for Windows](https://www.python.org/downloads/windows/) | Choose the **Windows installer (64-bit)** for Python 3.14, which was used to check this recipe. Enable its PATH option during installation. |
| [cc65](https://cc65.github.io/) | Follow **Windows Snapshot** and extract the archive; you need `ca65.exe` and `ld65.exe`. See the [Windows setup guide](https://cc65.github.io/getting-started.html). |
| [FFmpeg](https://ffmpeg.org/download.html) | Under **Windows EXE Files**, follow a Windows build-provider link. Download a binary build, extract it, and add its `bin` folder to PATH. |
| [GCC through MSYS2](https://www.msys2.org/) | Install MSYS2, then install its MinGW-w64 GCC package using the commands below. |
| [ADOFAI on Steam](https://store.steampowered.com/app/977950/A_Dance_of_Fire_and_Ice/) | Install your own copy of the original game. |
| [Mesen emulator](https://github.com/SourMesen/Mesen2/releases) | Download the Windows build from the release assets. SA-1 support is required; the master also needs MSU-1 support. |

For GCC, open **MSYS2 UCRT64** from the Start menu and run the command from
the [MinGW-w64 setup guide](https://www.mingw-w64.org/getting-started/msys2/):

```sh
pacman -S mingw-w64-ucrt-x86_64-gcc
```

Then add `C:\msys64\ucrt64\bin` to your Windows user PATH (adjust it if you
installed MSYS2 elsewhere). To edit PATH, search Start for **Edit environment
variables for your account**, select **Path**, choose **Edit**, then **New**.
Add FFmpeg's `bin` folder there too. Return to PowerShell for the remaining
build steps; only the `pacman` command above runs in MSYS2.

Open a new PowerShell window after changing PATH. Clone and enter the source:

```powershell
git clone https://github.com/kandowontu2/adofai-snes.git
Set-Location adofai-snes
```

If you already have the source, open PowerShell in that folder instead.
Create a Python environment. Activation is unnecessary; every command below
uses its Python directly, avoiding PowerShell execution-policy problems.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
New-Item -ItemType Directory -Force .tools | Out-Null
```

Set the cc65 location. **Replace the example path** with the folder that
contains cc65's `bin` directory:

```powershell
$env:CC65_HOME = 'C:\Tools\cc65'
```

Alternatively, put `ca65.exe` and `ld65.exe` directly in `.tools\cc65\`.
Check the tools before importing anything:

```powershell
.\.venv\Scripts\python.exe --version
& "$env:CC65_HOME\bin\ca65.exe" --version
& "$env:CC65_HOME\bin\ld65.exe" --version
ffmpeg -version
gcc --version
```

If you used `.tools\cc65\`, run those two executables from that folder instead.
The build compiles its own BRR audio encoder using GCC; you do not need to find
or download a separate encoder.

## 2. Point the importers at your game

Set this to the **game folder**, not the Steam folder or the game's executable:

```powershell
$env:ADOFAI_GAME = 'C:\Program Files (x86)\Steam\steamapps\common\A Dance of Fire and Ice'
Test-Path "$env:ADOFAI_GAME\A Dance of Fire and Ice_Data\resources.assets"
```

The check must print `True`. Change the path if your Steam library is on another
drive. Keep using this PowerShell window: environment variables set here last
only for this session. Set both variables again when opening a new window.

## 3. Import the first song and its sounds

Run these in order:

```powershell
.\.venv\Scripts\python.exe tools/import_campaign.py --levels 1
.\.venv\Scripts\python.exe tools/import_hit_samples.py
.\.venv\Scripts\python.exe tools/import_hitsounds.py --levels 1
```

This creates `assets/private/level1.json`, `assets/private/1-X.wav`,
`assets/private/hitsound-levels.json`, and the `assets/private/hitsounds/`
sample folder. The installed game is not modified. These extracted files are
local build inputs and must not be included in a pull request.

## 4. Build the first-song master

The first command compiles the chart, graphics and music. The second builds the
SA-1 ROM. Audio and chart generation can take a while; wait for each to finish.

```powershell
.\.venv\Scripts\python.exe tools/campaign_assets.py --pack master --levels 1 --out build/demo-assets
.\.venv\Scripts\python.exe tools/build_sa1.py --source build/demo-assets --out build/sa1-demo
```

The compiler imports missing color, camera and visibility information from the
same game installation automatically. The displayed master title may refer to
all worlds, but `--levels 1` includes only 1-X.

**Your playable files are:**

- `build/sa1-demo/adofai.sfc` — the ROM to open in your emulator.
- `build/sa1-demo/adofai.msu` — required data; keep it beside the ROM.
- `build/sa1-demo/adofai-*.pcm` — optional full-quality music, if present.

For compressed playback, copy only the `.sfc` and `.msu` into a separate play
folder. For PCM playback, also copy the `adofai-*.pcm` files from
`build/sa1-demo/sample-clock-pcm/` into that play folder. Do not copy files named
`level1.pcm`: those are intermediate encoder inputs, not MSU music tracks.

Open `adofai.sfc` and press START. Always boot fresh after rebuilding; an old
save state restores old code/data state. Replace the matching `.msu` and PCM
files too when rebuilding audio.

## 5. Optional: make a single-file cartridge

After step 4, run:

```powershell
.\.venv\Scripts\python.exe tools/build_standalone.py --sa1 --source build/sa1-demo --levels 1 --key standalone-demo --title "FIRST LEVEL DEMO"
```

Open **`build/packs/standalone-demo/adofai.sfc`**. This version needs no `.msu`
or `.pcm` files. It contains compressed music and still requires SA-1 support.

## Editing graphics and rebuilding

See [GRAPHICS.md](GRAPHICS.md) for CHR, palette and tile assignments.

For **static CHR or palette edits**, rebuild the existing SA-1 pack:

```powershell
.\.venv\Scripts\python.exe -c "import sys; from pathlib import Path; sys.path.insert(0,'tools'); from build_sa1 import compile_engine; compile_engine(Path('build/sa1-demo'), generate_pcm=False)"
```

For a standalone pack, replace `build/sa1-demo` with
`build/packs/standalone-demo` in that command.
The `generate_pcm=False` option keeps existing PCM music when only graphics
or engine code changed. Omit it when intentionally rebuilding audio.

For **track-shape or chart-generator edits**, repeat step 4 with fresh output
folders, for example `build/demo-assets-v2` and `build/sa1-demo-v2`. Change both
`--source` and `--out` accordingly. The SA-1 builder reuses an existing output
pack; simply rerunning it against a changed source does not refresh all chart
data. Fresh folders avoid this trap. Repeat step 5 with the new source and a
new key if you also want a new standalone cartridge.

Submit source graphics and screenshots, not generated files from `build/`.

## Common problems

| Message or symptom | What to check |
| --- | --- |
| `python`, `ffmpeg` or `gcc` is not recognized | Install that tool, add its executable folder to PATH, and open a new terminal. |
| `ca65 not found` / `ld65 not found` | Check `CC65_HOME\bin`, or put both executables in `.tools\cc65\`. |
| `ModuleNotFoundError` | Use `.\.venv\Scripts\python.exe` and install `requirements.txt` with that same interpreter. |
| Missing `hitsound-levels.json` or `sndKick.wav` | Run all three commands in step 3. Chart import alone is insufficient. |
| Missing Unity assets / import failure | Check `ADOFAI_GAME`. Importers depend on the installed game's asset layout; a changed game version may need importer updates. |
| Source-audio hash assertion | The embedded-hit alignment was measured against a specific recording. Do not bypass the check; a different recording needs an audio review. |
| ROM opens but master data/music is missing | Keep the matching `.msu` beside the ROM, with the same basename, in an MSU-1-capable emulator. |
| Old chart geometry after a rebuild | Use fresh output folders as described above, then boot without a save state. |

## Larger builds and developer checks

The one-song recipe is a starting point, **not a reproducible full-release
recipe**. The 65-song releases also need official, Workshop and community
imports, plus chart-specific renderer settings. Those inputs and historical
release caches are not shipped. Do not remove `--levels 1` and expect a full
catalog build to work from this setup.

Relevant importers are `import_official.py`, `import_tech.py` and
`import_community.py`. Some later importers still have local paths or depend on
previous import stages. Renderer flags such as `--camera-rotation`,
`--camera-position`, `--camera-zoom`, `--adaptive-raster`,
`--adaptive-motion-raster`, `--shared-contours` and `--motion-step` need
chart-specific capacity and emulator checks; enabling all flags is not a
validated release configuration.

Two compiler checks that do not require historical ROM fixtures:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_tile_rotation.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_camera_rotation.py
```

Emulator runners need their own configured Mesen or Snes9x libretro paths.
The entire historical test suite also needs old ROM fixtures that are not in
Git. For graphics changes, test a full song, checkpoint retries and multiple
speeds. Windows is the supported development workflow; other platforms may
need path and executable-name changes.
