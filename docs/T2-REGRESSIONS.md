# T2 regression and performance audit

## Required behavior and release gate

Target: MesenCE at `C:/mesen2/Mesen.exe`, MSU master, 1.0x.
The user requires smooth movement without reducing animation updates or tile
quality. Do not install or package a candidate as finished while the one-frame
presentation gate fails. Completion of autoplay and PPU agreement alone are
not evidence of original-game parity or smooth movement.

Reported sections:
- T2-X: moving platforms through 14%; invisible 15-21%; upward hold release
  jolts at 40-50%; heavy lag at 56-57% and 93%; offscreen planets at 97-99%.
- T2-EX: moving platforms through 14%; unclear midspins/colors at 19-35%;
  upward hold release jolts at 40-50%; midspins obscured at 54-65%; lag at 93%;
  offscreen planets at 97-99%.

Candidate: `build/packs/t2-stream-test`.
Canonical source assets: `build/neo-audit/t2-assets`.
No T2 candidate has been installed in release folders or ZIPs during this audit.
Installed releases remain the previous T1-transition fix:
ROM `3c840d330ce20b5bd85c758b63a58e81c2611ba1004a6056b8df830cc4bcb6f9`,
MSU `d3fab74941005518ce53b58b785d3c4a901763c2691846d157aef755a90edfc3`.

## Verified baseline

ROM `affd092a73f445ab1e46620734fbaac69d35a243016a1229eb92146a5098babd`,
MSU `7cc0e366579d951ee18ccbd1222e1bd3a452c62087c9b4d2097fdc909f58e70d`.

| Section | Delivered / frames | FPS | Maximum gap |
| --- | --- | --- | --- |
| X opening, steps 1-54 | 975 / 981 | 59.792173 | 2 |
| X middle, steps 210-222 | 208 / 229 | 54.826975 | 5 |
| X late, steps 350-360 | 221 / 236 | 56.518446 | 3 |
| EX late, steps 401-414 | 243 / 254 | 57.723353 | 2 |

All four had zero VBlank overruns. The uninterrupted 67,72,67 replay passed
218/246/218 hardware pixel captures. This is a correctness baseline, not a
performance pass. Evidence: `build/neo-audit/t2-bounded-*/result.json`.

Retained baseline work includes full-frame motion, raster phase reuse for moving
groups of at least eight tiles, native T2 follow timing, compact row packets,
bulk coordinate records, inline 64-byte textures in cartridge RAM, a two-byte
ROM timestamp index, IRAM cache/row kernels, missing-texture lists, dynamic map
DMA budgeting, bounded bulk rows, and CPU work overlapping SA-1 work. Native
MSU transfers already use hardware DMA; do not reimplement this as a new gain.

Prior rejected experiments include dirty prefetch bitsets, unrolled copies,
oldest-slot allocation, larger VBlank budgets, and symbol candidate filtering.
Increasing the upload allowance caused overruns. The symbol filter reduced
candidate counts but did not improve any of the four timing measurements.

## Partial-texture experiment

Inline records retain their original size and full 64-byte texture, replacing
unused deadline hints with the previous raw tag and exact changed span.
Descriptor bit 15 opts into this ABI. The worker accepts a partial span only
when the base equals the acknowledged VRAM tag, the target equals the current
tag, and no tag acknowledgements remain pending. Skipped versions and checkpoint
seeds fall back to full uploads. A resident-shadow comparison was tried and
removed because it did not improve timing.

Adjacent selected spans may share DMA when the gap costs at most the 56-byte
setup allowance. NMI reads STREAM_CHR directly; runs do not cross unselected
slots. The SA-1 queue moved to $416E00, with 128 entries ending before $417600;
assembly assertions protect this boundary. The visible commit retains the
3950-byte weighted allowance after subtracting map work.

The initial hint-only runtime passed full T2-X autoplay and 218 pixel captures
(8,399,856 pixels): ROM
`c8e2d1b2c00ef4328920b5a279d2c18f168acd8e1fb6a6e984e8b0f0648cb019`,
MSU `8f69e923072498706eda94548863f26cc210c42554cfee3df76a9575d8b55768`.
This does not validate later implementations by itself.

Packet pipelining and direct NMI publication did not improve the burst and were
removed. Physical ordering and byte-budgeted fixed-slot batches alone retained
a six-frame worst gap. Similarity-based allocation was disabled again after
regressing presentation. A two-frame prefetch preference also regressed the
middle to a seven-frame gap and was removed. The cache unit test retains its
new dense case changing 70 textures every frame and checks every output pixel.

## Exact viewport culling

The candidate enables exact sampled-cell culling for T2-X/T2-EX. It removes only
cells not sampled by the PPU, preserving sampled pixels and the authored frame
rate. The five viewport tests cover sampling and boundary sharing. Relative to
the earlier canonical assets, it removes 31/24 raw textures and 110/114 lifetime
intervals from X/EX. Alone this is not proof of a frame-rate improvement.

## Fixed-slot budget retry

Telemetry now records delta flags/budget, identity allocator state, pending
VRAM acknowledgements, and native decoder readiness. It showed that much of the
burst switches to the general allocator before reaching the partial-upload
path. Unconditionally keeping identity slots was rejected (149-frame gap).
An approximate 2200-byte admission check was also removed.

The original fixed-slot admission uses M7_UPLOAD_LIMIT (32) before measuring
map DMA. Map transfers can reduce the real budget to 24 while an accepted
atomic set still contains 25-32 textures. Deferring this unchanged overlap can
leave presentation stalled for dozens of frames. This reproduced a 50-frame
pause with exact-culling assets even after the approximate admission experiment
was removed.

