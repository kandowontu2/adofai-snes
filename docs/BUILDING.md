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

## Build the optimized AR-X cartridge

Import level `23` with the commands in step 3, then compile its full-detail
chart into a fresh directory. Use that directory for either ROM format.

```powershell
.\.venv\Scripts\python.exe tools/campaign_assets.py --pack master --levels 23 --out build/ar-assets --chart-cache-only --camera-position --camera-rotation --camera-zoom --reuse-motion-phase --motion-step 1
.\.venv\Scripts\python.exe tools/native_animation.py --source build/ar-assets
.\.venv\Scripts\python.exe tools/build_standalone.py --sa1 --adaptive-audio --source build/ar-assets --levels 23 --key ar-standalone --title "EXTRA WORLDS 3"
```

Open `build/packs/ar-standalone/adofai.sfc` in MesenCE. For an MSU build, pass
`--source build/ar-assets --out build/ar-msu --no-pcm` to `tools/build_sa1.py`,
then keep `build/ar-msu/adofai.sfc` and `adofai.msu` together.

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
recipe**. The full releases also need official, Workshop and community
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

## Neo Cosmos

Install the Neo Cosmos DLC in the same Steam
game directory, then import its nine full-song main/EX stages and hold sounds:

```powershell
.\.venv\Scripts\python.exe tools/import_neo.py
.\.venv\Scripts\python.exe tools/import_hit_samples.py
```

The importer reads the installed `Bundles/neocosmos_scenes_all.bundle` without
changing the game. It assigns IDs 66–74, preserving native camera/track effects,
holds, planet easing, and free-roam cells. Tutorials and the playground are
excluded. Extracted charts and audio remain private build inputs.

For an isolated **T1-X development test**, run:

```powershell
.\.venv\Scripts\python.exe tools/campaign_assets.py --pack master --levels 66 --out build/neo-t1-dev-assets --camera-position --camera-rotation --motion-step 1 --no-pcm
.\.venv\Scripts\python.exe tools/build_sa1.py --source build/neo-t1-dev-assets --out build/packs/neo-t1-dev --no-pcm
.\.venv\Scripts\python.exe tools/run_mesen_campaign.py --pack neo-t1-dev --levels 1
```

Open `build/packs/neo-t1-dev/adofai.sfc` in MesenCE, keeping its matching
`adofai.msu` beside it. This test uses compressed audio. `--no-pcm` avoids
generating full-size PCM music during development.

For a free-roam test, substitute `68` for `66` in the asset command and use
a fresh output directory. IDs 66�74 cover the five main worlds and four EX
variants. Free-roam movement, objectives and return transitions use player
input; autoplay chooses a legal route. The compiler retains the generated
grid cells separately from the song notes.

The full catalog still requires the earlier import stages described above.
Validate full songs, checkpoint retries, multiple speeds and graphics in
MesenCE before distributing a modified build.


### SA-1 animation packets (development masters)

The T1-X/T1-EX optimization uses full per-frame chart assets, a lossless ROM
bitmap dictionary, and animation packets decoded by SA-1. It requires an
existing master with the resident native decoder; the isolated one-song
recipe above does not include that decoder.

After replacing charts 66 and 71 in a **development copy** of that master
with freshly compiled `--motion-step 1` assets, run:

```powershell
python tools/mode1_tracks.py --source build/packs/my-master-dev --out build/packs/my-master-dev --levels 66 --budget 1000 --lookahead 256
python tools/mode1_tracks.py --source build/packs/my-master-dev --out build/packs/my-master-dev --levels 71 --budget 2000 --lookahead 64
python tools/build_sa1.py --source build/packs/my-master-dev --out build/packs/my-master-dev --stream-levels 66 71 --no-pcm
python -m unittest discover -s tests -p test_sa1_stream.py
python tools/run_mesen_campaign.py --pack my-master-dev --levels 66 71 --graphics-dumps
python tools/run_mesen_campaign.py --pack my-master-dev --levels 66 71 --checkpoints --graphics-dumps
```

Use the configured Python environment from the earlier build steps. This
regenerates the matching ROM and MSU data file together. Keep both files
together when testing or distributing them. PCM music is unchanged. The
packet compiler rejects old catch-up/native or bitmap-prefetch chart formats;
use fresh canonical chart assets rather than mixing those formats. This path
uses a lossless Mode 1 tile cache for T1-X and T1-EX at 1� and below.
Accelerated playback retains the established full-detail Mode 7 renderer;
the compiler builds both streams from the same per-frame source assets.
The preloader ramps up speculative loading after idle intervals; it does
not limit animation updates or discard required tile uploads. Each source pixel retains
its original color; animation is not resampled. SA-1 prepares texture and map
uploads, while the S-CPU handles gameplay and PPU commits. Other charts keep
the Mode 7 renderer, including camera rotation.

The two `mode1_tracks.py` commands must run before `--stream-levels` converts
the canonical animation files. If you change the graphics or chart, regenerate
the canonical assets first and repeat all three commands. These commands are
for master ROM/data builds; standalone packaging is a separate build path.

For performance checks, use `tools/profile_ar_section_mesen.py`. It samples
completed visible frames at `endFrame`, checks upload overruns independently,
and records the ROM/MSU hashes. A safe NMI can finish its non-PPU bookkeeping
in the top HUD band; sampling its completion counter at `startFrame` can
incorrectly report a repeated frame. Pixel comparisons and checkpoint tests
are still required before release.

Mode 1 release checks must include both full manual replays and checkpoint
retries with `--graphics-dumps`, plus autoplay inspection of moving holds.
The runner checks actual PPU scroll and tilemap configuration against the
published camera, and derives symbol positions from chart events rather than
the renderer's projected-coordinate buffers. Missing coverage and VBlank
overruns fail the run. Pixel verification alone does not establish correct
on-screen placement; inspect screenshots from the affected moving sections too.

Before trusting a new emulator/testing setup, run the negative checks:

```powershell
python tools/check_mesen_failfast.py --rom build/packs/my-master-dev/adofai.sfc --out build/failfast-checks
```

All three injected failures must be rejected. Replay reports remain failed until
every required check completes, and record the verification code hash as well
as ROM/data hashes. Changing checks invalidates `--resume` results.


### Check switching songs without resetting

From the project folder, after building a master test pack, run:

```powershell
python tools/run_mesen_sequence.py --pack mode1-test --levels 66 71 66
```

This uses MesenCE at `C:\mesen2\Mesen.exe` (override with `--mesen PATH`).
It plays T1-X, returns through the menu, plays T1-EX, then returns to T1-X
without resetting. It checks hardware scroll, symbol placement, palettes,
and captured tile pixels. Results are in the pack's `verification/sequence-66-71-66`
folder. A cold-boot replay alone does not cover stale state between songs.


For the projected T3 renderer and engine-only rebuilds, see [PROJECTED-RENDERER.md](PROJECTED-RENDERER.md).
