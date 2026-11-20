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

- `build/sa1-demo/adofai.sfc` â€” the ROM to open in your emulator.
- `build/sa1-demo/adofai.msu` â€” required data; keep it beside the ROM.
- `build/sa1-demo/adofai-*.pcm` â€” optional full-quality music, if present.

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

Release checks target MesenCE (the runners default to `C:\mesen2\Mesen.exe`).
Historical Snes9x/libretro scripts are not the release acceptance tests.
Historical tests that need absent ROM fixtures explicitly skip; a skipped test
is not release evidence. For graphics changes, test a full song, checkpoint
retries and multiple speeds. Windows is the supported development workflow; other platforms may
need path and executable-name changes.

## Selected Workshop additions

The selected charts are listed in `tools/featured_catalog.json` and
`tools/firestix_catalog.json`, plus `tools/joke_catalog.json` for other Joke
Worlds such as TQG's It Stop. With Steam running under the account that
owns the game, download and import them with:

```powershell
.\.venv\Scripts\python.exe tools/download_tech.py
.\.venv\Scripts\python.exe tools/import_featured.py
.\.venv\Scripts\python.exe tools/import_firestix.py
.\.venv\Scripts\python.exe tools/import_jokes.py
```

The Featured selection uses the May 2023 endless.reality revision and the
installed catalog's Classic and Tech waves. The Firestix list adds 15 charts, including separately named
1-X and B-X Workshop variants; Night Wander is excluded. Five duplicate
Firestix maps remain represented by existing Joke Worlds. These imports
write private local assets; they do not subscribe to or publish Workshop
items. The full-release build limitations above still apply.

## Yangsy cursed levels

`tools/yangsy_catalog.json` selects Yangsy-authored charts only. With the
shared Workshop downloads available, import them with:

```powershell
.\.venv\Scripts\python.exe tools/import_yangsy.py
```

These charts appear under **YANGSY CURSED LEVELS**. The source repository
contains the importer and catalog, not the downloaded charts or music.

## Main EX Levels (Team Vega)

`tools/main_ex_catalog.json` lists the twelve Team Vega remakes, 1-EX through
12-EX, in world order. They have their own **MAIN EX LEVELS** menu category.
These are Workshop charts, separate from the Neo Cosmos EX stages.

With Steam running under the account that owns ADOFAI:

```powershell
.\.venv\Scripts\python.exe tools/download_tech.py --ids 2756895275 2756409843 2756897185 2756222522 2756337547 2757077338 2885179160 2885178898 2885179669 2885178918 2885179019 2885178890
.\.venv\Scripts\python.exe tools/import_main_ex.py
```

The command above downloads only these twelve Workshop items.
The importer reads the downloaded Workshop folders and writes private local
assets; chart and music downloads are not included in the source repository.

The SNES port adds curated checkpoints to Main EX charts that have none,
and to Mad Piano Party II. These additions are defined in
`tools/supplemental_checkpoints.py`; they are not original chart events.
Existing authored checkpoints are preserved. Changing the list requires
rebuilding chart data, graphics, checkpoint snapshots, and PCM restart tracks.

## Neo Cosmos

Install the Neo Cosmos DLC in the same Steam
game directory, then import its nine full-song main/EX stages and hold sounds:

```powershell
.\.venv\Scripts\python.exe tools/import_neo.py
.\.venv\Scripts\python.exe tools/import_hit_samples.py
```

The importer reads the installed `Bundles/neocosmos_scenes_all.bundle` without
changing the game. It assigns IDs 66â€“74, preserving native camera/track effects,
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
a fresh output directory. IDs 66–74 cover the five main worlds and four EX
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
uses a lossless Mode 1 tile cache for T1-X and T1-EX at 1× and below.
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


## Refreshing all stock charts

After updating the installed game, refresh the private source imports before
rendering. This resolves embedded JSON charts by song identity rather than
assuming Unity asset numbers are unchanged. Native short and long tiles use
the controller's actual tile dimensions.

```powershell
.\.venv\Scripts\python.exe tools/reimport_stock.py
```

This updates imported chart data; it does not replace installed ROMs or ZIPs.
Rebuild and verify the master after importing. The full snapshot cache builder
uses per-frame source poses and lossless compression:

```powershell
.\.venv\Scripts\python.exe tools/build_catalog_cache.py --out build/packs/stock-refresh-assets --levels 1 2 3 --workers 2
```