At `@transition_defer`, an identity stream now rolls back only uncommitted map
rows, invalidates the IRAM/map preparation state, and retries the same scene
through the general allocator. The general allocator clears identity mode, so
this retry cannot loop indefinitely. It never publishes an incomplete scene.

The retry reduced this reproduced pause from 50 to 6 frames, with no VBlank
overruns. It still fails the user's performance gate: 206/229 frames,
54.299793 FPS. Evidence: `t2-budget-fallback-middle/result.json`.
ROM `8f77fc7532d1489ebdabf3925723011de85df06caf74d9fb171edfbc4e61e545`;
MSU `ac321ce24ffaa5b32f1b52c985aa278d7ce1ddf914d37f34848b3ccd5ea25e14`.

That candidate passed full autoplay and hardware pixel checks:
- T2-X: 218 captures, 8,375,056 pixels.
- T2-EX: 247 captures, 9,791,664 pixels.
- Uninterrupted T2-X, T2-EX, T2-X: 218/247/218 captures, all passed.

These results validate image integrity and cross-level state, not smoothness.

## General allocator batch sizing (in progress)

The general stream path previously limited held transfers to 40 textures even
when adjacent physical destinations share DMA setup. A new prefix budget tracks
the union of physical slots. Adding one costs 64 bytes plus 56 for a new run,
minus 56 for each selected neighboring slot. The ceiling remains 4800 weighted
bytes, the previous worst case for 40 scattered textures, and the queue is
capped at 128 entries. No scene, pixel, or animation update is omitted.

The current candidate below validates this change in MesenCE with no overruns,
including checkpoint and cross-level pixel audits. Its assets restore the
previous future-use allocation policy while retaining exact culling and the
fixed-budget retry. Release folders and ZIPs must remain unchanged until
the presentation gate and correctness checks pass.

## Reproduction

Build canonical assets with `tools/campaign_assets.py --pack master --out
build/neo-audit/t2-assets --levels 67 72 --chart-cache-only --camera-position
--camera-rotation --motion-step 1 --no-pcm`.

`build/neo-audit/build_t2_candidate.py` copies canonical assets, prepares inline
streams, generates MSU data, and builds the SA-1 ROM. For engine-only changes,
`build/neo-audit/compile_engine_fast.py build/packs/t2-stream-test` rebuilds both
CPU and worker code and symbols. Do not mutate a ROM or MSU file during testing.

Use `tools/profile_ar_section_mesen.py` with `--max-hold 1`, the level and step
ranges in the table above, and 1800/5000/8000/8000 frames respectively. It measures
at endFrame and binds results to unchanged ROM/MSU hashes. Failed gates must
remain failures; do not loosen them to label a candidate successful.

Use `tools/run_mesen_campaign.py --pack t2-stream-test --levels 67 72 --autoplay
--graphics-dumps --capture-steps 17 76 154 186 215 216 217 254 356 405 430`, followed
by `tools/verify_mesen_ppu.py` for each level. Include the real-menu no-reset
sequence with `tools/run_mesen_sequence.py --pack t2-stream-test --levels 67 72 67`
and checkpoint tests before release. Captures near 216/217 explicitly cover the
middle disappearance burst. Packet tests cover wrapping, repeated writes,
timestamps, bounded packets, checkpoint seeds, and coordinate batches.

## Current candidate (not ready for release)

ROM `7a8bedef9b48e256d68ee2dc2751d7d42976ac6b1caa0a1d49390f91542ff6bb`;
MSU `2b94cfd0db6745482f44941c3ffc02dfcd6f40340dfb1fb7286fab3d0b87a4c2`.
The weighted run budget now applies to both held uploads and final scene commits.
Updates fitting the conservative count budget skip the extra planning scan.

| Section | Delivered / frames | FPS | Maximum gap |
| --- | --- | --- | --- |
| X opening | 978 / 981 | 59.976149 | 2 |
| X middle | 209 / 229 | 55.090567 | 5 |
| X late | 223 / 236 | 57.029925 | 2 |
| EX late | 243 / 254 | 57.723353 | 2 |

All have zero VBlank overruns. These are modest improvements over the verified
baseline, not a smoothness pass. Evidence: `t2-budget-fast-*/result.json`.
The exact build passed the uninterrupted 67,72,67 sequence and all three hardware
pixel audits: 218/247/217 captures (8,388,788 / 9,795,748 / 8,368,776 pixels).
All 36 stream, pattern cache, viewport, Mode 1, camera and raster-phase unit
tests passed. Checkpoint replay also passed: X 4/4 retries and EX 3/3 retries, with
238/268 PPU captures (9,108,568 / 10,572,736 pixels), bound to the same ROM/MSU.
No build or ZIP was installed because the performance gate still fails.

A function timing trace is saved in
`build/neo-audit/t2-budget-function-timing/functions.csv`. These are successive
entry timestamps, not exclusive function timings: intervals ending at tag
commit include VBlank waits. Decoder/catchup work and held uploads remain major
contributors. Do not describe a whole interval as CPU execution time without
subtracting waits and nested calls.

## Remaining investigation

The function-entry trace includes catchup decoder intervals up to about 13 ms
followed by another decoder job at the same chart time. Current indexed stream
alternatives coalesce 2, 4, or 8 packets. A five-packet catchup can therefore
process a four-packet alternative and another packet, potentially decoding
textures overwritten by the last packet. This is a hypothesis for the next
optimization, not an implemented fix. Any new format must retain every normal
frame, preserve exact final state, remain compatible with checkpoint snapshots,
and verify descriptor offsets and cursor advancement. Do not reduce published
updates or quality to hide the remaining five-frame pause.

