# Known rendering issues

The November 9 PA-X update fixes the presentation freeze near 75% at 1.0x.
It does not guarantee 60 FPS: MesenCE measured 47.88 delivered FPS over steps
300-424, with a longest hold of 32 frames. The manual replay completed all
407 scored hits; 250 PPU samples matched 9.37 million visible pixels.

The new presentation-progress check found remaining stalls at 1.0x:

| Chart | Approximate section in this build |
| --- | --- |
| FT04-X Feral [Hard] | 95% |
| FT19-X Celica (Remastered Ver.) | 50% |
| FT21-X Heaven's Gateway | 95% |

The preceding release also fails the progress check for all three charts
(Heaven's Gateway fails earlier, around 33%). These remain unresolved.
A completed autoplay run and correct pixels in its last published scene
alone do not prove that its display kept advancing.

`tools/verify_render.py` now rejects a displayed scene more than 120 song-clock
frames behind playback. This conservative hang check is separate from frame-rate
measurement. `tools/profile_ar_section_mesen.py --max-hold N` also bounds holds
that continue through the end of the measurement window and checks VBlank safety.
