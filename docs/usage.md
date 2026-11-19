# Usage

## Workflow

1. **Brief**: "Make a 32x32 slime enemy, idle (2 frames) and hop (4 frames)". Claude reads `STYLE_GUIDE.md`.
2. **Claude draws**: silhouette, flat colors, shading, outline. It calls `preview` after every few steps,
   corrects itself, then runs `validate`.
3. **You review**: open `art/work/slime.png` in Pixelorama (or any editor), fix what you dislike and export
   as PNG over the same file. The server reloads it on the next call; no restart needed.
4. **Animate**: Claude duplicates frames, edits them and previews them side by side.
5. **Ship**: `export_godot` writes the sheet PNG and a SpriteFrames `.tres`. In Godot use an
   AnimatedSprite2D, load the `.tres` and set Project Settings > Rendering > Textures >
   Default Texture Filter to **Nearest**.

Tip: once you finish a sprite you love, add it to the style guide as the reference. Consistency across the
game comes from that file, not from the tools.

## Tools (27)

| Group | Tools |
|---|---|
| Sprites | `new_sprite`, `list_sprites`, `duplicate`, `load_png`, `resize`, `quantize` |
| Palette | `set_palette`, `get_palette` (presets: `db16`, `pico8`; locked per sprite) |
| Drawing | `draw_ascii`, `draw_pixels`, `draw_rect`, `draw_line`, `draw_ellipse`, `draw_polygon`, `flood_fill`, `replace_color` |
| Finishing | `outline`, `shade`, `mirror`, `flip`, `shift`, `stamp` |
| Seeing / checking | `preview` (rulers, grid, 2x game-size view, multi-frame strip), `get_ascii`, `validate` |
| Export | `export_png`, `export_godot` |

## Pixelorama and other editors

The server never talks to an editor. Both sides read and write PNG files in a shared folder, so with Docker
the host folder is bind-mounted at `/work` and the editor opens the same files on the host.

Any editor that opens and saves PNG works (Pixelorama, Aseprite, LibreSprite, GIMP, Krita, Piskel...).
Caveats:

- Export flat PNG every time. Native formats (`.pxo`, `.aseprite`, `.psd`, `.xcf`), layers and frames are not read.
- Keep to the sprite's locked palette; palette tools (`quantize`, `replace_color`) assume it.
- Avoid saving while Claude is writing the same sprite.

## Optional: better first drafts with AI

For richer characters, generate a first draft with an AI pixel art tool such as PixelLab, then bring it in:
`load_png` -> `set_palette` -> `resize` -> `quantize` -> `validate`, and let Claude clean it up and animate it.

## Limits

- It improves consistency and removes the worst problems (noise, off-palette colors, blurry shapes).
  Complex characters and expressive animation still benefit from a hand polish.
- Max canvas 256x256. Pixel art is best at 16 to 64 px.
