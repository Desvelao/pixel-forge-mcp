#!/usr/bin/env python3
"""pixel-forge: an MCP server that lets Claude Code make pixel art with a feedback loop.

Why this exists: Claude places pixels blind. This server gives it (1) a locked palette,
(2) drawing and ASCII tools, (3) shading/outline helpers, (4) a validator that finds noisy
pixels, and (5) an upscaled, gridded preview image it can LOOK at and then fix.
Sprites are plain PNGs, so Pixelorama (or any editor) can open, polish and re-save them.

Env vars:
  PIXEL_FORGE_DIR     working folder for sprite PNGs (default ./pixel-work)
  PIXEL_FORGE_EXPORT  where exports go; point it into your Godot project, e.g. /game/assets/sprites
                      (default <PIXEL_FORGE_DIR>/export)
"""
from __future__ import annotations

import functools
import io
import json
import os
import re
from collections import deque
from pathlib import Path
from typing import Optional

import numpy as np
try:  # mcp >= 2
    from mcp.server.mcpserver import Image, MCPServer as FastMCP
    from mcp.server.mcpserver.exceptions import ToolError
except ImportError:  # mcp 1.x
    from mcp.server.fastmcp import FastMCP, Image
    from mcp.server.fastmcp.exceptions import ToolError
from PIL import Image as PILImage
from PIL import ImageDraw, ImageFont

WORK = Path(os.environ.get("PIXEL_FORGE_DIR", "./pixel-work")).resolve()
EXPORT = Path(os.environ.get("PIXEL_FORGE_EXPORT", str(WORK / "export"))).resolve()
MAX_SIZE = 256

PRESETS: dict[str, list[str]] = {
    # DawnBringer 16: a great default for readable, cohesive sprites
    "db16": ["#140c1c", "#442434", "#30346d", "#4e4a4e", "#854c30", "#346524", "#d04648", "#757161",
             "#597dce", "#d27d2c", "#8595a1", "#6daa2c", "#d2aa99", "#6dc2ca", "#dad45e", "#deeed6"],
    "pico8": ["#000000", "#1d2b53", "#7e2553", "#008751", "#ab5236", "#5f574f", "#c2c3c7", "#fff1e8",
              "#ff004d", "#ffa300", "#ffec27", "#00e436", "#29adff", "#83769c", "#ff77a8", "#ffccaa"],
}

CHARS = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
RGBA = tuple[int, int, int, int]


def _from_arr(arr: np.ndarray, mode: str = "RGBA") -> PILImage.Image:
    """Pillow >= 12 returns read-only images from fromarray; copy so pixels stay writable."""
    return PILImage.fromarray(arr, mode).copy()

mcp = FastMCP("pixel-forge")


def tool(fn):
    """Register an MCP tool; expected errors reach Claude as readable messages (not a generic crash)."""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except (ValueError, KeyError, OSError) as e:
            raise ToolError(str(e)) from e
    return mcp.tool()(wrapper)


# ----------------------------------------------------------------------------- state

class Sprite:
    def __init__(self, name: str, img: PILImage.Image, palette: list[RGBA]):
        self.name = name
        self.img = img
        self.palette = palette
        self.mtime = 0

    @property
    def w(self) -> int:
        return self.img.width

    @property
    def h(self) -> int:
        return self.img.height


_SPRITES: dict[str, Sprite] = {}


def _name(n: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_\-]{1,64}", n or ""):
        raise ValueError("name must be 1-64 characters: letters, digits, _ or -")
    return n


def _png(n: str) -> Path:
    return WORK / f"{n}.png"


def _meta(n: str) -> Path:
    return WORK / f"{n}.json"


def _hex_to_rgba(h: str) -> RGBA:
    h = h.strip().lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if len(h) == 6:
        h += "ff"
    if len(h) != 8 or not re.fullmatch(r"[0-9a-fA-F]{8}", h):
        raise ValueError(f"bad color {h!r}: use #rgb, #rrggbb, 'clear', or a palette index like 'p3'")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4, 6))  # type: ignore[return-value]


def _to_hex(c: RGBA) -> str:
    return "#%02x%02x%02x" % c[:3]