## Recorded timing experiments

Measurements are not acceptance labels; the one-frame gate remains unchanged.

| Evidence | Level | Steps | FPS | Gap | Overruns |
| --- | --- | --- | --- | --- | --- |
| `t2-batched-ex-late` | 72 | [401, 414] | 57.485809 | 2 | 0 |
| `t2-batched-late` | 67 | [350, 360] | 56.774186 | 2 | 0 |
| `t2-batched-middle` | 67 | [210, 222] | 55.090567 | 5 | 0 |
| `t2-batched-opening` | 67 | [1, 54] | 59.546872 | 2 | 0 |
| `t2-before-opening` | 67 | [1, 54] | 53.107715 | 4 | 0 |
| `t2-bitset-middle` | 67 | [210, 222] | 54.826975 | 5 | 0 |
| `t2-bounded-ex-late` | 72 | [401, 414] | 57.723353 | 2 | 0 |
| `t2-bounded-late` | 67 | [350, 360] | 56.518446 | 3 | 0 |
| `t2-bounded-middle` | 67 | [210, 222] | 54.826975 | 5 | 0 |
| `t2-bounded-opening` | 67 | [1, 54] | 59.792173 | 2 | 0 |
| `t2-budget-fallback-ex-late` | 72 | [401, 414] | 56.298085 | 2 | 0 |
| `t2-budget-fallback-late` | 67 | [350, 360] | 55.495488 | 2 | 0 |
| `t2-budget-fallback-middle` | 67 | [210, 222] | 54.299793 | 6 | 0 |
| `t2-budget-fallback-opening` | 67 | [1, 54] | 59.976149 | 2 | 0 |
| `t2-budget-fast-ex-late` | 72 | [401, 414] | 57.723353 | 2 | 0 |
| `t2-budget-fast-late` | 67 | [350, 360] | 57.029925 | 2 | 0 |
| `t2-budget-fast-middle` | 67 | [210, 222] | 55.090567 | 5 | 0 |
| `t2-budget-fast-opening` | 67 | [1, 54] | 59.976149 | 2 | 0 |
| `t2-budget-late` | 67 | [350, 360] | 55.495488 | 3 | 0 |
| `t2-budget-middle` | 67 | [210, 222] | 55.354158 | 5 | 2 |
| `t2-budget-opening` | 67 | [1, 54] | 56.480607 | 2 | 0 |
| `t2-bulkguard-opening` | 67 | [1, 54] | 59.485547 | 2 | 0 |
| `t2-bulkrow-opening` | 67 | [1, 54] | 34.902247 | 524 | 0 |
| `t2-cache-opening` | 67 | [1, 54] | 59.362896 | 2 | 0 |
| `t2-clear-late` | 67 | [350, 360] | 56.262706 | 3 | 0 |
| `t2-clear-opening` | 67 | [1, 54] | 59.730848 | 2 | 0 |
| `t2-commit-batch-late` | 67 | [350, 360] | 56.774186 | 2 | 0 |
| `t2-commit-batch-middle` | 67 | [210, 222] | 55.090567 | 5 | 0 |
| `t2-coord-late` | 67 | [350, 360] | 56.262706 | 3 | 0 |
| `t2-coord-opening` | 67 | [1, 54] | 59.730848 | 2 | 0 |
| `t2-delta-atomic-middle` | 67 | [210, 222] | 55.090567 | 6 | 0 |
| `t2-delta-fast-middle` | 67 | [210, 222] | 55.090567 | 6 | 0 |
| `t2-delta-fixed-middle` | 67 | [210, 222] | 20.823707 | 149 | 0 |
| `t2-delta-held-middle` | 67 | [210, 222] | 55.090567 | 6 | 0 |
| `t2-delta-merged-middle` | 67 | [210, 222] | 54.036202 | 6 | 0 |
| `t2-delta-middle` | 67 | [210, 222] | 54.826975 | 5 | 0 |
| `t2-delta-ordered-middle` | 67 | [210, 222] | 55.090567 | 6 | 0 |
| `t2-delta-placed-middle` | 67 | [210, 222] | 55.090567 | 6 | 0 |
| `t2-delta-shadow-middle` | 67 | [210, 222] | 54.563384 | 6 | 0 |
| `t2-delta-state-middle` | 67 | [210, 222] | 55.090567 | 6 | 0 |
| `t2-direct-opening` | 67 | [1, 54] | 57.952414 | 2 | 0 |
| `t2-directrow-opening` | 67 | [1, 54] | 59.485547 | 2 | 0 |
| `t2-dirtyprefetch-late` | 67 | [350, 360] | 56.262706 | 3 | 0 |
| `t2-dirtyprefetch-middle` | 67 | [210, 222] | 53.772611 | 7 | 0 |
| `t2-dirtyprefetch-opening` | 67 | [1, 54] | 56.971209 | 3 | 0 |
| `t2-fixed-clear-opening` | 67 | [1, 54] | 55.749142 | 2 | 0 |
| `t2-general-batch-middle` | 67 | [210, 222] | 54.826975 | 6 | 0 |
| `t2-guard-late` | 67 | [350, 360] | 57.285665 | 3 | 0 |
| `t2-guard-middle` | 67 | [210, 222] | 52.191063 | 12 | 0 |
| `t2-guard-opening` | 67 | [1, 54] | 57.032535 | 3 | 0 |
| `t2-hotcompare-ex-opening` | 72 | [1, 61] | 59.040723 | 2 | 0 |
| `t2-hotcompare-late` | 67 | [350, 360] | 56.262706 | 3 | 0 |
| `t2-hotcompare-opening` | 67 | [1, 54] | 59.730848 | 2 | 0 |
| `t2-hotfixed-late` | 67 | [350, 360] | 56.262706 | 3 | 0 |
| `t2-hotfixed-opening` | 67 | [1, 54] | 59.669523 | 2 | 0 |
| `t2-hudoverlap-late` | 67 | [350, 360] | 56.518446 | 3 | 0 |
| `t2-hudoverlap-opening` | 67 | [1, 54] | 59.730848 | 2 | 0 |
| `t2-inline-hud-opening` | 67 | [1, 54] | 54.702173 | 3 | 0 |
| `t2-inline-opening` | 67 | [1, 54] | 54.579522 | 3 | 0 |
| `t2-iram-opening` | 67 | [1, 54] | 59.362896 | 2 | 0 |
| `t2-large-transfer-late` | 67 | [350, 360] | 50.380696 | 8 | 0 |
| `t2-large-transfer-opening` | 67 | [1, 54] | 55.749142 | 2 | 0 |
| `t2-lazy-opening` | 67 | [1, 54] | 56.971209 | 2 | 0 |
| `t2-masks-opening` | 67 | [1, 54] | 59.240246 | 2 | 0 |
| `t2-nmi-handoff-middle` | 67 | [210, 222] | 54.563384 | 6 | 0 |
| `t2-oldest-middle` | 67 | [210, 222] | 54.299793 | 7 | 0 |
| `t2-overlap-opening` | 67 | [1, 54] | 59.730848 | 2 | 0 |
| `t2-parallel-late` | 67 | [350, 360] | 56.262706 | 3 | 0 |
| `t2-parallel-opening` | 67 | [1, 54] | 56.971209 | 2 | 0 |
| `t2-phase-late` | 67 | [350, 360] | 52.682352 | 3 | 0 |
| `t2-phase-opening` | 67 | [1, 54] | 55.687879 | 2 | 0 |
| `t2-pipeline-middle` | 67 | [210, 222] | 54.299793 | 6 | 0 |
| `t2-poll-late` | 67 | [350, 360] | 56.518446 | 3 | 0 |
| `t2-poll-opening` | 67 | [1, 54] | 59.485547 | 2 | 0 |
| `t2-precise-ex-late` | 72 | [401, 414] | 58.198443 | 2 | 0 |
| `t2-precise-late` | 67 | [350, 360] | 56.774186 | 2 | 0 |
| `t2-precise-middle` | 67 | [210, 222] | 33.476086 | 50 | 0 |
| `t2-precise-opening` | 67 | [1, 54] | 59.976149 | 2 | 0 |
| `t2-precise-safe-middle` | 67 | [210, 222] | 33.476086 | 50 | 0 |
| `t2-prefetch-gap-middle` | 67 | [210, 222] | 54.299793 | 7 | 0 |
| `t2-rowcopy-opening` | 67 | [1, 54] | 58.626993 | 2 | 0 |
| `t2-rowdma-opening` | 67 | [1, 54] | 58.933619 | 2 | 0 |
| `t2-rows-late` | 67 | [350, 360] | 56.262706 | 3 | 0 |
| `t2-rows-opening` | 67 | [1, 54] | 58.13639 | 2 | 0 |
| `t2-scan-opening` | 67 | [1, 54] | 56.909884 | 2 | 0 |
| `t2-scene-opening` | 67 | [1, 54] | 55.504091 | 2 | 0 |
| `t2-shortqueue-opening` | 67 | [1, 54] | 59.608198 | 2 | 0 |
| `t2-symbols-ex-late` | 72 | [401, 414] | 57.723353 | 2 | 0 |
| `t2-symbols-late` | 67 | [350, 360] | 56.518446 | 3 | 0 |
| `t2-symbols-middle` | 67 | [210, 222] | 54.826975 | 5 | 0 |
| `t2-symbols-opening` | 67 | [1, 54] | 59.792173 | 2 | 0 |
| `t2-wordcopy-middle` | 67 | [210, 222] | 54.826975 | 5 | 0 |


