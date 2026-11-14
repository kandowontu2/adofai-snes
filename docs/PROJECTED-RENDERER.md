# Projected T3 frames

Use the Python environment and tools from [BUILDING.md](BUILDING.md).
These commands require a development master containing fresh canonical
assets for T3-X (68) and T3-EX (73). They compile exact screen-space frames
before rebuilding the matching ROM and MSU data file:

```powershell
python tools/projected_snapshots.py --source build/packs/my-master-dev --out build/packs/my-master-dev --levels 68 73
python tools/build_sa1.py --source build/packs/my-master-dev --out build/packs/my-master-dev --stream-levels 68 73 --no-pcm
python tools/run_mesen_campaign.py --pack my-master-dev --levels 68 73 --autoplay --graphics-dumps
python tools/run_mesen_campaign.py --pack my-master-dev --levels 68 73 --checkpoints --graphics-dumps
```

Compilation can take several minutes. It preserves source pixels and animation
samples. SciPy (already in `requirements.txt`) handles exact palette packing
when the greedy packer cannot fit a dense crossing. Animation data is stored
in the `.msu` file. Keep the new `.sfc` and `.msu` together; existing PCM music
does not need to be regenerated.

The empty top and bottom eight-pixel HUD borders provide additional upload
time. Gameplay and HUD text keep their positions. Graphics replays check each
actual PPU port writes (including the last byte of every DMA), and compare sampled joypad data with the injected
buttons. Run the pixel verifier on every successful capture folder as well.
Autoplay alone does not validate manual inputs, checkpoint restores, or
switching songs without resetting.

For engine-only changes to a frozen pack, rebuild both CPUs together:

```powershell
python tools/rebuild_sa1_engine.py --out build/packs/my-master-dev
```

This refreshes worker table addresses after linking the main CPU. Use
`tools/build_sa1.py` when changing graphics, audio, or chart assets instead.

T3's native copy cameras retain the off-camera source geometry. They replace
the base view with the authored two/four camera views; live planet and streak
copies are transformed by SA-1 from the current controller-driven objects.
The compiler also retains colors exposed only by those additional cameras.
Large poses prefetch into the unused half of the CHR atlas. The visible map,
palette and sprites publish together after the complete pose is ready.
During the live-copy section, DMA routes finished four-bit glyphs directly
into the back atlas staging buffer. This avoids expanding those same pixels
again on SA-1. Compressed-audio refills run after an active early graphics
upload, preserving the graphics DMA registers across the nested NMI.
Poses include the final note frame and two seconds of native post-roll;
late final inputs cannot publish a timestamp beyond the last baked image.

Check the captured live-copy jobs as well as the background pixels:

```powershell
python tools/verify_camera_copies.py --pack build/packs/my-master-dev --folder build/packs/my-master-dev/verification/mesen-68-autoplay
```

See [Neo Cosmos release checks](NEO-REGRESSIONS.md) for math geometry and
randomization, copied-sprite cleanup, and manual moving-platform transitions.
