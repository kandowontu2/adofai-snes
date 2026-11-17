# Neo Cosmos release checks

Run these from the project folder after building a development master. Replace
`my-master-dev` with its folder name under `build/packs`. Tests use MesenCE at
`C:\mesen2\Mesen.exe`; the campaign runner also accepts `--mesen PATH`.

## Three-planet holds and free-roam exits

For a master containing endless.reality, run both controller and autoplay
replays. Its current local menu index is 75; check `pack.json` for other packs.
This change adds a native motion table, so repack an older asset pack before
using the engine-only rebuild command:

```powershell
python tools/build_sa1.py --source build/packs/old-master --out build/packs/my-master-dev --no-pcm
```

```powershell
python -m unittest discover -s tests -p test_featured_import.py
python tools/run_mesen_campaign.py --pack my-master-dev --levels 75 --graphics-dumps
python tools/run_mesen_campaign.py --pack my-master-dev --levels 75 --autoplay --graphics-dumps
python tools/run_mesen_campaign.py --pack my-master-dev --levels 75 --checkpoints --graphics-dumps
```

The live hold check derives the release vector from the original floor's
exit angle and next radius. Do not substitute the next note's orbit angle:
three planets add 60 degrees to that angle, which formerly made the test
accept the same displaced path as the renderer. Free-roam return angles are
checked separately against the native entry vector. Projected scenes also
assert that planets use the camera already baked into the track image.
Inspect maze captures during rotation and after its cells fade; symbols must
stay on their cells and disappear with them. Run T3-X/T3-EX as regressions
because they share projected free-roam rendering.

## Math forks and copied scenes

```powershell
python -m unittest discover -s tests -p test_neo_math_fog.py
python tools/run_mesen_campaign.py --pack my-master-dev --levels 68 73 --autoplay --graphics-dumps
python tools/run_mesen_campaign.py --pack my-master-dev --levels 68 73 --checkpoints --graphics-dumps
python tools/verify_math_randomization.py --pack my-master-dev
```

For each resulting replay folder, run both independent hardware checks. For
example, for T3-EX autoplay:

```powershell
python tools/verify_mesen_ppu.py --pack my-master-dev --level 73 --folder build/packs/my-master-dev/verification/mesen-73-autoplay
python tools/verify_camera_copies.py --pack build/packs/my-master-dev --folder build/packs/my-master-dev/verification/mesen-73-autoplay
```

The math tests compare the alternate corners with reflected playable corners,
and compare both gem platforms' complete material pixels, palette sequences,
and reveal/fade curves. Inspect screenshots during approach as well as landing:
neither route may reveal its correctness through geometry, color, or brightness.
Both answers use the same live CHR font. Randomization replays exercise actual
controller retries and require independent choices to change.

The live copy check compares SA-1 output against a separate fixed-point sprite
oracle. It also rejects original sprites left active after a shorter copied
scene replaces the input prefix. PPU checks include the entire hardware OAM,
not just the declared output length, and enforce scanline sprite limits.

## Manual moving-platform transitions

```powershell
python tools/profile_midspin_motion.py --rom build/packs/my-master-dev/adofai.sfc --labels build/packs/my-master-dev/adofai.lbl --out build/neo-audit/t4ex-manual --level 74 --steps 60 188 --frames 3200 --manual --manual-jitter --manual-jitter-frames 1 --max-hold 3 --max-display-age 3
```

Repeat without `--manual --manual-jitter --manual-jitter-frames 1` for autoplay.
Also test T4-X (69, steps 54–168), T2-X (67, steps 34–107), and T2-EX
(72, steps 39–122). The manual replay must exercise waiting midspins.
Before the authored handoff time, an early accepted landing must still draw
the preceding orbit. After that time, use the next real tile while scoring
waits for any late tap. A detached midspin must never become a planet pivot.
This checks a visual jump that a frame-rate counter alone cannot detect.

## Timing bars, audio editions, and performance

T2-EX is level 72. Check ordinary hit deadlines as thin neutral lines and midspin
deadlines as colored cues, below the track. Run its full replay and checkpoints
with graphics dumps as above, plus `test_singsing_scene.py`.

Repeat changed charts with compressed playback by testing a separate development
folder containing the same ROM/MSU pair and no PCM files. Also test song changes
without a reset; cold boot does not detect state carried between charts.

Keep the ROM, MSU data, and verifier code unchanged during a replay. Reports bind
their evidence to all three. Three frames is the current accepted presentation
gap; compressed playback may reach four frames of chart-clock display age.
These are separate measurements, and neither is a claim of locked 60 FPS.
Do not reduce track detail or source animation updates to meet these limits.

## Free-roam entry and trails

Use actual controller input to test the first free-roam landing. Autoplay
does not exercise an early entry edge or the manual hop path.

