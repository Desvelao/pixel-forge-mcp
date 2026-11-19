# pixel-forge-mcp

An MCP server that lets Claude Code make pixel art **with a feedback loop**, plus a workflow around
**Pixelorama** (free, open source) for hand polishing. Everything is plain PNG, so any editor works.

Why it beats Claude drawing blind: a locked palette, precise drawing tools, shading and outline helpers,
a validator that finds noisy pixels, and an upscaled, gridded `preview` image that Claude looks at and then fixes.

## Install

Requires Docker and [Claude Code](https://claude.com/claude-code). Run from the project that will use the sprites
(for example your Godot project):

```bash
curl -fsSL https://raw.githubusercontent.com/Desvelao/pixel-forge-mcp/main/install.sh | sh -s -- --register --scaffold
```

This pulls `ghcr.io/desvelao/pixel-forge-mcp`, installs a `pixel-forge-mcp` launcher in `~/.local/bin`,
registers the MCP server with Claude Code, and copies the skill and `STYLE_GUIDE.md` into the project.
Drop the flags to only install the launcher. Then start a fresh `claude` session and run `/mcp`.

### Use the Docker image directly

```bash
mkdir -p art/work assets/sprites
claude mcp add pixel-forge -- docker run -i --rm -u "$(id -u):$(id -g)" \
  -v "$PWD/art/work:/work" \
  -v "$PWD/assets/sprites:/export" \
  ghcr.io/desvelao/pixel-forge-mcp:latest
```

- `/work`: one `<name>.png` per sprite. Open these in Pixelorama.
- `/export`: where `export_png` / `export_godot` write. Pointing it at your Godot `assets/sprites`
  folder means Godot picks the files up on its own.
- `-i` is required (stdio server, no port), do not add `-t`.

Pin a release with a tag (`ghcr.io/desvelao/pixel-forge-mcp:v0.1.0`). Other options (docker compose,
from source, other MCP clients, troubleshooting): [docs/installation.md](docs/installation.md).

### Skill and style guide

`--scaffold` copies these into your project; do it by hand otherwise:
- `.claude/skills/pixel-art/SKILL.md` (teaches Claude the loop and the pixel art rules)
- `STYLE_GUIDE.template.md` as `STYLE_GUIDE.md` (edit it: sizes, palette, mood, light direction)

## Workflow

1. **Brief**: "Make a 32x32 slime enemy, idle (2 frames) and hop (4 frames)". Claude reads the style guide.
2. **Claude draws**: silhouette, then flat colors, shading, outline. It calls `preview` after every few
   steps and corrects itself, then `validate`.
3. **You review**: open `art/work/slime.png` in Pixelorama, fix what you dislike by hand.
   Export as PNG over the same file. The server reloads it on the next call (no restart needed).
4. **Animate**: Claude duplicates frames, edits them, previews them side by side.
5. **Ship**: `export_godot` writes the sheet PNG and a SpriteFrames `.tres`.
   In Godot use an AnimatedSprite2D, load the `.tres`, and set
   Project Settings > Rendering > Textures > Default Texture Filter to **Nearest**.

The server never talks to Pixelorama: with Docker, the host work folder is bind-mounted at `/work`, and you
edit the same PNG files on the host.

## Tools (27)

| Group | Tools |
|---|---|
| Sprites | `new_sprite`, `list_sprites`, `duplicate`, `load_png`, `resize`, `quantize` |
| Palette | `set_palette`, `get_palette` (presets: `db16`, `pico8`; locked per sprite) |
| Drawing | `draw_ascii`, `draw_pixels`, `draw_rect`, `draw_line`, `draw_ellipse`, `draw_polygon`, `flood_fill`, `replace_color` |
| Finishing | `outline`, `shade`, `mirror`, `flip`, `shift`, `stamp` |
| Seeing / checking | `preview` (rulers, grid, 2x game-size view, multi-frame strip), `get_ascii`, `validate` |
| Export | `export_png`, `export_godot` |

Colors are `#rrggbb`, a palette index like `p6`, or `clear`. Semi-transparency is rejected on purpose.

## Limits (be realistic)
- It improves consistency and removes the worst problems (noise, off-palette colors, blurry shapes).
  Complex characters and expressive animation still benefit from your eye and a hand polish in Pixelorama.
- Max canvas 256x256. Pixel art is best at 16 to 64 px.
- Pixelorama's native `.pxo` format is not read; exchange is via PNG.

## Documentation

- [Installation](docs/installation.md): installer, `docker run`, compose, from source, upgrade, troubleshooting
- [Usage](docs/usage.md): workflow, tools, Pixelorama and other editors
- [Configuration](docs/configuration.md): env vars, mounts, importing PNGs
- [Development](docs/development.md): run from source, tests, CI, releasing
- [Changelog](CHANGELOG.md)

## Development quick start

```bash
pip install -r requirements.txt
python test_smoke.py
```
