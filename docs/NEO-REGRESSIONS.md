# Neo Cosmos release checks

Run these from the project folder after building a development master. Replace
`my-master-dev` with its folder name under `build/packs`. Tests use MesenCE at
`C:\mesen2\Mesen.exe`; the campaign runner also accepts `--mesen PATH`.

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