def _normalize(img: PILImage.Image) -> PILImage.Image:
    """Fully transparent pixels become (0,0,0,0) so comparisons are exact."""
    arr = np.array(img.convert("RGBA"))
    arr[arr[..., 3] == 0] = 0
    return _from_arr(arr, "RGBA")


def _read_disk(n: str, keep_palette: Optional[list[RGBA]] = None) -> Sprite:
    img = PILImage.open(_png(n))
    if img.width > MAX_SIZE or img.height > MAX_SIZE:
        raise ValueError(f"{n}.png is {img.width}x{img.height}; max is {MAX_SIZE}x{MAX_SIZE}")
    pal: list[RGBA] = keep_palette if keep_palette is not None else []
    if keep_palette is None and _meta(n).exists():
        pal = [_hex_to_rgba(c) for c in json.loads(_meta(n).read_text()).get("palette", [])]
    sp = Sprite(n, _normalize(img), pal)
    sp.mtime = _png(n).stat().st_mtime_ns
    return sp


def _get(n: str) -> Sprite:
    """Fetch a sprite. Auto-reloads if the PNG changed on disk (e.g. you saved it from Pixelorama)."""
    n = _name(n)
    sp = _SPRITES.get(n)
    if sp is not None:
        if _png(n).exists() and _png(n).stat().st_mtime_ns != sp.mtime:
            sp = _SPRITES[n] = _read_disk(n, keep_palette=sp.palette)
        return sp
    if _png(n).exists():
        sp = _SPRITES[n] = _read_disk(n)
        return sp
    raise ValueError(f"no sprite named {n!r}: call new_sprite or load_png first")


def _save(sp: Sprite) -> None:
    WORK.mkdir(parents=True, exist_ok=True)
    sp.img.save(_png(sp.name))
    _meta(sp.name).write_text(json.dumps({"palette": [_to_hex(c) for c in sp.palette]}))
    sp.mtime = _png(sp.name).stat().st_mtime_ns


def _done(sp: Sprite, msg: str) -> str:
    _save(sp)
    return f"{msg}  [{sp.name} {sp.w}x{sp.h}]"


def _color(sp: Sprite, c: str, enforce: bool = True) -> RGBA:
    c = c.strip()
    if c.lower() in ("clear", "transparent", "none"):
        return (0, 0, 0, 0)
    m = re.fullmatch(r"p(\d+)", c.lower())
    if m:
        i = int(m.group(1))
        if i >= len(sp.palette):
            raise ValueError(f"palette index p{i} out of range (palette has {len(sp.palette)} colors)")
        return sp.palette[i]
    rgba = _hex_to_rgba(c)
    if rgba[3] != 255:
        raise ValueError("semi-transparent colors are not allowed in pixel art; use 'clear' or an opaque color")
    if enforce and sp.palette and rgba not in sp.palette:
        raise ValueError(f"{c} is not in the palette of {sp.name!r}. Use a palette index (p0..p{len(sp.palette)-1}) "
                         f"or call set_palette to change the palette.")
    return rgba


def _legend_chars(sp: Sprite) -> dict[RGBA, str]:
    """Stable char for each color: palette index chars first, then extras."""
    mapping: dict[RGBA, str] = {c: CHARS[i] for i, c in enumerate(sp.palette[:len(CHARS)])}
    nxt = len(mapping)
    arr = np.array(sp.img)
    for col in {tuple(int(v) for v in px) for px in arr.reshape(-1, 4) if px[3] == 255}:
        if col not in mapping and nxt < len(CHARS):
            mapping[col] = CHARS[nxt]  # type: ignore[index]
            nxt += 1
    return mapping


# ----------------------------------------------------------------------------- sprite lifecycle

@tool
def new_sprite(name: str, width: int, height: int, palette: Optional[list[str]] = None,
               preset: Optional[str] = None) -> str:
    """Create a transparent canvas. Give `palette` (hex list) or `preset` ('db16' or 'pico8').
    With a palette set, drawing any other color is rejected (this keeps sprites cohesive).
    Use sizes like 16, 32 or 64. Leave a 1px empty margin so outlines are not clipped."""
    _name(name)
    if not (1 <= width <= MAX_SIZE and 1 <= height <= MAX_SIZE):
        raise ValueError(f"width/height must be 1..{MAX_SIZE}")
    cols = PRESETS[preset] if preset else (palette or [])
    if preset and preset not in PRESETS:
        raise ValueError(f"unknown preset {preset!r}; options: {list(PRESETS)}")
    sp = Sprite(name, PILImage.new("RGBA", (width, height), (0, 0, 0, 0)), [_hex_to_rgba(c) for c in cols])
    _SPRITES[name] = sp
    return _done(sp, f"created, palette of {len(sp.palette)} colors")