## Lossless OBJ offload experiments (November 12, continued)

A restorable pre-experiment candidate is in
`build/neo-audit/t2-five-frame-baseline/` (ROM, MSU, labels and metadata).
The 2/3/5-packet catchup descriptors preserve exact final state and checkpoint
seed tags; their focused test passes. Alone they produce 210/229 presentations,
55.354158 FPS and a five-frame maximum gap, with no VBlank overrun.

The initial 80-cell OBJ offload prototype is rejected: 130/229 presentations,
34.266860 FPS, three-frame maximum gap, and a stale BG texture caught by the
hardware pixel verifier. It must not be shipped. The compiler initially
published tag-only changes for masked textures without updating their BG pixel
storage; removing those tag writes fixes that stale cache identity.

The corrected 16-cell experiment passes all 218 T2-X PPU captures (8,378,328
pixels), but delivers only 207/229 frames, 54.563384 FPS, maximum gap five.
It is also rejected as a performance improvement. Evidence:
`build/neo-audit/t2-spill16-middle/result.json`; ROM
`ede0a6e2c1f9ed6cb479f3b6e9d9450ad24a8d0115c6575a3f0700bcea26d8fe`, MSU
`c3ac607da405882bcc8b6d1176cca6f0efb0ae221eec58972f1450e752f90fcb`.

The next experimental revision caches OBJ glyph images by compiler-assigned
identity, separately tracking the RAM image and the NMI-acknowledged VRAM image.
Every packet remains a complete snapshot for checkpoints; unchanged glyphs
avoid RAM copying and VRAM transfer. This revision has NOT yet passed emulator
validation. No installed folder or ZIP has changed.


