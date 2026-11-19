# Configuration

## Environment variables (inside the container or when running from source)

| Variable | Default | Meaning |
|---|---|---|
| `PIXEL_FORGE_DIR` | `./pixel-work` (`/work` in the image) | Work folder, one `<name>.png` per sprite |
| `PIXEL_FORGE_EXPORT` | `<PIXEL_FORGE_DIR>/export` (`/export` in the image) | Where `export_png` / `export_godot` write |

In Docker you normally do **not** set these; you choose which host folders are mounted instead.

## Mounts

| Container path | Purpose | Mode |
|---|---|---|
| `/work` | Sprite PNGs. Open them in Pixelorama; the server reloads files changed on disk | read-write |
| `/export` | Exported sheets and Godot `.tres` files. Point it at your Godot `assets/sprites` | read-write |
| `/import` (optional) | Source PNGs for `load_png` | read-only |

Use **bind mounts**, not named volumes, so edits made on the host are visible to the server.
Run the container with `-u "$(id -u):$(id -g)"` so file ownership matches your user.

## Launcher (installed by `install.sh`)

`pixel-forge-mcp` reads these host-side variables:

| Variable | Default |
|---|---|
| `PIXEL_FORGE_DIR` | `$PWD/art/work` |
| `PIXEL_FORGE_EXPORT` | `$PWD/assets/sprites` |
| `PIXEL_FORGE_IMPORT` | unset (no `/import` mount) |

`install.sh --register` also passes the first two to `claude mcp add` as absolute paths for the project.

## docker compose variables

`WORK_DIR`, `EXPORT_DIR`, `IMPORT_DIR` (host folders), `PIXEL_FORGE_TAG` (image tag, default `latest`),
`UID` / `GID` (default 1000).

## Limits

Maximum canvas 256x256. Colors are `#rrggbb`, a palette index like `p6`, or `clear`;
semi-transparency is rejected on purpose.
