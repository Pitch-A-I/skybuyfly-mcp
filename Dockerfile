# SkyBuyFly MCP server: a read-only facade over the public SkyBuyFly JSON API.
# Build context: this directory. The image runs with a read-only root filesystem
# (`docker run --read-only --tmpfs /tmp ...`): it writes nothing outside /tmp.
# Written for the classic builder as well as BuildKit: no heredocs, no --chmod.

# uv only resolves and installs; it is not in the runtime image.
FROM ghcr.io/astral-sh/uv:0.10.0@sha256:78a7ff97cd27b7124a5f3c2aefe146170793c56a1e03321dd31a289f6d82a04f AS uv

FROM python:3.12.16-slim-bookworm@sha256:935c3c5b12357a7e10caa9c1e6ca5692344d97cf229832ef584be2cec9fc03df AS build
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PYTHON=/usr/local/bin/python3.12 \
    UV_PROJECT_ENVIRONMENT=/app/.venv
WORKDIR /build
# Dependencies first (exactly uv.lock), so a source-only change reuses this layer.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
# The package itself, as a regular (non-editable) install: the runtime image needs no source tree.
COPY src ./src
RUN uv sync --frozen --no-dev --no-editable

FROM python:3.12.16-slim-bookworm@sha256:935c3c5b12357a7e10caa9c1e6ca5692344d97cf229832ef584be2cec9fc03df
# The git commit the image is built from (`--build-arg SKYBUYFLY_MCP_REVISION=<commit>`); /mcp/health reports it.
# Without the build argument it is empty, which the server reads as "no revision" (health answers null).
ARG SKYBUYFLY_MCP_REVISION=
LABEL org.opencontainers.image.title="skybuyfly-mcp" \
      org.opencontainers.image.description="SkyBuyFly public MCP server (read-only price comparison facade)" \
      org.opencontainers.image.vendor="PitchAI" \
      org.opencontainers.image.revision="${SKYBUYFLY_MCP_REVISION}" \
      com.pitchai.aipc.service="skybuyfly-mcp"
RUN groupadd --system --gid 21008 skybuyfly-mcp \
 && useradd --system --uid 21008 --gid 21008 --no-create-home --home-dir /nonexistent \
            --shell /usr/sbin/nologin skybuyfly-mcp
COPY --from=build /app/.venv /app/.venv
# Bytecode is compiled at build time; the root filesystem is read-only at run time.
ENV PATH=/app/.venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HOME=/tmp \
    SKYBUYFLY_MCP_REVISION=${SKYBUYFLY_MCP_REVISION}
USER 21008:21008
WORKDIR /tmp
EXPOSE 8000
# The process's own health route; the slim image has no curl. The port listens 2-8 s after the start (importing
# the MCP SDK and pydantic building its schemas on one CPU; nothing is fetched at startup): during the 30 s start
# period a failed probe does not count and probes run every second, so the container is healthy within about a
# second of listening. Needs Docker Engine 25+ for --start-interval.
HEALTHCHECK --interval=10s --timeout=3s --start-period=30s --start-interval=1s --retries=3 \
  CMD ["/app/.venv/bin/python", "-c", "import json, sys, urllib.request; body = json.load(urllib.request.urlopen('http://127.0.0.1:8000/mcp/health', timeout=2)); sys.exit(0 if body.get('service') == 'skybuyfly-mcp' and body.get('status') == 'ok' else 1)"]
ENTRYPOINT ["/app/.venv/bin/python", "-m", "skybuyfly_mcp"]
