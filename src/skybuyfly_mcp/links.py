# Copyright (c) 2026 PitchAI. Licensed under the MIT License (see LICENSE).
"""Own-domain links and images: no result ever carries a retailer URL.

A product links to its SkyBuyFly page (``/prod/{id}``), an offer to its SkyBuyFly deal page
(``/snapshots/{snapshot_id}``, which hands off to the retailer), both tagged ``utm_source=skybuyfly-mcp`` and
``utm_medium=ai-app``. An image on ``assets.pitchai.net`` or SkyBuyFly itself is kept; any other http(s) image is
served through SkyBuyFly's image proxy (``/api/mobile/image_proxy?url=``).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from urllib.parse import quote, urlsplit

if TYPE_CHECKING:
    from skybuyfly_mcp.upstream_models import ProductImages

ASSETS_ORIGIN = "https://assets.pitchai.net"
_ASSETS_HOST = "assets.pitchai.net"
_TRACKING = "utm_source=skybuyfly-mcp&utm_medium=ai-app"


@dataclass(frozen=True, slots=True)
class Links:
    """Builds every link of a result on ``public_base_url`` (``https://skybuyfly.pitchai.net``)."""

    public_base_url: str

    @property
    def public_host(self) -> str:
        """SkyBuyFly's host name."""
        return urlsplit(self.public_base_url).hostname or ""

    def product(self, product_id: str) -> str:
        """Return a product's SkyBuyFly page.

        Returns:
            ``/prod/{id}`` with the AI-app tracking parameters.
        """
        return f"{self.public_base_url}/prod/{quote(product_id, safe='')}?{_TRACKING}"

    def offer(self, snapshot_id: str) -> str:
        """Return an offer's SkyBuyFly deal page.

        Returns:
            ``/snapshots/{snapshot_id}`` with the AI-app tracking parameters.
        """
        return f"{self.public_base_url}/snapshots/{quote(snapshot_id, safe='')}?{_TRACKING}"

    def image(self, images: ProductImages) -> str | None:
        """Return a product's image on an own domain.

        The DuckDuckGo image wins when it is one of ours (``assets.pitchai.net``), then the canonical image, then
        ``image_url``, then a DuckDuckGo image elsewhere. A path is on SkyBuyFly; a value that is neither a path nor
        an http(s) URL (``data:``) is no image an assistant can show, so the next one is used.

        Returns:
            The first usable image URL (own domain or proxied), or ``None`` when the product has none.
        """
        ddg = (images.duckduckgo_img or "").strip()
        own_ddg = ddg if urlsplit(ddg).hostname == _ASSETS_HOST else ""
        candidates = (own_ddg, images.canonical_image or "", images.image_url or "", ddg)
        stripped = [candidate.strip() for candidate in candidates]
        present = [candidate for candidate in stripped if candidate]
        rewritten = [self._own_image(candidate) for candidate in present]
        usable = [url for url in rewritten if url is not None]
        return usable[0] if usable else None

    def _own_image(self, url: str) -> str | None:
        if url.startswith("/") and not url.startswith("//"):
            return f"{self.public_base_url}{url}"
        parts = urlsplit(url)
        if parts.scheme not in {"http", "https"} or not parts.hostname:
            return None
        if parts.scheme == "https" and parts.hostname in {self.public_host, _ASSETS_HOST}:
            return url
        return f"{self.public_base_url}/api/mobile/image_proxy?url={quote(url, safe='')}"
