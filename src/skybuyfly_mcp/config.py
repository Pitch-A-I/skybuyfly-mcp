# Copyright (c) 2026 PitchAI. Licensed under the MIT License (see LICENSE).
"""Environment configuration of the SkyBuyFly MCP server.

Every tunable has an explicit default; a value that does not parse (or is out of range) raises ``ConfigError`` at
startup instead of being replaced by its default. The two published tokens have no default: unset, their
``/.well-known`` route answers 404 (the explicit contract of a server not yet claimed by that directory).

``SKYBUYFLY_MCP_API_BASE_URL`` (``https://skybuyfly.pitchai.net``)
    The public SkyBuyFly JSON API the tools call (``/api/...``).
``SKYBUYFLY_MCP_PUBLIC_BASE_URL`` (``https://skybuyfly.pitchai.net``)
    The site every product, offer and image link points to.
``SKYBUYFLY_MCP_REVISION`` (unset)
    The git commit id of the running build, reported by ``/mcp/health``; the image sets it from
    its ``SKYBUYFLY_MCP_REVISION`` build argument. Unset (a local run): ``null``.
``SKYBUYFLY_MCP_CLIENT_CALLS_PER_MINUTE`` (300) / ``SKYBUYFLY_MCP_GLOBAL_CALLS_PER_MINUTE`` (1200)
    Tool calls per client (``X-Real-IP``, shared by many assistant users behind one egress address) and in total.
``SKYBUYFLY_MCP_LIVE_MAX_CONCURRENT`` (4) / ``SKYBUYFLY_MCP_LIVE_RUNS_PER_MINUTE`` (20)
    Live price streams open at once and started per minute by this process (inside the engine's own admission).
``SKYBUYFLY_MCP_LIVE_COALESCE_SECONDS`` (60)
    How long one live result answers every identical request (same product and currency).
``SKYBUYFLY_MCP_CACHE_SEARCH_SECONDS`` (60) / ``..._PRODUCT_SECONDS`` (120) / ``..._HISTORY_SECONDS`` (600) /
``..._REFERENCE_SECONDS`` (600) / ``SKYBUYFLY_MCP_CACHE_MAX_ENTRIES`` (2000)
    Response cache lifetimes (reference: airports, currencies, featured products, catalogue stats) and size.
``SKYBUYFLY_MCP_OPENAI_CHALLENGE_TOKEN`` / ``SKYBUYFLY_MCP_REGISTRY_AUTH`` (unset)
    The OpenAI apps domain challenge token and the MCP Registry HTTP auth record.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

from skybuyfly_mcp import __version__

if TYPE_CHECKING:
    from collections.abc import Mapping

_PREFIX = "SKYBUYFLY_MCP_"
_SITE = "https://skybuyfly.pitchai.net"
_REVISION = re.compile(r"^[0-9a-f]{7,40}$")


class ConfigError(ValueError):
    """An environment value that does not parse or is out of range."""


@dataclass(frozen=True, slots=True)
class CallLimits:
    """Tool calls per minute, per client address and across the process."""

    per_client_per_minute: int = 300
    global_per_minute: int = 1200


@dataclass(frozen=True, slots=True)
class LiveLimits:
    """This process's own bounds on live price streams."""

    max_concurrent: int = 4
    runs_per_minute: int = 20
    coalesce_seconds: float = 60.0


@dataclass(frozen=True, slots=True)
class CacheLifetimes:
    """Seconds each kind of upstream answer is reused, and the cache's entry bound."""

    search_seconds: float = 60.0
    product_seconds: float = 120.0
    history_seconds: float = 600.0
    reference_seconds: float = 600.0
    max_entries: int = 2000


@dataclass(frozen=True, slots=True)
class Published:
    """The records directories read from ``/.well-known/`` (``None``: not configured, the route answers 404)."""

    openai_challenge_token: str | None = None
    registry_auth: str | None = None