```powershell
python tools/profile_freeroam_input.py --rom build/packs/my-master-dev/adofai.sfc --labels build/packs/my-master-dev/adofai.lbl --out build/free-entry-check --level 68 --steps 160 170 --frames 6500 --manual --tap-free-entries
```

This presses before the automatic entry, follows a legal grid route, and
checks the active trail color in the running emulator after hops. It must
reach the end of the requested section, record an early entry and exercise
both planet colors. Repeat for T3-EX (73, steps 210–217). For endless.reality,
use level 75, steps 335–342, 6800 frames and `--free-entry-lead 3`.

After changing scene-transfer scheduling, also run:

```powershell
python tools/verify_calibration_mesen.py --pack my-master-dev
python tools/run_mesen_sequence.py --pack my-master-dev --levels 1 75 1
```

Calibration checks continuous motion and audible SPC clicks after both PCM
and compressed playback. The sequence must navigate between sets without a
reset. These campaign indices are one-based positions in `pack.json`.
Checkpoint replays still need independent PPU verification: a completed run
with a nonzero upload-overrun counter is a failed result.

### Workshop maze hazards

The May 2023 endless.reality maze uses decoration hitboxes: a rotating bar,
moving mines, and a sweeping bar. It does not contain collectible coin objects.
The standard maze route is compiled from the authored transforms. Samples are
shared and trimmed at constant prefixes/tails without dropping any frames.
Both planets are checked against rotated boxes with the native collision radius.
Autoplay is exempt from death, as in the original game; manual replay must still
complete the collision-free route.

Run that manual route in both PCM and compressed editions. Drain queued hops
before checking the current hazard pose: otherwise a valid, timestamped hop
can be killed against its old pivot while the renderer is busy.

After a hazard change, run a manual campaign replay and then:

```powershell
python tools/run_mesen_campaign.py --pack my-master-dev --levels 75 --prepare-only
python tools/verify_decoration_hitboxes_mesen.py --pack build/packs/my-master-dev
```

This checks deliberate contact with the rotating bar, contact by the orbiting
planet with a mine, and contact with the sweeping bar. Also capture maze frames
4313, 4480, 4800, 5300, 5635 and 5670 with the campaign PPU verifier. The last
two captures cover the authored fade-out during the return to the track.

Snapshot-only masters omit unused sparse coordinate tables from ROM, retaining
the canonical files for pixel verification. Test a native-rendered chart followed
by a snapshot chart without resetting (for example 23, 94, 75 in the 94-chart
master), as well as checkpoint reloads, whenever changing this path.

Three-planet graphics replays also write `triplet-geometry.txt`. This probe
checks the orientation of the three live planet positions against the chart's
rotation direction, including reversed free-roam turns. An equilateral
triangle alone is insufficient: the third planet can be mirrored to the wrong
side while all three distances remain correct. The renderer's `$F000/$F000`
offscreen sentinel is excluded and counted separately, as it is not a projected
position; 3PXH-X's blind camera section exercises this case. Ordinary two-to-three
transitions also check that the existing planets retain their landing roles.
The release gate requires nonzero orientation coverage for all 31 Triple
Planet charts. The pre-fix renderer fails this probe on 3P1-X's first change.

Three-planet twirls use the native OutSine reflection blend over half an
interval. Their formations flatten and change orientation during that blend;
the probe accounts for this instead of requiring a rigid triangle. 3P4-X also
checks each planet's world-coordinate continuity at its first seven twirls.
The release gate requires all seven handoffs, which failed before the blend.

Extended charts reserve 5,120 notes and a separate compact list of at most
2,816 icon-bearing floors. Every imported chart must fit both bounds. The
SA-1 layout check proves that the expanded coordinate, timing, opacity and
judgment arrays remain separate from graphics shadows, the audio FIFO and
shared worker state. Coordinate publication checks use the build's actual
array addresses and capacity, including Galaxy Collapse's final floors.

T3-X/EX import all 19 native Mawaru section headings from the installed
NeoCosmos English localization. Their native beat schedule, EX soccer wording,
entrance, upward movement and fade are rendered into full-detail snapshots.
Headings are applied after the track-copy compositor and remain active with
VFX off. The stage punctuation CHR is external and editable.

Galaxy Collapse retains all 4,771 floors. Extended charts use a non-overlapping
5,120-note memory layout inside the existing 256 KiB SA-1 BW-RAM. Dense indexed
frames share flipped glyphs losslessly and may use a 640-chunk double atlas,
with 319 8bpp glyphs per bank. Restart seeds preserve the indexed flag without
overlapping byte-count bit 14. The PPU oracle checks both banks and bit depths.

Compact restart seed format 3 removes final DMA block padding and the proven
zero tail of each screen map globally, including VFX-off alternates. The
loader restores those zero bytes and reads an exact final atlas chunk.
Palette, visible atlas bytes, symbols and clone state are preserved. Data
version 34 prevents older ROMs from misreading the new layout. Identical
immutable snapshot packets share storage while retaining every timestamped
event. This does not remove any rendered updates.