Replace the example level IDs with the charts you need. Do not use --resume
for a chart whose source or renderer changed; that option trusts a completed cache.

For the additional Community versions, download and import the exact charts:

```powershell
.\.venv\Scripts\python.exe tools/download_tech.py --ids 2879708027 3364771383
.\.venv\Scripts\python.exe tools/import_community.py --levels 251 252
```

251 is the original endless.reality; 252 is CHAOS CONTROL. The Featured
endless.reality remains chart 75.

### Optional scenery and render caches

The global VFX option selects alternate pre-rendered scenery data. It does not
disable gameplay cues or T3-X/EX effects. CHAOS CONTROL keeps its track at full
resolution while simplifying and dimming decorative scenery behind it.
Both variants must be built and tested; testing VFX ON alone does not cover OFF.

For a faster host-side render, set the worker count before invoking the cache
builder. This changes build speed, not in-game update frequency or image quality:

```powershell
$env:ADOFAI_RENDER_WORKERS = '4'
```

Use `tools/merge_render_cache.py --help` when replacing a chart in an existing
master. It checks that timing, audio and checkpoint data still match and copies
the complete render cache, including Mode 1 seeds. Preserve a VFX OFF cache
before merging its VFX ON replacement. Do not manually copy only stream files.

### Triple Planet collection and Overclocked beta