@dataclass(frozen=True, slots=True)
class Settings:
    """Validated server configuration (see the module docstring for each variable)."""

    api_base_url: str = _SITE
    public_base_url: str = _SITE
    revision: str | None = None
    calls: CallLimits = CallLimits()
    live: LiveLimits = LiveLimits()
    cache: CacheLifetimes = CacheLifetimes()
    published: Published = Published()

    @property
    def version(self) -> str:
        """The package's version (health, metrics, server info and User-Agent)."""
        return __version__

    @property
    def user_agent(self) -> str:
        """The User-Agent of every upstream request (never names a crawler: the live API refuses those)."""
        return f"SkyBuyFly-MCP/{self.version} (+{self.public_base_url}/mcp/docs)"

    @classmethod
    def from_environ(cls, environ: Mapping[str, str]) -> Settings:
        """Read and validate every ``SKYBUYFLY_MCP_*`` variable.

        A URL that is not an https (or local http) origin, a number that is not positive or a revision that is
        not a git commit id raises ``ConfigError`` (from ``_Environment``).

        Returns:
            The validated settings.
        """
        env = _Environment(environ)
        calls, live, cache = CallLimits(), LiveLimits(), CacheLifetimes()
        return cls(
            api_base_url=env.origin("API_BASE_URL"),
            public_base_url=env.origin("PUBLIC_BASE_URL"),
            revision=env.revision("REVISION"),
            calls=CallLimits(
                per_client_per_minute=env.count("CLIENT_CALLS_PER_MINUTE", calls.per_client_per_minute),
                global_per_minute=env.count("GLOBAL_CALLS_PER_MINUTE", calls.global_per_minute),
            ),
            live=LiveLimits(
                max_concurrent=env.count("LIVE_MAX_CONCURRENT", live.max_concurrent),
                runs_per_minute=env.count("LIVE_RUNS_PER_MINUTE", live.runs_per_minute),
                coalesce_seconds=env.seconds("LIVE_COALESCE_SECONDS", live.coalesce_seconds),
            ),
            cache=CacheLifetimes(
                search_seconds=env.seconds("CACHE_SEARCH_SECONDS", cache.search_seconds),
                product_seconds=env.seconds("CACHE_PRODUCT_SECONDS", cache.product_seconds),
                history_seconds=env.seconds("CACHE_HISTORY_SECONDS", cache.history_seconds),
                reference_seconds=env.seconds("CACHE_REFERENCE_SECONDS", cache.reference_seconds),
                max_entries=env.count("CACHE_MAX_ENTRIES", cache.max_entries),
            ),
            published=Published(env.token("OPENAI_CHALLENGE_TOKEN"), env.token("REGISTRY_AUTH")),
        )


@dataclass(frozen=True, slots=True)
class _Environment:
    """Typed reads of ``SKYBUYFLY_MCP_*`` variables."""

    environ: Mapping[str, str]

    def _raw(self, name: str) -> str | None:
        value = self.environ.get(_PREFIX + name)
        return None if value is None else value.strip()

    def origin(self, name: str) -> str:
        """Read an origin (``https://host``, or ``http://`` on 127.0.0.1 or localhost); SkyBuyFly's when unset.

        Returns:
            The origin without a trailing slash.

        Raises:
            ConfigError: The value is no such origin.
        """
        value = self._raw(name) or _SITE
        parts = urlsplit(value)
        local = parts.scheme == "http" and parts.hostname in {"127.0.0.1", "localhost"}
        if (parts.scheme != "https" and not local) or not parts.netloc or parts.path not in {"", "/"}:
            message = f"{_PREFIX}{name} must be an https origin without a path, got {value!r}"
            raise ConfigError(message)
        return f"{parts.scheme}://{parts.netloc}"

    def revision(self, name: str) -> str | None:
        """Read a git commit id (7 to 40 lowercase hex digits; unset or blank: none).

        Returns:
            The revision, or ``None``.

        Raises:
            ConfigError: The value is no commit id.
        """
        raw = self._raw(name)
        if not raw:
            return None
        if _REVISION.fullmatch(raw) is None:
            message = f"{_PREFIX}{name} must be a git commit id (7 to 40 lowercase hex digits), got {raw!r}"
            raise ConfigError(message)
        return raw

    def count(self, name: str, default: int) -> int:
        """Read a positive whole number (``default`` when unset).

        Returns:
            The number.

        Raises:
            ConfigError: The value is no positive whole number.
        """
        raw = self._raw(name)
        if raw is None:
            return default
        if not raw.isdigit() or int(raw) < 1:
            message = f"{_PREFIX}{name} must be a positive whole number, got {raw!r}"
            raise ConfigError(message)
        return int(raw)

    def seconds(self, name: str, default: float) -> float:
        """Read a positive number of seconds (``default`` when unset).

        Returns:
            The seconds.

        Raises:
            ConfigError: The value is no positive number.
        """
        raw = self._raw(name)
        if raw is None:
            return default
        if not raw.replace(".", "", 1).isdigit() or float(raw) <= 0:
            message = f"{_PREFIX}{name} must be a positive number of seconds, got {raw!r}"
            raise ConfigError(message)
        return float(raw)

    def token(self, name: str) -> str | None:
        """Read a published record (unset or blank: none).

        Returns:
            The record, or ``None``.
        """
        raw = self._raw(name)
        return raw or None