@tool
def set_palette(name: str, colors: Optional[list[str]] = None, preset: Optional[str] = None) -> str:
    """Replace a sprite's palette (hex list or preset). Existing pixels are NOT recolored;
    run quantize afterwards to snap them to the new palette. Empty list = no palette lock."""
    sp = _get(name)
    if preset:
        if preset not in PRESETS:
            raise ValueError(f"unknown preset {preset!r}; options: {list(PRESETS)}")
        colors = PRESETS[preset]
    sp.palette = [_hex_to_rgba(c) for c in (colors or [])]
    return _done(sp, f"palette set ({len(sp.palette)} colors)")


@tool
def get_palette(name: str) -> str:
    """Show the palette as 'p<index> char hex' lines."""
    sp = _get(name)
    if not sp.palette:
        return "no palette lock (any opaque color is allowed)"
    return "\n".join(f"p{i}  '{CHARS[i]}'  {_to_hex(c)}" for i, c in enumerate(sp.palette[:len(CHARS)]))


@tool
def list_sprites() -> str:
    """List sprites in the working folder."""
    WORK.mkdir(parents=True, exist_ok=True)
    out = []
    for p in sorted(WORK.glob("*.png")):
        try:
            with PILImage.open(p) as im:
                out.append(f"{p.stem}  {im.width}x{im.height}")
        except Exception:
            pass
    return "\n".join(out) or "(no sprites yet)"


@tool
def duplicate(src: str, dst: str) -> str:
    """Copy a sprite (use for animation frames: duplicate, then edit the copy)."""
    s = _get(src)
    sp = Sprite(_name(dst), s.img.copy(), list(s.palette))
    _SPRITES[dst] = sp
    return _done(sp, f"copied from {src}")


@tool
def load_png(path: str, name: str) -> str:
    """Import any PNG (Pixelorama export, PixelLab/AI output, a reference) as a sprite.
    No palette lock is set; call set_palette then quantize to snap it to your palette."""
    p = Path(path).expanduser()
    if not p.is_file():
        raise ValueError(f"file not found: {p}")
    img = PILImage.open(p)
    if img.width > MAX_SIZE or img.height > MAX_SIZE:
        raise ValueError(f"image is {img.width}x{img.height}; max {MAX_SIZE}. Use resize in your tool first or crop.")
    sp = Sprite(_name(name), _normalize(img), [])
    _SPRITES[name] = sp
    return _done(sp, f"loaded {p.name}")


@tool
def resize(name: str, width: int, height: int, method: str = "nearest", then_quantize: bool = True) -> str:
    """Rescale a sprite. method 'nearest' keeps hard pixels; 'box' averages (better for shrinking AI
    images). If a palette is set and then_quantize is true, colors are snapped back to it."""
    sp = _get(name)
    if not (1 <= width <= MAX_SIZE and 1 <= height <= MAX_SIZE):
        raise ValueError(f"width/height must be 1..{MAX_SIZE}")
    resample = PILImage.NEAREST if method == "nearest" else PILImage.BOX
    sp.img = _normalize(sp.img.resize((width, height), resample))
    if sp.palette and then_quantize:
        _quantize(sp)
    return _done(sp, f"resized with {method}")


def _quantize(sp: Sprite) -> int:
    if not sp.palette:
        raise ValueError("set a palette first (set_palette)")
    arr = np.array(sp.img)
    mask = arr[..., 3] >= 128
    pal = np.array([c[:3] for c in sp.palette], dtype=np.int32)
    rgb = arr[..., :3].astype(np.int32)
    idx = ((rgb[:, :, None, :] - pal[None, None, :, :]) ** 2).sum(-1).argmin(-1)
    out = np.zeros_like(arr)
    out[mask, :3] = pal[idx][mask]
    out[mask, 3] = 255
    changed = int((out != arr).any(-1).sum())
    sp.img = _from_arr(out, "RGBA")
    return changed


