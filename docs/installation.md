# Installation

pixel-forge-mcp is published as a Docker image: `ghcr.io/desvelao/pixel-forge-mcp`.
The server speaks MCP over **stdio**, so there is no port and no daemon: your MCP client starts the
container on demand and talks to it through stdin/stdout.

**Requirements:** Docker (daemon running, your user allowed to run `docker`) and
[Claude Code](https://claude.com/claude-code) (or any MCP client).

## Option 1: installer script (recommended)

Run it from the project that will use the sprites (for example your Godot project):

```bash
curl -fsSL https://raw.githubusercontent.com/Desvelao/pixel-forge-mcp/main/install.sh | sh
```

It checks Docker, pulls the image, and installs a `pixel-forge-mcp` launcher in `~/.local/bin`
(make sure that folder is on your `PATH`).

Do everything in one go (register with Claude Code and copy the skill + style guide into the project):

```bash
curl -fsSL https://raw.githubusercontent.com/Desvelao/pixel-forge-mcp/main/install.sh | sh -s -- --register --scaffold
```

| Option | Effect |
|---|---|
| `--register` | Runs `claude mcp add pixel-forge ...` for the current directory |
| `--scope local\|project\|user` | Scope used by `--register` (default `local`; `user` = every project) |
| `--scaffold` | Copies `.claude/skills/pixel-art/SKILL.md` and `STYLE_GUIDE.md` into the current directory (never overwrites) |
| `--bin-dir DIR` | Where to put the launcher (default `~/.local/bin`) |
| `--version TAG` | Image tag to install (default `latest`) |
| `--uninstall` | Removes the launcher |

Pin a version for reproducible installs by using the tag in the URL and the env var:

```bash
curl -fsSL https://raw.githubusercontent.com/Desvelao/pixel-forge-mcp/v0.1.0/install.sh | PIXEL_FORGE_VERSION=v0.1.0 sh
```

Prefer to read it first? `curl -fsSL <url> -o install.sh`, inspect, then `sh install.sh`.

## Option 2: plain `docker run`

No installer needed. Pull the image and register it directly (use absolute paths):

```bash
docker pull ghcr.io/desvelao/pixel-forge-mcp:latest
mkdir -p art/work assets/sprites

claude mcp add pixel-forge -- docker run -i --rm -u "$(id -u):$(id -g)" \
  -v "$PWD/art/work:/work" \
  -v "$PWD/assets/sprites:/export" \
  ghcr.io/desvelao/pixel-forge-mcp:latest
```

- `-i` is required (stdio), do **not** use `-t`.
- `-u "$(id -u):$(id -g)"` makes the files the server creates belong to you, so Pixelorama can save over them.
- `/work` holds one `<name>.png` per sprite; `/export` receives `export_png` / `export_godot` output.
- To use `load_png`, also mount a folder read-only: `-v "$PWD/import:/import:ro"`.

Other MCP clients use the same command in their config, for example:

```json
{
  "mcpServers": {
    "pixel-forge": {
      "command": "docker",
      "args": ["run", "-i", "--rm", "-u", "1000:1000",
               "-v", "/abs/path/art/work:/work",
               "-v", "/abs/path/assets/sprites:/export",
               "ghcr.io/desvelao/pixel-forge-mcp:latest"]
    }
  }
}
```

## Option 3: docker compose

```bash
git clone https://github.com/Desvelao/pixel-forge-mcp.git
claude mcp add pixel-forge \
  -e WORK_DIR=$PWD/art/work -e EXPORT_DIR=$PWD/assets/sprites \
  -- docker compose -f /abs/path/to/pixel-forge-mcp/docker-compose.yml run --rm -T pixel-forge
```

Compose uses the published image; run `docker compose build` to use a local build instead.

## Option 4: from source (no Docker)

```bash
git clone https://github.com/Desvelao/pixel-forge-mcp.git
cd pixel-forge-mcp
pip install -r requirements.txt

claude mcp add pixel-forge \
  -e PIXEL_FORGE_DIR=$PWD/art/work -e PIXEL_FORGE_EXPORT=$PWD/assets/sprites \
  -- python /abs/path/to/pixel-forge-mcp/server.py
```

## Skill and style guide

Copy these into your project so Claude knows the workflow and your art direction
(`--scaffold` does this for you):

- `.claude/skills/pixel-art/SKILL.md`
- `STYLE_GUIDE.template.md` as `STYLE_GUIDE.md` (edit sizes, palette, mood, light direction)

## Verify

Start a **fresh** `claude` session in the project and run `/mcp`: `pixel-forge` should be connected.
Then ask Claude to make a 16x16 sprite; a PNG appears in your work folder.

## Upgrade and uninstall

```bash
docker pull ghcr.io/desvelao/pixel-forge-mcp:latest   # upgrade (or re-run the installer)
sh install.sh --uninstall                             # remove the launcher
claude mcp remove pixel-forge                         # unregister
docker rmi ghcr.io/desvelao/pixel-forge-mcp:latest    # remove the image
```

## Troubleshooting

- **`/mcp` shows it failed**: run the launcher by hand (`pixel-forge-mcp`); it should wait silently for input.
  Common causes: Docker daemon not running, user not in the `docker` group, image not pulled.
- **`docker pull` asks for login / is denied**: the GHCR package must be public.
- **Permission denied writing sprites**: you started the container without `-u "$(id -u):$(id -g)"`.
- **Edits made in Pixelorama are not seen**: the work folder must be a bind mount (not a named volume)
  and you must export PNG over the same file.
- **Tool replies show `/work` paths**: expected; those are container paths for your work folder.
