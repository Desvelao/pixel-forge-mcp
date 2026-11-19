# pixel-forge-mcp documentation

pixel-forge is an MCP server that lets Claude Code make pixel art **with a feedback loop** (locked
palette, drawing tools, validator, upscaled preview). Sprites are plain PNGs, so you can polish them in
Pixelorama or any other editor.

| Page | What it covers |
|---|---|
| [Installation](installation.md) | One-line installer, `docker run`, docker compose, from source, upgrading, uninstalling |
| [Usage](usage.md) | The workflow with Claude, the 27 tools, using Pixelorama and other editors |
| [Configuration](configuration.md) | Environment variables, mounted folders, container paths, importing PNGs |
| [Development](development.md) | Running from source, tests, building the image, CI and releasing |

Quick start:

```bash
curl -fsSL https://raw.githubusercontent.com/Desvelao/pixel-forge-mcp/main/install.sh | sh -s -- --register --scaffold
```
