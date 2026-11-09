# Rendering performance and verification

The November 9 update removes the long presentation stalls in Feral [Hard],
Celica (Remastered Ver.), and Heaven's Gateway. All 65 master charts pass the
full-song graphics and presentation-progress checks, with no VBlank overruns.
The three affected standalone cartridges also pass.

This does not guarantee 60 FPS. MesenCE measurements of the affected sections:

| Chart | Steps | Maximum display hold | Delivered FPS |
| --- | --- | ---: | ---: |
| Feral [Hard] | 1380–1508 | 18 frames | 15.36 |
| Celica | 480–620 | 9 frames | 16.03 |
| Heaven's Gateway | 1800–2029 | 41 frames | 15.29 |

Heaven's Gateway still has a noticeable short pause. These measurements count
published track scenes, not emulator refreshes; audio and input can continue
while a track scene waits for a safe upload. Further rendering optimization is
needed for smooth 60 FPS in these sections. Increasing upload limits beyond the
VBlank budget caused corruption in testing and is not included in the release.

The earlier PA-X fix remains: its steps 300–424 measured 47.88 delivered FPS,
with a maximum hold of 32 frames in MesenCE at 1.0x.

`tools/verify_render.py` rejects a displayed scene more than 120 song-clock
frames behind playback. This conservative hang check is separate from frame-rate
measurement. `tools/profile_ar_section_mesen.py --max-hold N` also bounds holds
that continue through the end of the measurement window and checks VBlank safety.

This update changes master chart data. Replace both `adofai.sfc` and `adofai.msu`;
existing PCM files can be retained. Music bytes are unchanged.