The [Triple Planet collection](https://steamcommunity.com/sharedfiles/filedetails/?id=2922411723)
contains 31 charts by mariokirby1703/Luma1703. With Steam running on the
account that owns the game, download the selected Workshop catalogs, then import:

```powershell
.\.venv\Scripts\python.exe tools/download_tech.py
.\.venv\Scripts\python.exe tools/import_triple_planet.py
```

For **1234 OVERCLOCKED (BETA)**, use the author's
[playable beta archive](https://drive.google.com/file/d/1f6hE_8KJlWFkNMXj7ILVN82yibFX4RBS/view),
linked from the [work-in-progress video](https://www.youtube.com/watch?v=eOePfbcQkzY).
Extract it so this file exists under the project folder:
`assets/private/overclocked-source/1234 Overclocked Edition/1234overclocked.adofai`.
Keep its accompanying music and image files beside the chart. Then run:

```powershell
.\.venv\Scripts\python.exe tools/import_community.py --levels 284
```

These import commands prepare private source assets; they do not update an
installed ROM by themselves. Use the full snapshot/master build workflow above.
Overclocked's instructional text, perfect-only conditions and planet scaling
are part of its gameplay. The beta does not contain the video's finished VFX.

### Additional Community charts and T3 stage names

Milky Ways (C9-X, BluPen & Lemon1415) is Workshop item 2189119879:

```powershell
.\.venv\Scripts\python.exe tools/download_tech.py --ids 2189119879
.\.venv\Scripts\python.exe tools/import_community.py --levels 285
```

Galaxy Collapse (GC-X, pinball & Toht) uses the original unnerfed chart.
Extract your privately obtained galaxy_collapse_ADOFAI.rar so that
assets/private/community/galaxy-collapse/galaxy_collapse_fullpack/unnerfed.adofai
exists, keeping its music and images beside it. Import with:

```powershell
.\.venv\Scripts\python.exe tools/import_community.py --levels 286
```

Use --chart-cache-only when compiling canonical assets for this long chart,
then tools/projected_snapshots.py and the SA-1 master build. Its 4,771 floors
require the extended 5,120-note layout; a legacy non-SA-1 ROM cannot hold it.

Reimport T3-X/EX with tools/import_neo.py --levels 68 73 to include the native
stage headings. The importer reads their English strings from your installed
Neo Cosmos localization asset. Rerender both charts after importing. These
headings remain enabled with VFX off. Run tools/verify_neo_headings_release.py
--pack YOUR_PACK to capture every stage heading in MesenCE.

Current full-viewport master builds use restart format 4 and MSU data version 39. Restart
seeds reference the exact screen image already stored in the animation
stream. The build also removes unused Mode 7 tag tables from snapshot
directories and shares identical image packets. Every timestamp, update,
visible tile and symbol remains present. The independent render caches
remain complete for verification. Always replace the ROM and MSU data together;
an older ROM cannot read this layout.

For the additional Community charts, download Workshop items 2929378489
(Noteblock Cover) and 2818364450 (Heracles EX), then import them:

```powershell
.\.venv\Scripts\python.exe tools/download_tech.py --ids 2929378489 2818364450
.\.venv\Scripts\python.exe tools/import_community.py --levels 288 289
```

For updated Primrose, download the files from the
[creator folder](https://drive.google.com/drive/folders/11ZVwBwGM3rzb3hRshdc2vrhwqMH6HZGK)
into `assets/private/community/primrose/`, keeping the chart, music and images
together. `Primrose.adofai` must be directly inside that folder. Then run:

```powershell
.\.venv\Scripts\python.exe tools/import_community.py --levels 287
```

These are imports only. Continue with the full snapshot/master workflow above
to render and build the charts. Preserve the creator's asset filenames.


### Sky Blue

SB-X is GrivR.'s **Sky Blue**, mapped by FluffyYoshi (Workshop item
3371317110). Download and import the selected main chart with Steam running:

```powershell
.\.venv\Scripts\python.exe tools/download_tech.py --ids 3371317110
.\.venv\Scripts\python.exe tools/import_community.py --levels 290
```

The main chart includes five authored checkpoints. Its short tutorials are not
separate menu entries. Use full snapshots with camera position, rotation and
zoom, at motion step 1. Enable decoration tracks and depth order for the native
floor objects and jump/pause artwork. This performance-oriented port omits decorative backgrounds and retains native
floor objects plus these images: `jumptile.png`, `jumptile_outline.png`, `pausetile.png`,
`pausetile_outline.png`, `jungsanghwa_tile.png`, `bigoribit_tile.png`,
`hyperorbit_tile.png`, and `snail_indicator.png`. Include `null` in that image
allowlist to retain native AddObject floors. The same gameplay-only rendering
is used for both positions of the VFX option.

### Six additional Community charts

With Steam running, download and import these main charts:

```powershell
.\.venv\Scripts\python.exe tools/download_tech.py --ids 2128998212 2975260940 3558160844 2886897340 3386994667 2805465983
.\.venv\Scripts\python.exe tools/import_community.py --levels 291 292 293 294 295 296
```

| ID | Menu code | Chart |
| --- | --- | --- |
| 291 | WP-X | Wake Up, Piano! — Strode |
| 292 | OT-X | OCTAGON — M1n3c4rt |
| 293 | MG-X | MECHANICAL GOD — Hazrd |
| 294 | BV-X | Beethoven Virus — Trevor Smithy |
| 295 | WT-X | William Tell Overture — Dinosore |
| 296 | FL-X | Flow — Pharah & HanB |

Continue with the complete snapshot/master workflow above. Keep all image
files beside each downloaded chart. OCTAGON uses the native local-pivot and
live-proxy rendering flags recorded in its catalog entry. Its artwork is
part of gameplay and stays enabled with VFX off. William Tell's automatic
tiles and PlaySound cues are mixed on the music sample clock, including
intentional duplicate cues. Authored checkpoint locations are preserved.

For VFX OFF, render a separate copy of the compiled cache with these settings
in its `level<ID>.json`, then preserve it with `merge_render_cache.py` before
merging the VFX ON cache:

| Charts | VFX OFF settings |
| --- | --- |
| 291, 292 | Use the same cache in both modes; their artwork is gameplay. |
| 293 | Set `decoration_tracks` to `false`. |
| 294, 295 | Keep decoration tracks enabled; set `decoration_gameplay_images` to `[null]` to retain text while omitting background images. |
| 296 | Keep decoration tracks enabled; set `decoration_gameplay_images` to `[null, "remember.png", "enter.png", "3sq.png", "3sqbg.png", "ppt3x.png"]`. |

Apply those settings before rendering, not to an already rendered stream.
Keep `projection_native_palette_versions` written by the snapshot renderer;
the pixel verifier needs the native palette timeline before artwork is added.

Run `tools/verify_snapshot_storage.py --pack YOUR_PACK` after building. It
compares every assembled playback choice, native event, image reference and
restart seed against the full local caches. Follow it with the MesenCE catalog,
manual-play and checkpoint checks; the storage proof does not replace them.


### Phantigma (PH-X)

Use Juegang's chart from the [TUF download](https://api.tuforums.com/cdn/57d19ff2-aec2-414a-af2a-eeb303d1cf40).
Extract the ZIP so the following file exists under the project folder:

```text
assets/private/phantigma-juegang/Phantigma/level.adofai
```

Keep `Phantigma.ogg` and the accompanying PNG files beside it. Use
`level.adofai`, rather than the backup chart. Then import it:

```powershell
.\.venv\Scripts\python.exe tools/import_community.py --levels 297
```

Continue with the complete snapshot/master workflow above. Render full camera
position, rotation and zoom. For VFX ON, keep decoration tracks enabled; the
compiler samples decorative backgrounds at resolution 2 while retaining the
full track detail. For the separate VFX OFF cache, set `decoration_tracks` to
`false` before rendering, then merge the variants as described above. Both
variants retain all nine holds. This chart has no authored checkpoints.

### Release editions

The full PCM edition is retired. `install_stock_release.py` updates only
`dist/adofai-msu-hybrid` and `dist/adofai-msu-compressed`, then verifies their
ZIPs and the tester-update ZIP. It does not create a full PCM folder/archive
or distribute checkpoint PCM. Hybrid checkpoint retries use compressed audio.
Song-start PCM needed by the hybrid edition must remain available in the build
pack or the existing hybrid folder. A separate refreshed audio directory can
be passed with `--audio-source`; unchanged song-start tracks are retained.

### Rebuild a full-viewport catalog

Use this workflow after importing the charts you want. It renders every camera
frame, keeps gameplay objects when optional scenery is disabled, and builds a
compressed master without generating a full PCM set. It needs the private
chart/audio files from the import steps above. Choose a new output name each
time so an already verified release stays intact.

For example, make a catalog containing the imported Main Worlds:

```powershell
New-Item -ItemType Directory -Force build/catalog-work | Out-Null
.\.venv\Scripts\python.exe -c "import json; from pathlib import Path; Path('build/catalog-work/catalog.json').write_text(json.dumps({'levels':list(range(1,13))}))"
.\.venv\Scripts\python.exe tools/compile_catalog.py --catalog build/catalog-work/catalog.json --out build/catalog-work/raw --workers 2 --resume
.\.venv\Scripts\python.exe tools/render_catalog.py --source build/catalog-work/raw --catalog build/catalog-work/catalog.json --out build/catalog-work/rendered --workers 2
.\.venv\Scripts\python.exe tools/assemble_catalog.py --catalog build/catalog-work/catalog.json --rendered build/catalog-work/rendered --out build/packs/my-expanded-master
```

Open `build/packs/my-expanded-master/adofai.sfc` with its matching `.msu`
beside it. This pipeline uses the 160-pixel gameplay viewport and global
lossless native-event/image compression. It can take hours for a large
catalog. Completed compile/render stages can be resumed; do not reuse a
failed projection cache after changing its imported source or VFX settings.

MSU-1 can address at most 4 GiB. If a large catalog exceeds that limit, keep
the staged output and generate a storage plan:

```powershell
.\.venv\Scripts\python.exe tools/plan_catalog_storage.py --source build/packs/my-expanded-master --out build/catalog-work/storage-plan.json --workers 2
.\.venv\Scripts\python.exe tools/assemble_catalog.py --catalog build/catalog-work/catalog.json --rendered build/catalog-work/rendered --out build/packs/my-budgeted-master --storage-plan build/catalog-work/storage-plan.json
```

The plan retains all gameplay frames, tile detail, replacement objects,
hazards and T3 effects. It budgets the additional optional decorative scenes
for VFX ON; large scenes that do not fit use the same gameplay cache in both
settings. The report lists every omitted scene. Full render caches remain
available for a smaller catalog that can include those scenes.

Verify the assembled files in MesenCE before distributing them:

```powershell
.\.venv\Scripts\python.exe tools/verify_sa1_layout.py --pack my-expanded-master
.\.venv\Scripts\python.exe tools/verify_snapshot_storage.py --pack my-expanded-master
.\.venv\Scripts\python.exe tools/verify_catalog_mesen.py --pack my-expanded-master --workers 2
.\.venv\Scripts\python.exe tools/verify_catalog_mesen.py --pack my-expanded-master --workers 2 --manual
```

These checks expect MesenCE at `C:\mesen2\Mesen.exe`. `run_mesen_campaign.py`
accepts `--mesen` when running an individual replay with another executable
path. Watch checks, real-input checks and checkpoint checks cover different
behavior; a successful import alone is not a verified playable release.