Further OBJ prototype measurements (still not a release):
- Cached glyph images: 173/230, 45.402150 FPS, max gap 3; 202 PPU captures
  pass (7,797,308 pixels).
- SA-1 DMA bridge for glyph copies: 174/230, 45.664590 FPS, max gap 3.
- Coalesced map writes, contiguous spill transfer, aggregate sprite budgets:
  203/229, 53.509019 FPS, max gap 3; 213 PPU captures pass (8,198,740 pixels).
  ROM 6a021c42a64aabb969625903a37f5b8f7f024d348eb16dcdd3e4e55622312282,
  MSU 47f2d39f41f25bd72d0a32bde8b6b01bfc666a1152d7ccbbcc7e1d24d333f5d1.
- Precomputed OAM positions with actual-camera equality guard and dynamic
  fallback: 216/229, 56.935705 FPS, max gap 3, no VBlank overruns. The object
  verifier initially assumed the old SPILL_FRAME staging ABI. It now derives
  streamed expected objects from world-cell inputs and the actual raster
  camera, independently of the prepacked output. This revision must be
  replayed under that updated contract before claiming visual correctness.

The current build also moves BG repair uploads earlier when both the last
BG use and last source write permit it, preserving complete frame images.
This is experimental, not yet validated. The OBJ path currently remains
activated for levels 67/72 by tools/sa1_stream.py; do not publish or package
from it until the one-frame timing gate and full correctness suite pass.


The early-repair/prepacked candidate reduces the measured middle section to
218/229 presentations, 57.462888 FPS, maximum gap 2, and zero VBlank overruns.
All 218 T2-X hardware captures pass (8,412,556 pixels) under the world-input
sprite contract. ROM 29aa700a6ce8104afdea48ac9b557fce1c491ace82f719e2245a9a11ed90a340,
MSU f9591cfc4c952da1c0a4c687c8ef70b1d4335eb23d52eab0e0542044baac86fa.
Backup: `build/neo-audit/t2-two-frame-candidate/`. It still fails the release gate.

Next candidate uses a 40-frame source-write lookahead to move currently visible
old tiles into exact-color OBJ before their BG slots need replacement. Both
ordinary source texture writes and repairs move earlier only after the last
visible BG use and the last preceding texture write. A randomized 60-frame
pixel-composition test with constrained four-object capacity passes, along
with the checkpoint/palette/rotation and prepacked-OAM tests. Emulator results
for this new lookahead candidate are still pending. Release folders and ZIPs
remain unchanged.


The broad 40-frame source-write lookahead is REJECTED and disabled in
prepare_spills: it regresses to 191/229, 50.345925 FPS (max gap 2), and hardware
pixel verification fails near the start of both X and EX. The randomized
in-view test was insufficient: an early logical texture replacement can still
be visible outside the compiler's predicted viewport. Do not enable lookahead
without addressing that lifetime constraint. Candidate hashes:
ROM f0ae31bea036116cbdf64021cbd3de5b5ee694db5f559012f9389e5a596bcfe6,
MSU 7caca68bfa613a6341dd883f8f617863b0f595e6bae9e6b06c4db54e1ddf21a2.

The in-progress build returns to the verified early-repair/prepacked variant
and adds bulk contiguous alpha updates (existing kind-19 ABI) to the stream
compiler and SA-1 decoder. Scalar alpha values/timestamps are unchanged; unit
coverage now compares opacity as well as X/Y batches. Performance and full
hardware validation are pending. No release folders or ZIPs were updated.


Latest measured prototype (alpha-batched data plus the unrolled 16-bit inline
texture copy): ROM 77bc81a656d16ed0bf593b99f9038d7e7a98d2508b346ed347bef526910464ee,
MSU 7dc89a52186d8cbae2ad620c35321b597c5f4a5f57e823b1cd111ef5e6a85218.
- Middle: 219/229, 57.726479 FPS, max gap 2.
- Opening: 952/981, 58.381691 FPS, max gap 2 (REGRESSION versus baseline).
- Late X: 223/236, 57.029925 FPS, max gap 2.
- Late EX: 243/254, 57.723353 FPS, max gap 2.
All four have zero VBlank overruns; none passes the one-frame gate.
A trial 4350-byte weighted OBJ-frame allowance regressed the maximum gap to 3
and was reverted to 3950. The scalar-to-bulk alpha change alone did not improve
performance; batch_coordinates now leaves alpha batching disabled by default
(the optional unit-tested implementation remains available).

The OBJ compiler is now explicitly gated by level metadata
`stream_spill_trial`; ordinary builds do not enable this unfinished renderer.
`build/neo-audit/build_t2_candidate.py` opts the test pack into it. The current
on-disk candidate still contains the prior alpha-batched stream data; rebuilding
with that script will use the now-disabled default for alpha batches. Three
full regression jobs (autoplay X/EX, checkpoints X/EX, sequence X/EX/X) are
currently being run against the exact hashes above. Do not mutate their ROM
or MSU until they complete. Release folders/ZIPs have not changed.


Final observed correctness results for ROM 77bc81a656d16ed0bf593b99f9038d7e7a98d2508b346ed347bef526910464ee
and MSU 7dc89a52186d8cbae2ad620c35321b597c5f4a5f57e823b1cd111ef5e6a85218:
- Full autoplay: X 218 PPU captures / 8,383,056 pixels; EX 245 / 9,770,968.
- Checkpoints: X 4/4 retries, 242 captures / 9,258,440 pixels;
  EX 3/3 retries, 266 / 10,478,952.
- Uninterrupted 67 -> 72 -> 67: PASS, 217 / 246 / 217 captures and
  8,388,372 / 9,730,328 / 8,357,880 checked pixels.
