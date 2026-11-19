# Development

## Run from source

```bash
git clone https://github.com/Desvelao/pixel-forge-mcp.git
cd pixel-forge-mcp
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt        # mcp>=1.2 (1.x and 2.x supported), pillow, numpy
python test_smoke.py                   # starts server.py over stdio and calls the tools
```

Point Claude Code at your working copy:

```bash
claude mcp add pixel-forge-dev \
  -e PIXEL_FORGE_DIR=$PWD/pixel-work -e PIXEL_FORGE_EXPORT=$PWD/export \
  -- $PWD/.venv/bin/python $PWD/server.py
```

## Build and test the image locally

```bash
docker build -t ghcr.io/desvelao/pixel-forge-mcp:latest .
docker run --rm -u 12345:12345 --entrypoint python ghcr.io/desvelao/pixel-forge-mcp:latest test_smoke.py
```

Running the smoke test as an arbitrary UID checks the image works for any host user.

## Repository layout

| Path | What |
|---|---|
| `server.py` | The MCP server (all tools) |
| `test_smoke.py` | End-to-end test over stdio |
| `Dockerfile`, `docker-compose.yml` | Image and compose setup |
| `install.sh` | `curl \| sh` installer and launcher generator |
| `.claude/skills/pixel-art/SKILL.md` | Skill that teaches Claude the loop (copied into user projects) |
| `STYLE_GUIDE.template.md` | Style guide template |
| `.github/workflows/` | CI (`docker-build.yml`) and release (`release.yml`) |

## CI: `docker-build.yml`

Builds the image, runs the smoke test (as UID 12345) and, when asked, pushes multi-arch
(`linux/amd64`, `linux/arm64`) to `ghcr.io/desvelao/pixel-forge-mcp`.

- **Pull requests**: build + smoke test, no push.
- **Push to `main`**: build + smoke test, pushes `latest` and `sha-<short>`.
- **On demand**: Actions tab > *Docker build* > *Run workflow* (inputs: `push`, `tag`, `platforms`).
- **Reusable**: call it from another workflow:

```yaml
jobs:
  docker:
    uses: ./.github/workflows/docker-build.yml        # or Desvelao/pixel-forge-mcp/.github/workflows/docker-build.yml@main
    with:
      push: true
      tag: v1.2.3
    permissions:
      contents: read
      packages: write
```

Outputs: `image`, `digest`, `version`.

## Releasing

1. Make sure `main` is green.
2. Move the `[Unreleased]` entries in `CHANGELOG.md` under a new `## [X.Y.Z] - date` heading and commit.
3. Tag and push:

```bash
git tag v0.1.0
git push origin v0.1.0
```

`release.yml` validates the tag (`vX.Y.Z` or `vX.Y.Z-rc.1`), builds and pushes the image
(`v0.1.0`, `0.1.0`, `0.1`, `latest`; pre-releases get no `latest`/`major.minor` tags), then creates a
GitHub release with generated notes, install instructions and the assets `install.sh`,
`docker-compose.yml`, `SKILL.md`, `STYLE_GUIDE.template.md`. Tags containing `-` are marked pre-release.

First release only: after the first push, set the GHCR package visibility to **public**
(GitHub > your profile > Packages > pixel-forge-mcp > Package settings), or `docker pull` will need a login.

## Changing the installer

`install.sh` is POSIX `sh`, wrapped in `main()` so a truncated download never runs partially. Lint it with
`shellcheck install.sh`. To test without publishing, stub `docker pull` and run it with `--bin-dir` pointing at
a temp folder.

## License and contributions

The project is MIT licensed ([LICENSE](../LICENSE)). By submitting a contribution you agree to license it under the
same terms. The Docker image carries the `org.opencontainers.image.licenses=MIT` label (set in the `Dockerfile`),
so keep it in sync if the license ever changes.
