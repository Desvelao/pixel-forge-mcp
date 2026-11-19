FROM python:3.12-slim

LABEL org.opencontainers.image.source="https://github.com/Desvelao/pixel-forge-mcp" \
      org.opencontainers.image.description="pixel-forge: stdio MCP server for making pixel art with Claude Code" \
      org.opencontainers.image.licenses="MIT"

# HOME=/tmp so any UID passed with `docker run -u UID:GID` works without a home dir.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HOME=/tmp \
    PIXEL_FORGE_DIR=/work \
    PIXEL_FORGE_EXPORT=/export

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py test_smoke.py ./

# World-writable fallbacks; in normal use /work and /export are bind-mounted from the host.
RUN mkdir -p /work /export && chmod 777 /work /export

# Default non-root user; override with `-u "$(id -u):$(id -g)"` so files match your host user.
USER 1000:1000

# stdio MCP server: no port. Run with stdin open and no TTY (`docker run -i`).
ENTRYPOINT ["python", "/app/server.py"]