All passed with no VBlank overruns. Total 1,651 PPU captures, 64,367,996
compared pixels. This does NOT override the failed one-frame performance gate
or the opening performance regression. No release installation/ZIP changes.

The private candidate builder now explicitly sets both stream_spill_trial and
stream_bulk_alpha_trial so its intended combination matches the last measured
candidate. Ordinary stream compilation defaults both experimental paths off.
The source retains the tested unrolled inline texture copy, exact 2/3/5 catchup
alternatives, and prior verified baseline optimizations. All test processes
from this audit have completed; no background build or emulator job is pending.


## Direct transport experiments (2026-11-12, continued)

Experimental packets now support direct final-RAM routes and batched inline
textures. This preserves all texture bytes and event timestamps. The default
release compiler still does not enable these trial flags.

- Bulk direct transport: ROM `4269ccab1cb5d79068d1991650749550d94cf1a5dcb8f99916bbd559b61ef7ce`,
  MSU `ed2db850d1cb0ea0a0431b20bb59dc59bf86209daa16902f193c6e930b63f7af`.
  Opening 944/981 transitions (57.832077 FPS), middle 223/228
  (58.780844 FPS), both maximum gap/display age 2 and zero VBlank overruns.
  These fail the one-frame gate; the opening is worse than the original baseline.
- SA-1 metadata DMA bridge: ROM
  `5b33d446226c72cb0034b1bfe6fe059b69a8c7aa0fd6d1d0fe7fdf0cf321d66c`,
  same MSU. Identical presentation counts. Full T2-X autoplay completed;
  217 PPU samples / 8,352,064 visible pixels passed. Function tracing showed
  the packet copy falling from ~0.404 ms to ~0.233 ms but fixed cache setup
  increasing from ~0.671 ms to ~0.909 ms because the bridge invalidated IRAM.
  The bridge was reverted; retain neither the slower opening as a release nor
  a claim that this DMA substitution removed the pause.

Next candidate routes packed OBJ bytes directly to their final OAM buffer,
while retaining the raster-origin guard and dynamic coordinate fallback. It
also uses CPU DMA for the small immutable SA-1 trail OAM result. These changes
require fresh emulator validation. Packet tests now include exact position
routing and preservation of the camera guard/line budgets (15 tests pass).
Release folders and ZIPs remain unchanged until the actual one-frame gate passes.


### Continued audit: corrected bulk-row admission

Threshold 48 avoids unnecessary OBJ offload in the opening, restoring its
978/980 transitions (59.976149 FPS). The larger 8192-byte CPU scratch batch
improved the middle to 224/228 transitions (59.044435 FPS). Neither passes
the one-frame gate; EX ending remains 243/253 (57.723353 FPS), gap 2.

The new threshold exposed a real map corruption at T2-X chart time 2336,
step 122, world cell (66,95). Instrumented SA-1 callbacks showed the first
bulk-row pass staging tile 159, followed by a versioned retry that failed
to restore it. Bulk admission accounted for atomic CHR and map DMA but not
the simultaneously uploaded OBJ CHR/palette. The later exact budget rejected
that scene after bulk copying had bypassed row undo capture. Adding the same
OBJ cost to bulk admission fixes the missed row upload. This preserves full
tile detail; no visibility or update-frequency changes were used.

Verified corrected candidate:
- ROM c1848e16483530e0160c3c4fc6af7f97af48632e13bcf767ed1435193f2d253f
- MSU 9c3afc03bcb8a1ee55b7bb1b1cd73d8185eab031933065512a016c2f3524977b
- Full X: 223 PPU captures, 8,567,320 visible pixels.
- Full EX: 259 PPU captures, 10,252,268 visible pixels.
- Both full-song autoplay runs passed the sprite/trail/hold checks and had
  zero VBlank overruns. Explicit chart-time captures cover 2329 through 2340.
- Backed up ROM/MSU/labels/metadata in t2-corrected-bulk-candidate.

Other retained changes: direct packed-OAM routing with explicit route detection
for older packets; trail OAM DMA; private direct-page trail counters; meter-only
HUD redraw when counters/feedback are unchanged. The latter two passed measured
performance without improvement to the remaining gap. The all-IRAM trail job
was reverted because overlay reload cost regressed the opening. The speculative
+320 visible-DMA allowance was reverted because it provided no improvement.
Transport routing fields were moved from 43EF60 (inside Mode 1 dirty blocks)
to 42BC70..42BC78; layout verification now checks the reservation.

The earlier attempt to call bank-81 helpers without reserving/mirroring those
physical ROM bytes was reverted. Only bank 80 was mirrored in the existing
layout. A new opt-in fastrom_helpers_trial now reserves the additional ROM
range before asset placement and mirrors/link-addresses camera/Neo helper
banks together. That candidate is being built; it is not release-approved.
No installed folders or ZIPs have been changed.


### Continued audit: exact OBJ deltas and measured sparse row admission

The reserved helper mirror passed the layout checker (299 blobs) and full
X/EX graphics checks. Sprite delta hints (kind 35, format 9) now specify an
aligned byte span and its required NMI-acknowledged image ID. Unknown or
mismatched bases use the full original image, including catch-up/checkpoints.
Three spill tests and fifteen stream tests passed. This did not change the
remaining presentation gaps; it is not evidence of smoothness.

Measured sparse admission probes the same dirty/exposed row spans without
mutating staged bytes, includes OBJ palette/CHR and atomic CHR costs, and
only uses bulk copies below the unchanged 3950-byte-equivalent budget.
The short identity-row MVN experiment regressed the middle and was removed.
The two-byte map-row decoder threshold was retained (EX 246/253 vs 245/253).