@tool
def quantize(name: str) -> str:
    """Snap every pixel to the nearest palette color and make alpha strictly 0 or 255."""
    sp = _get(name)
    n = _quantize(sp)
    return _done(sp, f"quantized, {n} pixels changed")


# ----------------------------------------------------------------------------- drawing

@tool
def draw_pixels(name: str, pixels: list[tuple[int, int, str]]) -> str:
    """Set individual pixels: [[x, y, color], ...]. color = '#hex', 'p3' (palette index) or 'clear'."""
    sp = _get(name)
    px = sp.img.load()
    clipped = 0
    for x, y, c in pixels:
        col = _color(sp, c)
        if 0 <= x < sp.w and 0 <= y < sp.h:
            px[x, y] = col
        else:
            clipped += 1
    return _done(sp, f"{len(pixels) - clipped} pixels set" + (f", {clipped} out of bounds skipped" if clipped else ""))


@tool
def draw_ascii(name: str, rows: list[str], legend: Optional[dict[str, str]] = None,
               x: int = 0, y: int = 0) -> str:
    """Paint a block from text rows; the most precise way to draw. '.' is transparent.
    Characters map to the palette by index ('0'..'9','a'..) unless `legend` overrides
    them, e.g. {"k": "#140c1c", "r": "p6"}. `x`,`y` is the top-left corner."""
    sp = _get(name)
    table: dict[str, RGBA] = {CHARS[i]: c for i, c in enumerate(sp.palette[:len(CHARS)])}
    for ch, col in (legend or {}).items():
        table[ch] = _color(sp, col)
    px = sp.img.load()
    unknown: set[str] = set()
    n = 0
    for j, row in enumerate(rows):
        for i, ch in enumerate(row):
            if ch in ". ":
                col = (0, 0, 0, 0)
            elif ch in table:
                col = table[ch]
            else:
                unknown.add(ch)
                continue
            if 0 <= x + i < sp.w and 0 <= y + j < sp.h:
                px[x + i, y + j] = col
                n += 1
    if unknown:
        raise ValueError(f"characters {sorted(unknown)} are not in the legend or palette; nothing guaranteed drawn")
    return _done(sp, f"{n} cells painted")


