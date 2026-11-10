# Copyright (c) 2026 PitchAI. Licensed under the MIT License (see LICENSE).
"""``python -m skybuyfly_mcp``: serve the MCP server with uvicorn on ``0.0.0.0:$PORT`` (8000), one worker.

nginx in front sets ``X-Real-IP`` and ``X-Forwarded-*`` (proxy headers are trusted). The upstream client's request
log (``httpx``) and the SDK's per-request lines (``mcp``) are kept at WARNING: they would log full query strings;
the access log is ``skybuyfly_mcp.access`` (one line per tool call).
"""

from __future__ import annotations

import ipaddress
import logging
import os

import uvicorn

from skybuyfly_mcp.config import ConfigError, Settings
from skybuyfly_mcp.server import build_app

DEFAULT_PORT = "8000"
MAX_PORT = 65535
ALL_INTERFACES = str(ipaddress.IPv4Address(0))
"""The server listens on every interface of its container; only the reverse proxy in front may reach the port."""


def main() -> None:
    """Validate the configuration and serve until stopped.

    Raises:
        ConfigError: ``PORT`` is not a port number (other settings: ``Settings.from_environ``).
    """
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    for noisy in ("httpx", "mcp"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    port = os.environ.get("PORT", DEFAULT_PORT).strip()
    if not port.isdigit() or not 0 < int(port) <= MAX_PORT:
        message = f"PORT must be a TCP port number, got {port!r}"
        raise ConfigError(message)
    app = build_app(Settings.from_environ(os.environ))
    uvicorn.run(
        app,
        host=ALL_INTERFACES,
        port=int(port),
        workers=1,
        proxy_headers=True,
        forwarded_allow_ips="*",
        access_log=False,
    )


if __name__ == "__main__":
    main()