Candidate ee2a2047c019c696ada705cc1c7d8c8341634748b5b12f885d4216d2ab546455,
MSU 5ca74a00b8944a1fe1e35545cd9da4f2948eca7a35f17dd14b557bbd8faadb88:
- Middle 224/228 transitions, max gap 2; EX ending 247/253, max gap 2.
- Zero VBlank overruns, full X/EX autoplay completed.
- Full X 220 PPU captures / 8,483,524 pixels; EX 251 / 9,999,700 pixels.
- Still fails the one-frame gate. No folders/ZIPs updated.

Next opt-in candidate batches consecutive non-wrapping map-row records
(kind 36, stream format 10) to reduce repeated header dispatch on SA-1.
The cell IDs, row coordinates, values and write order remain intact.
A new semantic round-trip test brings the stream suite to 16 passing tests.
The candidate is being built and has not yet passed emulator verification.


### Continued audit: idle-time reads and stable OBJ slots

The batched row decoder passed full X/EX runs. A guarded idle-time packet
prefetch reads only before scanline 170, while frame_ready is still zero.
It caches the exact MSU offset/length, invalidates at every seed, and falls
back on a different catch-up choice. Full 2 KiB prefetch improved EX ending
to 249/253 transitions, gap 2. Increasing the prefix to 6 KiB regressed it
to 246/253, so the cap was restored to 2 KiB. No VBlank overruns occurred.

The middle timing trace shows held texture uploads inside cache preparation,
not merely a CPU deadline miss. Stable palette/glyph slot assignment preserves
exact pixels and avoids unnecessary reindexing. Its candidate passed full
X/EX graphics comparison (224 / 252 samples; 8,587,460 / 9,981,584 pixels),
but middle remains 225/228 and EX ending 248/253, gap 2. Hashes:
ROM 4f3e04d6b09514d07a8c3f43a4a1befecc1c45a9ab5956845540534fd4d6b92b
MSU d07a8ff25617cd714c0027568f2e9e5a8928dd11f05ba25ab4a5e6fc97c3088f

The next candidate removes redundant writes for cells that remain OBJ-masked.
A new one-shot seed flag reconstructs the complete mask from the first OBJ
snapshot after load/checkpoint, allowing ordinary frames to emit only entering
and leaving mask cells. Nine pixel/palette/delta/checkpoint unit tests pass
across legacy, stable, and incremental configurations. Emulator verification
of this incremental candidate is still pending. Releases remain untouched.


### Wrap-up candidate (not release-approved)

Incremental-mask candidate c722c2edc300edfef285beb63694ef7cfaa81679a98972dbbd9fc04fad9a07fe
with MSU 69010217a939e7f7b1c469d0743899192ff2104eee0e638ba33fb2df1d137288
passed full X/EX autoplay and all checkpoint retries (4/4 and 3/3).
PPU comparisons: autoplay X 224 samples / 8,598,760 pixels, EX 252 / 9,958,564;
checkpoints X 247 / 9,457,428 and EX 268 / 10,626,636. Zero VBlank overruns.
Middle 225/228, ending 249/253; both still max gap 2, FAIL one-frame gate.
Sixteen stream tests and nine spill tests pass. Layout: 299 blobs, no crossing.
Measured the first held middle upload at cost 544 vs remaining budget 453.
A +128 allowance did not fix the stalls and regressed EX by a frame. Reverted
both admission and final budgets to 3950; rebuilt byte-identical c722 candidate.
Release folders, ZIPs and GitHub have not been updated. No-reset sequence
67 -> 72 -> 67 is running as the final wrap-up check.


### User-approved interim release

The user explicitly accepted a two-frame gap for now. The one-frame goal
remains unachieved; this is an interim release under the revised criterion.
The restored c722 candidate passed the no-reset 67 -> 72 -> 67 sequence:
223/248/223 PPU samples, all actual hardware pixels and sprite checks passed.
The same candidate passed full 1-X, AR-X, T1-X and T1-EX regressions.
Compressed middle: 224/227 transitions, max gap 2, max chart-clock age 3;
compressed EX ending: 249/253, max gap/age 2. Zero VBlank overruns.
The compressed middle's stricter age assertion failed; that distinction is
explicit in the installer/release notes, not misreported as a full gate pass.
All three master editions use identical updated ROM/MSU files. PCM files
are unchanged. Standalone cartridges use a separate backend and are unchanged.
Installer validates ROM/data hashes, full-song sequence, checkpoint and
regression pixel evidence, then replaces installed files and existing master
ZIP contents. Changed ZIP members are SHA256 checked and all archive members
are CRC tested. See build/neo-audit/t2-installed-release.json on completion.

### Follow-up: cubicle visibility, lane art, and EX 86%

The released c722 master reproduces an untested EX 86% stall (steps 370-382):
197 measured frames, 117 transitions, maximum gap 36, display age 35,
zero VBlank overruns. Evidence: build/neo-audit/t2-ex-86-before/result.json.
Earlier two-frame results did not cover this section.

The user confirmed T2-X's cubicle must retain the whole figure-eight route.
Pending changes restore the ordinary figure-eight tiles at the cubicle entrance.
The user's correction explicitly excludes midspins: red/blue alternate routes
must retain native visibility, not be revealed together. Two alpha intensities
preserve faint notefield boards and bright tick marks; wide-angle joins regain
sharp corners toward diagonal midspins.

The projected OBJ experiment failed sprite checks and was removed. The accepted
optimization candidate instead suppresses raster-phase changes driven by hidden
or offscreen groups. EX 86% measured a one-frame gap in the 1bea candidate.

