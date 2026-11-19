---
name: pixel-art
description: Make game-ready pixel art sprites with the pixel-forge MCP tools. Use whenever the user asks for sprites, characters, items, tiles or animations for the Godot game.
---

# Pixel art with pixel-forge

You cannot see pixels you have not rendered. **Never trust your mental picture: call `preview`
and look at the image after every 2-3 edits**, then fix what you see.

## Before you start
1. Read `STYLE_GUIDE.md` in the project root (palette, sprite size, light direction, outline rule).
   If it does not exist, copy `STYLE_GUIDE.template.md` and ask the user to confirm the choices.
2. Use the palette named in the style guide: `new_sprite(..., preset="db16")`. The palette is locked,
   so off-palette colors are rejected. Refer to colors by index (`p6`) to avoid typos.

## The loop (one sprite)
1. **Silhouette first.** One flat color, no detail. `draw_ellipse` / `draw_polygon` / `draw_ascii`.
   `preview`. A sprite that does not read as a silhouette will not be saved by detail. Fix shape now.
2. **Flat regions.** Fill body, clothes, hair, skin as separate flat colors. `preview`.
3. **Shade.** `shade(base, highlight, shadow, light="top_left", depth=1)` once per region.
   Always the same light direction as the style guide. Use `depth=2` only on big shapes (> 20px).
4. **Details.** Eyes, mouth, buckles via `draw_ascii` or `draw_pixels`. Keep them few and readable at game size.
5. **Outline.** `outline` with a dark palette color (never pure black unless the guide says so).
   Keep a 1px empty margin on the canvas.
6. **Check.** `validate`. Fix every item it lists (isolated pixels, off-palette, semi-transparent).
   Then `preview` once more and judge the **2x game-size view**, not just the zoomed one.
7. Use `get_ascii` when you need exact coordinates to correct something.

## Rules that make pixel art look good
- 3 to 4 colors per material (shadow, base, highlight, optional accent). Do not use every palette color.
- Hue-shift ramps: shadows lean cooler/darker, highlights warmer/lighter. The palette already does this; use it.
- No single stray pixels, no 1px "noise" in flat areas, no semi-transparency.
- Lines should be clean: avoid "jaggies" (staircases with uneven steps). Steps of 1-1-1 or 2-2-2, not 1-2-1.
- Symmetric characters: draw one half, then `mirror`, then add asymmetric details.
- Readable at game size: the eyes and the main shape must be clear in the 2x view.

## Animation
- Make frame 0, then `duplicate` it for each new frame and edit the copy. Same canvas size for all frames.
- Idle: 2-4 frames, move head/body by 1px (`shift` on parts, or redraw). Walk: 4 or 6 frames.
- Reuse parts with `stamp` (body once, legs per frame). Keep the silhouette volume constant between frames.
- `preview(names=[frame0, frame1, ...])` shows them side by side; check for popping.
- Name frames `<char>_<anim><n>`, e.g. `hero_walk0`.

## Delivering to Godot
- `export_godot(sheet="hero", animations={"idle": [...], "walk": [...]}, fps=8, res_path="res://assets/sprites/")`
  writes the sheet PNG and a SpriteFrames `.tres`. Tell the user: use AnimatedSprite2D, load the .tres,
  and set Project Settings > Rendering > Textures > Default Texture Filter to **Nearest**.
- Single static sprite: `export_png(name)`.

## Pixelorama round trip
- Sprites live as `<name>.png` in the work folder. The user can open them in Pixelorama, polish by hand,
  and export (File > Export) as PNG over the same file. The server reloads it automatically on the next call.
- For an imported image (AI output, PixelLab, reference): `load_png` -> `set_palette` -> `resize` (method
  `box` when shrinking) -> `quantize` -> `validate`.
