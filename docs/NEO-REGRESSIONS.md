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
python tools/profile_midspin_motion.py --rom build/packs/my-master-dev/adofai.sfc --labels build/packs/my-master-dev/adofai.lbl --out build/neo-audit/t4ex-manual --level 74 --steps 1 673 --frames 10000 --manual --manual-jitter --manual-jitter-frames 3 --manual-practice --max-hold 3 --max-display-age 3
```

Repeat without the four `--manual` options for autoplay. The manual replay must
exercise waiting midspins. The orbit must use the next real tile while the
scoring logic waits for a tap, rather than using a detached midspin as its pivot.
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
