# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- Documentation: README and `docs/` now mention the MIT license.

## [0.1.0] - 2026-11-19

First release.

### Added
- MCP server `pixel-forge` (stdio) with 27 tools for making pixel art with a feedback loop: sprites,
  locked palettes (`db16`, `pico8`), drawing, finishing, `preview` / `validate`, and PNG / Godot export.
- Docker image `ghcr.io/desvelao/pixel-forge-mcp` (`linux/amd64`, `linux/arm64`) that runs as any host user
  via `docker run -u "$(id -u):$(id -g)"`; `docker-compose.yml` uses the published image.
- Reusable `docker-build.yml` workflow: build, smoke test and optional push to GHCR. Runs on pull requests
  and `main`, on demand, and via `workflow_call`.
- `release.yml` workflow: pushing a `vX.Y.Z` tag builds and pushes the image and creates a GitHub release.
- `install.sh` installer (`curl | sh`) with `--register`, `--scaffold`, `--bin-dir`, `--version` and `--uninstall`.
- `pixel-art` Claude Code skill and `STYLE_GUIDE.template.md`.
- Documentation in `docs/` (installation, usage, configuration, development).
- MIT license.

[Unreleased]: https://github.com/Desvelao/pixel-forge-mcp/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Desvelao/pixel-forge-mcp/releases/tag/v0.1.0
