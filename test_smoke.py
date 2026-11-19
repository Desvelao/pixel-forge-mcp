"""End-to-end smoke test: starts server.py over stdio and calls the tools like Claude Code would.
Run:  python test_smoke.py
"""
import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

HERE = Path(__file__).parent


def iserr(res):
    return bool(getattr(res, "is_error", getattr(res, "isError", False)))


def text(res):
    return "".join(c.text for c in res.content if getattr(c, "type", "") == "text")


async def main():
    tmp = Path(tempfile.mkdtemp(prefix="pf-"))
    env = {**os.environ, "PIXEL_FORGE_DIR": str(tmp / "work"), "PIXEL_FORGE_EXPORT": str(tmp / "out")}
    params = StdioServerParameters(command=sys.executable, args=[str(HERE / "server.py")], env=env)
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            tools = [t.name for t in (await s.list_tools()).tools]
            print("tools:", len(tools), tools)

            async def call(tool, **kw):
                res = await s.call_tool(tool, kw)
                assert not iserr(res), f"{tool} failed: {text(res)}"
                return res

            print(text(await call("new_sprite", name="blob0", width=16, height=16, preset="db16")))
            # palette indices: 0 dark, 6 red, 12 skin, 15 white
            rows = [
                "................",
                "................",
                "................",
                ".....666666.....",
                "....66666666....",
                "...6666666666...",
                "...6666666666...",
                "...66f6666f66...",
                "...6666666666...",
                "...6666666666...",
                "....66666666....",
                ".....666666.....",
                "................",
                "................",
                "................",
                "................",
            ]
            print(text(await call("draw_ascii", name="blob0", rows=rows, legend={"f": "p15"})))
            print(text(await call("shade", name="blob0", base="p6", highlight="p12", shadow="p1", light="top_left")))
            print(text(await call("outline", name="blob0", color="p0")))
            print(text(await call("draw_pixels", name="blob0", pixels=[[0, 0, "p9"]])))  # stray pixel on purpose
            v = json.loads(text(await call("validate", name="blob0")))
            print("validate:", v)
            assert v["isolated_pixels"] == [[0, 0]], v
            assert v["verdict"].startswith("fix")

            # palette lock must reject off-palette colors
            bad = await s.call_tool("draw_pixels", {"name": "blob0", "pixels": [[1, 1, "#123456"]]})
            assert iserr(bad) and "not in the palette" in text(bad), text(bad)
            print("palette lock ok:", text(bad)[:70])

            print(text(await call("draw_pixels", name="blob0", pixels=[[0, 0, "clear"]])))
            await call("duplicate", src="blob0", dst="blob1")
            print(text(await call("shift", name="blob1", dx=0, dy=1)))

            res = await call("preview", names=["blob0"])
            imgs = [c for c in res.content if getattr(c, "type", "") == "image"]
            assert imgs, "preview returned no image"
            res2 = await call("preview", names=["blob0", "blob1"])
            assert [c for c in res2.content if getattr(c, "type", "") == "image"]
            print("preview ok:", len(imgs[0].data), "b64 chars")

            print(text(await call("get_ascii", name="blob0")))
            print(text(await call("mirror", name="blob0", axis="vertical", keep="left")))
            print(text(await call("export_png", name="blob0", scale=8)))
            print(text(await call("export_godot", sheet="blob", animations={"idle": ["blob0", "blob1"]},
                                  res_path="res://assets/sprites/")))
    print((tmp / "out" / "blob.tres").read_text())
    print("files:", sorted(p.name for p in (tmp / "out").iterdir()))
    print("workdir:", tmp)
    print("ALL OK")


asyncio.run(main())


async def roundtrip():
    """Pixelorama round trip (external PNG edit is auto-reloaded) and import -> palette -> quantize."""
    import numpy as np
    from PIL import Image as PI
    tmp = Path(tempfile.mkdtemp(prefix="pf-rt-"))
    env = {**os.environ, "PIXEL_FORGE_DIR": str(tmp / "work"), "PIXEL_FORGE_EXPORT": str(tmp / "out")}
    params = StdioServerParameters(command=sys.executable, args=[str(HERE / "server.py")], env=env)
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()

            async def call(tool, **kw):
                res = await s.call_tool(tool, kw)
                assert not iserr(res), f"{tool} failed: {text(res)}"
                return res

            await call("new_sprite", name="a", width=8, height=8, preset="db16")
            await call("draw_rect", name="a", x=2, y=2, w=4, h=4, color="p6")
            # simulate saving from Pixelorama: overwrite the PNG on disk
            png = tmp / "work" / "a.png"
            im = PI.open(png).convert("RGBA")
            im.putpixel((0, 0), (0xd0, 0x46, 0x48, 255))   # a red pixel added "by hand"
            im.save(png)
            os.utime(png, (png.stat().st_atime + 5, png.stat().st_mtime + 5))
            ascii_ = text(await call("get_ascii", name="a"))
            assert " 0 6" in ascii_, ascii_  # first row starts with the hand-added red pixel
            print("auto-reload after external edit: ok")

            # import an 'AI' image with off-palette colors, snap it to db16
            rng = np.random.default_rng(1)
            arr = rng.integers(0, 256, (12, 12, 4), dtype=np.uint8)
            arr[..., 3] = 255
            ref = tmp / "ai.png"
            PI.fromarray(arr, "RGBA").save(ref)
            await call("load_png", path=str(ref), name="ai")
            await call("set_palette", name="ai", preset="db16")
            await call("quantize", name="ai")
            v = json.loads(text(await call("validate", name="ai")))
            assert v["off_palette"] == [], v
            print("import -> palette -> quantize: ok, colors used:", v["colors_used"])

            # stamp / flood_fill / replace_color / flip
            await call("new_sprite", name="b", width=8, height=8, preset="db16")
            await call("stamp", name="b", src="a", x=0, y=0)
            await call("flood_fill", name="b", x=7, y=7, color="p2")
            await call("replace_color", name="b", old="p6", new="p9")
            await call("flip", name="b", direction="horizontal")
            print("stamp/fill/replace/flip: ok")
    print("ROUNDTRIP OK")


asyncio.run(roundtrip())