@tool
def get_ascii(name: str) -> str:
    """Read the sprite back as text with coordinates and a legend, for exact inspection/editing."""
    sp = _get(name)
    mp = _legend_chars(sp)
    px = sp.img.load()
    ruler = "   " + "".join(str((i // 10) % 10) if i % 10 == 0 else " " for i in range(sp.w))
    ruler2 = "   " + "".join(str(i % 10) for i in range(sp.w))
    lines = [ruler, ruler2]
    for j in range(sp.h):
        row = "".join("." if px[i, j][3] == 0 else mp.get(tuple(px[i, j]), "?") for i in range(sp.w))  # type: ignore[arg-type]
        lines.append(f"{j:>2} {row}")
    lines.append("legend: . = clear; " + "; ".join(f"{ch} = {_to_hex(c)}" for c, ch in mp.items()))
    return "\n".join(lines)


@tool
def draw_rect(name: str, x: int, y: int, w: int, h: int, color: str, filled: bool = True) -> str:
    """Rectangle with top-left (x,y) and size w x h."""
    sp = _get(name)
    col = _color(sp, color)
    ImageDraw.Draw(sp.img).rectangle([x, y, x + w - 1, y + h - 1], fill=col if filled else None, outline=col)
    return _done(sp, "rect drawn")


@tool
def draw_line(name: str, x0: int, y0: int, x1: int, y1: int, color: str) -> str:
    """1px line between two points (inclusive)."""
    sp = _get(name)
    ImageDraw.Draw(sp.img).line([x0, y0, x1, y1], fill=_color(sp, color), width=1)
    return _done(sp, "line drawn")


@tool
def draw_ellipse(name: str, x: int, y: int, w: int, h: int, color: str, filled: bool = True) -> str:
    """Ellipse inside the box with top-left (x,y) and size w x h."""
    sp = _get(name)
    col = _color(sp, color)
    ImageDraw.Draw(sp.img).ellipse([x, y, x + w - 1, y + h - 1], fill=col if filled else None, outline=col)
    return _done(sp, "ellipse drawn")


@tool
def draw_polygon(name: str, points: list[tuple[int, int]], color: str, filled: bool = True) -> str:
    """Polygon through the given [x, y] points."""
    sp = _get(name)
    col = _color(sp, color)
    ImageDraw.Draw(sp.img).polygon(points, fill=col if filled else None, outline=col)
    return _done(sp, "polygon drawn")


@tool
def flood_fill(name: str, x: int, y: int, color: str) -> str:
    """Fill the contiguous (4-connected) region of same-colored pixels containing (x,y)."""
    sp = _get(name)
    if not (0 <= x < sp.w and 0 <= y < sp.h):
        raise ValueError("start point out of bounds")
    px = sp.img.load()
    target, new = px[x, y], _color(sp, color)
    if target == new:
        return "nothing to do (already that color)"
    q = deque([(x, y)])
    px[x, y] = new
    n = 1
    while q:
        cx, cy = q.popleft()
        for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
            if 0 <= nx < sp.w and 0 <= ny < sp.h and px[nx, ny] == target:
                px[nx, ny] = new
                q.append((nx, ny))
                n += 1
    return _done(sp, f"{n} pixels filled")


@tool
def replace_color(name: str, old: str, new: str) -> str:
    """Swap every pixel of one color for another (palette swaps, recolored variants)."""
    sp = _get(name)
    o, nw = _color(sp, old, enforce=False), _color(sp, new)
    arr = np.array(sp.img)
    mask = (arr == np.array(o, dtype=np.uint8)).all(-1)
    arr[mask] = nw
    sp.img = _from_arr(arr, "RGBA")
    return _done(sp, f"{int(mask.sum())} pixels recolored")


# ----------------------------------------------------------------------------- finishing helpers

@tool
def outline(name: str, color: str, diagonals: bool = True) -> str:
    """Add a 1px outline around all opaque pixels (drawn on transparent pixels only).
    Use a dark palette color, not pure black. Keep a 1px empty margin or the outline gets clipped."""
    sp = _get(name)
    col = _color(sp, color)
    src = np.array(sp.img)
    opaque = src[..., 3] > 0
    pad = np.pad(opaque, 1)
    nb = pad[:-2, 1:-1] | pad[2:, 1:-1] | pad[1:-1, :-2] | pad[1:-1, 2:]
    if diagonals:
        nb |= pad[:-2, :-2] | pad[:-2, 2:] | pad[2:, :-2] | pad[2:, 2:]
    new = nb & ~opaque
    src[new] = col
    sp.img = _from_arr(src, "RGBA")
    edge = int(opaque[0].sum() + opaque[-1].sum() + opaque[:, 0].sum() + opaque[:, -1].sum())
    note = f"; WARNING {edge} opaque pixels touch the canvas edge, outline may be clipped" if edge else ""
    return _done(sp, f"{int(new.sum())} outline pixels added{note}")


@tool
def shade(name: str, base: str, highlight: str, shadow: str, light: str = "top_left", depth: int = 1) -> str:
    """Add form shading to a flat region. Pixels of color `base` that lie within `depth` pixels of a
    region edge facing the light become `highlight`; those facing away become `shadow`.
    light: top_left, top, top_right, left, right. Run once per flat-colored region.
    Keep the same light direction for the whole sprite."""
    dirs = {"top_left": (-1, -1), "top": (0, -1), "top_right": (1, -1), "left": (-1, 0), "right": (1, 0)}
    if light not in dirs:
        raise ValueError(f"light must be one of {list(dirs)}")
    sp = _get(name)
    b, hi, lo = _color(sp, base), _color(sp, highlight), _color(sp, shadow)
    dx, dy = dirs[light]
    snap = sp.img.copy().load()
    px = sp.img.load()

    def is_base(x: int, y: int) -> bool:
        return 0 <= x < sp.w and 0 <= y < sp.h and snap[x, y] == b

    def edge_toward(x: int, y: int, sx: int, sy: int) -> bool:
        for k in range(1, depth + 1):
            if (sx and not is_base(x + sx * k, y)) or (sy and not is_base(x, y + sy * k)):
                return True
        return False

    nh = ns = 0
    for y in range(sp.h):
        for x in range(sp.w):
            if snap[x, y] != b:
                continue
            if edge_toward(x, y, dx, dy):
                px[x, y] = hi
                nh += 1
            elif edge_toward(x, y, -dx, -dy):
                px[x, y] = lo
                ns += 1
    return _done(sp, f"{nh} highlight, {ns} shadow pixels")


@tool
def mirror(name: str, axis: str = "vertical", keep: str = "left") -> str:
    """Make a sprite symmetric: draw one half, mirror it onto the other.
    axis 'vertical' mirrors left/right (keep 'left' or 'right'); axis 'horizontal' mirrors
    top/bottom (keep 'top' or 'bottom'). An odd center row/column is left untouched."""
    sp = _get(name)
    w, h = sp.w, sp.h
    if axis == "vertical":
        half = w // 2
        if keep == "left":
            part = sp.img.crop((0, 0, half, h)).transpose(PILImage.FLIP_LEFT_RIGHT)
            sp.img.paste(part, (w - half, 0))
        else:
            part = sp.img.crop((w - half, 0, w, h)).transpose(PILImage.FLIP_LEFT_RIGHT)
            sp.img.paste(part, (0, 0))
    else:
        half = h // 2
        if keep == "top":
            part = sp.img.crop((0, 0, w, half)).transpose(PILImage.FLIP_TOP_BOTTOM)
            sp.img.paste(part, (0, h - half))
        else:
            part = sp.img.crop((0, h - half, w, h)).transpose(PILImage.FLIP_TOP_BOTTOM)
            sp.img.paste(part, (0, 0))
    return _done(sp, f"mirrored ({axis}, keeping {keep})")


@tool
def flip(name: str, direction: str = "horizontal") -> str:
    """Flip the whole sprite 'horizontal' or 'vertical'."""
    sp = _get(name)
    sp.img = sp.img.transpose(PILImage.FLIP_LEFT_RIGHT if direction == "horizontal" else PILImage.FLIP_TOP_BOTTOM)
    return _done(sp, f"flipped {direction}")


@tool
def shift(name: str, dx: int, dy: int, wrap: bool = False) -> str:
    """Move the whole image by (dx, dy) pixels. Handy for walk-cycle bobbing."""
    sp = _get(name)
    if wrap:
        from PIL import ImageChops
        sp.img = ImageChops.offset(sp.img, dx, dy)
    else:
        out = PILImage.new("RGBA", sp.img.size, (0, 0, 0, 0))
        out.paste(sp.img, (dx, dy))
        sp.img = out
    return _done(sp, f"shifted by ({dx},{dy})")


@tool
def stamp(name: str, src: str, x: int, y: int, flip_h: bool = False) -> str:
    """Paste another sprite onto this one at (x,y); transparent pixels do not overwrite.
    Compose characters from parts (body + head + weapon) or reuse a body across frames."""
    sp, s = _get(name), _get(src)
    part = s.img.transpose(PILImage.FLIP_LEFT_RIGHT) if flip_h else s.img
    sp.img.paste(part, (x, y), part)
    return _done(sp, f"stamped {src} at ({x},{y})")


# ----------------------------------------------------------------------------- checking and seeing

@tool
def validate(name: str) -> dict:
    """Quality check. Reports off-palette colors, semi-transparent pixels, isolated stray pixels,
    unused palette colors, color count, and pixels touching the canvas edge. Fix what it lists."""
    sp = _get(name)
    arr = np.array(sp.img)
    a = arr[..., 3]
    opaque = a == 255
    report: dict = {"size": f"{sp.w}x{sp.h}", "opaque_pixels": int(opaque.sum())}

    semi = np.argwhere((a != 0) & (a != 255))
    report["semi_transparent"] = [[int(x), int(y)] for y, x in semi[:20]]

    pad = np.pad(opaque, 1)
    neigh = sum(pad[1 + dy:1 + dy + sp.h, 1 + dx:1 + dx + sp.w]
                for dy in (-1, 0, 1) for dx in (-1, 0, 1) if (dx or dy))
    stray = np.argwhere(opaque & (neigh == 0))
    report["isolated_pixels"] = [[int(x), int(y)] for y, x in stray[:30]]

    colors = {tuple(int(v) for v in arr[y, x]) for y, x in np.argwhere(opaque)}
    report["colors_used"] = len(colors)
    if sp.palette:
        pal = set(sp.palette)
        report["off_palette"] = sorted(_to_hex(c) for c in colors if c not in pal)  # type: ignore[arg-type]
        report["unused_palette_indexes"] = [i for i, c in enumerate(sp.palette) if c not in colors]
    report["border_pixels"] = int(opaque[0].sum() + opaque[-1].sum() + opaque[:, 0].sum() + opaque[:, -1].sum())

    problems = [k for k in ("semi_transparent", "isolated_pixels", "off_palette") if report.get(k)]
    report["verdict"] = "clean" if not problems else f"fix: {', '.join(problems)}"
    return report


def _checker(w: int, h: int, cell: int) -> PILImage.Image:
    yy, xx = np.mgrid[0:h, 0:w]
    tone = np.where(((xx // cell) + (yy // cell)) % 2 == 0, 205, 228).astype(np.uint8)
    arr = np.stack([tone, tone, tone, np.full_like(tone, 255)], -1)
    return _from_arr(arr, "RGBA")


def _panel(sp: Sprite, scale: int, grid: bool, rulers: bool) -> PILImage.Image:
    w, h = sp.w, sp.h
    bg = _checker(w * scale, h * scale, max(8, scale))
    bg.alpha_composite(sp.img.resize((w * scale, h * scale), PILImage.NEAREST))
    if grid and scale >= 6:
        ov = PILImage.new("RGBA", bg.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(ov)
        for i in range(w + 1):
            d.line([(i * scale, 0), (i * scale, h * scale)], fill=(0, 0, 0, 80 if i % 8 == 0 else 26))
        for j in range(h + 1):
            d.line([(0, j * scale), (w * scale, j * scale)], fill=(0, 0, 0, 80 if j % 8 == 0 else 26))
        bg.alpha_composite(ov)
    if not rulers:
        return bg
    ml = mt = 24
    out = PILImage.new("RGBA", (w * scale + ml, h * scale + mt), (40, 40, 48, 255))
    out.paste(bg, (ml, mt))
    d, f = ImageDraw.Draw(out), ImageFont.load_default()
    step = 4 if scale >= 10 else 8
    for i in range(0, w, step):
        d.text((ml + i * scale + 2, 6), str(i), fill=(235, 235, 235, 255), font=f)
    for j in range(0, h, step):
        d.text((2, mt + j * scale + 2), str(j), fill=(235, 235, 235, 255), font=f)
    return out


@tool
def preview(names: list[str], scale: int = 0, grid: bool = True) -> list:
    """RENDER THE SPRITE AS AN IMAGE AND LOOK AT IT. Call this after every few edits.
    One name: big view with pixel-coordinate rulers plus a 2x 'game size' view.
    Several names: side-by-side strip (use it to compare animation frames).
    scale 0 = automatic."""
    sprites = [_get(n) for n in names]
    f = ImageFont.load_default()
    if len(sprites) == 1:
        sp = sprites[0]
        s = scale or max(1, min(32, 448 // max(sp.w, sp.h)))
        big = _panel(sp, s, grid, rulers=True)
        small = _panel(sp, 2, False, False)
        canvas = PILImage.new("RGBA", (big.width + 16 + small.width + 12, max(big.height, small.height + 30) + 8),
                              (40, 40, 48, 255))
        canvas.paste(big, (4, 4))
        canvas.paste(small, (big.width + 16, 28))
        ImageDraw.Draw(canvas).text((big.width + 16, 10), "game size (2x)", fill=(235, 235, 235, 255), font=f)
    else:
        total_w = sum(sp.w for sp in sprites)
        s = scale or max(1, min(16, (1100 - 12 * len(sprites)) // total_w, 320 // max(sp.h for sp in sprites)))
        panels = [_panel(sp, s, grid, False) for sp in sprites]
        canvas = PILImage.new("RGBA", (sum(p.width for p in panels) + 12 * (len(panels) + 1),
                                       max(p.height for p in panels) + 36), (40, 40, 48, 255))
        x = 12
        for sp, p in zip(sprites, panels):
            ImageDraw.Draw(canvas).text((x, 10), sp.name, fill=(235, 235, 235, 255), font=f)
            canvas.paste(p, (x, 28))
            x += p.width + 12
    buf = io.BytesIO()
    canvas.convert("RGB").save(buf, "PNG")
    (WORK / "previews").mkdir(parents=True, exist_ok=True)
    (WORK / "previews" / "last.png").write_bytes(buf.getvalue())
    return [Image(data=buf.getvalue(), format="png")]


# ----------------------------------------------------------------------------- export

@tool
def export_png(name: str, scale: int = 1) -> str:
    """Write a clean PNG into the export folder (scale>1 gives a nearest-neighbor enlarged copy)."""
    sp = _get(name)
    EXPORT.mkdir(parents=True, exist_ok=True)
    img = sp.img if scale == 1 else sp.img.resize((sp.w * scale, sp.h * scale), PILImage.NEAREST)
    out = EXPORT / (f"{name}.png" if scale == 1 else f"{name}@{scale}x.png")
    img.save(out)
    return f"wrote {out}"


@tool
def export_godot(sheet: str, animations: dict[str, list[str]], fps: int = 8, loop: bool = True,
                 res_path: str = "res://assets/sprites/") -> str:
    """Pack frames into one sprite sheet and write a Godot 4 SpriteFrames .tres next to it.
    animations: {"idle": ["hero_idle0", "hero_idle1"], "walk": [...]}. All frames must share one size.
    res_path is where the PNG will live inside the Godot project (res:// path, trailing slash).
    In Godot: AnimatedSprite2D -> Sprite Frames -> load the .tres. Set texture filter to Nearest."""
    if not animations:
        raise ValueError("animations is empty")
    frames = {a: [_get(n) for n in names] for a, names in animations.items()}
    sizes = {(s.w, s.h) for fl in frames.values() for s in fl}
    if len(sizes) != 1:
        raise ValueError(f"all frames must be the same size, got {sorted(sizes)}")
    fw, fh = sizes.pop()
    cols = max(len(fl) for fl in frames.values())
    rows = len(frames)
    sheet_img = PILImage.new("RGBA", (cols * fw, rows * fh), (0, 0, 0, 0))
    for r, (_, fl) in enumerate(frames.items()):
        for c, s in enumerate(fl):
            sheet_img.paste(s.img, (c * fw, r * fh))
    EXPORT.mkdir(parents=True, exist_ok=True)
    sheet_img.save(EXPORT / f"{sheet}.png")

    total = sum(len(fl) for fl in frames.values())
    L = [f'[gd_resource type="SpriteFrames" load_steps={total + 2} format=3]', "",
         f'[ext_resource type="Texture2D" path="{res_path}{sheet}.png" id="1"]', ""]
    for a, fl in frames.items():
        r = list(frames).index(a)
        for c in range(len(fl)):
            L += [f'[sub_resource type="AtlasTexture" id="AtlasTexture_{a}_{c}"]',
                  'atlas = ExtResource("1")',
                  f"region = Rect2({c * fw}, {r * fh}, {fw}, {fh})", ""]
    anims = []
    for a, fl in frames.items():
        fr = ",\n".join('{\n"duration": 1.0,\n"texture": SubResource("AtlasTexture_%s_%d")\n}' % (a, c)
                        for c in range(len(fl)))
        anims.append('{\n"frames": [%s],\n"loop": %s,\n"name": &"%s",\n"speed": %.1f\n}'
                     % (fr, "true" if loop else "false", a, float(fps)))
    L += ["[resource]", "animations = [" + ", ".join(anims) + "]", ""]
    (EXPORT / f"{sheet}.tres").write_text("\n".join(L))
    (EXPORT / f"{sheet}.json").write_text(json.dumps(
        {"frame_size": [fw, fh], "animations": {a: len(fl) for a, fl in frames.items()}, "fps": fps}, indent=2))
    return f"wrote {EXPORT / (sheet + '.png')}, .tres and .json ({total} frames, {fw}x{fh} each)"


if __name__ == "__main__":
    mcp.run()