The white third-planet preview and dashed triangle are attached to the live
entry floor, use the track's camera projection, and scale with zoom. They
disappear when the planet joins. `planet-previews.txt` independently checks
their positions against native entry vectors; ordinary pause floors and
transitions back to two planets must never show an insertion guide. This
applies to all charts, including T4, endless.reality and Main EX.

Primrose replaces hidden core planets with live proxies. Its PNG and native
Planet objects may describe the same actor and must be deduplicated by tag
and transform. Shared proxy translation affects actors without translating
the pre-rendered track. The Noteblock Cover hides those live proxies during
its authored four-orb decoration sequence, then restores them at the exit.
Test both charts manually as well as in Watch, plus Primrose's checkpoints.

The 5,120-note layout also changes the legacy Mode 7 CHR shadow split.
It stores 176 tiles in $7ED400..$7EFFFF and the remaining 80 in
$7F6800..$7F7BFF. Uploads, checkpoints, worker destinations and delta seeding
must use that same boundary. The full 16 KiB image is retained. A WRAM DMA
using the old 224-tile boundary wraps into CPU state; the layout gate now
proves both complete spans fit their banks. Replay all four legacy charts
62, 63, 64 and 65 whenever changing the shared note layout.


### Dense symbols and scripted four-orb artwork (2026-11-16)

Full snapshot charts in the extended master use a one-byte icon schedule at $43D000, after both projected-coordinate arrays. Command 4 projects the live symbols; dense screens dispatch command 12 to emit essential OAM on SA-1. Sparse screens reuse those projected positions in the existing CPU sprite loop, avoiding batch setup. The CPU transfers its immutable OAM prefix on DMA channel 0; channel 4 belongs to brightness HDMA. Packed OBJ/sliver counters use SA-1 IRAM $0100. Separate IRAM overlays hold projection, scan and emission kernels, with shared code-tag invalidation. No tile detail, authored updates or visible symbols are removed.

verify_snapshot_icons_mesen.lua independently reconstructs glyphs, palettes, order, clipping, checkpoint activation and exact hardware budgets from each chart, then compares actual returned OAM and high bits byte for byte. The release gate requires coverage for every full-snapshot chart. profile_symbols_mesen.py measures emulated master clocks. Dense C9-X steps 700-850 improved from 27 frames worst gap to 6; 131 common timestamps had identical essential symbols. This is a measured improvement, not a locked-60-fps guarantee.

B4-X uses an authored four-planet image rotated around a local pivot. The native transform scales that pivot with the image. local_decoration_pivots enables this transform for the chart. The raster centroid unit test covers four quarter turns. verify_four_orb_release.py separately checks actual MesenCE screenshots for four colors, the native orbit size, and proximity to the landing area after the authored entry transition.


### Twirl scratch and stream isolation

Three-planet twirl matrices use CPU WRAM $07C8..$07DD. The previous aliases at $05A2 overlapped the stream cursor and caused old packets to replay, delayed completion and long pauses. The layout gate proves that twirl, preview, math, OAM and stream scratch regions are disjoint. verify_twirl_stream_mesen.lua compares all 94 stream bytes before and after every live twirl blend. Its negative control restores the old aliases and must fail at $05A2. The original completion and hold-coverage thresholds remain unchanged.

Release transition replays use the compiled VFX default and assert that option in gameplay. This matches real menu navigation after reset and prevents comparing VFX-off output against VFX-on captures.

### Global snapshot storage, format 4

Restart seeds retain the exact cursor, format, camera copies and symbol list,
and reference the same immutable pose already used by the animation stream.
The loading path clears blank glyphs in both atlases and decodes into atlas
zero before publishing gameplay. A restart must not inherit the previous
level's pixels, indexed mode, camera copies or symbols.

Snapshot-only masters use 32-byte playback directories: all four choices
remain, while the unused 512-byte Mode 7 tag seed is omitted. The runtime
computes the directory address with a full 24-bit `index * 32`. Source caches
retain their complete legacy directories for independent verification.
Identical immutable poses can share an MSU pool across charts and VFX modes;
only the referencing event owns the musical due time. MSU version 35 rejects
older incompatible layouts. No updates, symbols, tile pixels or colors are
removed by these changes.

`verify_snapshot_storage.py` proves the assembled directory times/sizes,
native event bytes, pose bytes and restart states against the complete caches.
Unit tests cover ordinary/wide 4bpp and 8bpp atlases, blank starts, copies and
symbols. MesenCE replays still verify visible pixels, manual inputs, every
checkpoint and consecutive level transitions.

Decorative composites retain `projection_native_palette_versions` before
generated palette writes are added to the runtime stream. The reference
renderer uses that original timeline for the track beneath transparent art.
Reusing the finished composite's palette as its own input changes colors and
invalidates the pixel oracle. The source-color regression test covers this
case with distinct authored and generated RGB555 values.