Graphics verification caught two real rollback bugs: the packet arena is reused
for row undo before its fast OBJ metadata is consumed, and short scalar map rows
were mutated without saving their old values. OBJ snapshots now live at $42BA00;
short rows preserve their old bytes with a bounded copy before mutation. Full
X/EX hardware-pixel checks passed on 1bea (219/250 captures, ~18M pixels).
The X middle interval still reached three frames; an early admission check is
being tested to avoid first staging and then rolling back an identity scene
that cannot fit its VBlank budget. Release installation remains gated on final
hash-bound replays, pixel checks, and the accepted two-frame performance limit.

The early-admission experiment and a reduced sprite count did not improve the
middle gap and were reverted. Retained optimizations include skipping unchanged
OBJ palette uploads and a 4100-unit upload admission budget, checked against
actual MesenCE VBlank completion. No emitted geometry/detail was removed.
Checkpoint pixel verification then caught a speculative preload that canonical
checkpoint bootstrap discarded. Repairs crossing the origin-32..origin bootstrap
window now upload when needed; the final T2-X checkpoint replay passes (245
captures, 9,385,240 actual hardware pixels). Regression coverage includes a
sprite-to-background transition spanning a checkpoint.

Final candidate: ROM 17bd6f978668f6909ff215d849879ebf45f2cbfff45613993d02dc117737e4fc,
MSU da96c8b2b1a2ef7f2b6db1673c0f66c4c667fb39732d38d88ed36560c18f939f.
Final full replays, performance gates, and release packaging are in progress;
see t2-installed-release.json for the completed installation evidence.

### Follow-up installation complete (2026-11-13)

All release gates passed on the final hashes. All three master folders and the
compressed, hybrid and PCM tester-update ZIPs are replaced and verified. Each
ZIP passed full CRC checks, and replaced members match installed SHA256 hashes.
All seven timing profiles passed with zero VBlank overruns. Full T2 autoplay,
every checkpoint, three no-reset sequence stages, and 1-X/AR-X/T1-X/T1-EX hardware
pixel checks passed. See build/neo-audit/t2-installed-release.json for evidence.


## 2026-11-13: T2 exclusive routes and junctions

T2-X now previews the figure-eight on approach (beat 28), with only the
active hot/cold pair; the five CubicleTransition times switch the preview.
Native on-hit marker flashes no longer expose the previous route.
T2-EX keeps native marker timing. Active midspins expose a merged incoming/
outgoing connector junction; inactive overlapping surfaces cannot occlude it.
Removed both T2 scene overlays (scrolling background and EX gray notefields).
Full authored zoom was tested and rejected after sprite/performance failures;
this release retains the existing camera sampling. Mesen approach capture at
chart frame 1313 shows the complete route before entry without that experiment.

Recreated deleted build/packs from surviving frozen assets. All 144 non-T2
BRR and animation payloads match the previously installed MSU byte-for-byte.
Rebuilt T1 Mode 1 streams: tested opening/end/freeze ranges still max gap 1.

Current ROM: 3be260f3aac8ace03ff776aef87dca9398964356f2ced794e4134b15a4e7bbda
Current MSU: a8ed5bb6bab2a5accc53b588bece4e9d0f83f9ea230529bc22950b7f96af475e
Full T2 autoplay/checkpoint PPU checks and X -> EX -> X sequence passed.
1-X/AR-X/T1-X/T1-EX regressions and all 299 ROM-blob layout checks passed.
Opening/middle max gap 2; EX86/end max gap 1; zero VBlank overruns.
Compressed middle display age max 3 (distinct from presentation gap).
1,772 consecutive cubicle frames pass exclusive route/connector visibility.
All five scene tests plus readability and stream unit tests pass.
Evidence: build/neo-audit/t2-route-*.log, t2-route-visibility-check.json,
restored-master-asset-audit.json, t2-approach-check/approach-1313.png.
All three installed master folders and ZIPs updated; contained ROM/MSU
SHA256 and full archive CRC checks passed. See t2-route-install.log and
build/neo-audit/t2-installed-release.json. Standalone backend unchanged.

---


## 2026-11-13: T2-EX note display restored below gameplay

The EX chart intentionally hides late cubicle midspins and supplies their
cues in SingSing_Notefield. Removing the opaque overlays removed essential
information. Restored that EX-only display 28 screen pixels lower, using
thinner, dim, rounded backboards and separated crowded note glyphs. X's
scrolling background remains disabled. Native cue times/colors and row
transitions are retained; audio is unchanged.

All 23 original cue deadlines match imported floors; each marker is visible
before its deadline. Six scene tests pass, including last-group visibility,
position below gameplay, and spacing between close markers. 150 unchanged
music/animation/stream payloads match the prior installed MSU, including
T2-EX audio. At steps 130-179 (including reported 37%), 514 sampled frames,
511 visible transitions, max gap 2, display age 2, zero VBlank overruns.

ROM: 66fa6675c1a8c486af72a4d260c217f1ae2c181d1ea0011fc5d2a3f37b0a836e
MSU: 8dd1b6d032406c3156bab8717e7eae15ef962d382930693ed2cc3483968d5c68
Evidence: build/neo-audit/t2-cue-coverage.json, t2-cue-performance/result.json,
t2-cue-unchanged-payloads.json; screenshot in the master verification folder:
mesen-72-autoplay/step-162-frame-2870.png.
Full-song/checkpoint PPU tests, X -> EX -> X sequence, 1-X/AR-X/T1-X/T1-EX
regressions and layout checks passed. All three installed master folders and
ZIPs updated; SHA256 and full archive CRC checks passed. See t2-cue-install.log.

---
