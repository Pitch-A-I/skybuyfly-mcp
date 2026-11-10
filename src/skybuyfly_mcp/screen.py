# Copyright (c) 2026 PitchAI. Licensed under the MIT License (see LICENSE).
"""The restricted-goods screen: the one place the tobacco and nicotine predicate is applied.

Every product document (``ProductHead``: title, brand, category and, where the answer carries one, description) a
tool returns passes ``screened`` (lists: search pages, similar products, barcode, featured) or ``require_admitted``
(a product asked for by id: get_product, get_live_prices, get_price_history). A list answer whose screen withheld a
product says so in its ``notice`` (``RESTRICTED_NOTICE``). The number of products withheld is logged (no titles: the
log shows the screen works, not what was asked).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from mcp.server.mcpserver.exceptions import ToolError

from skybuyfly_mcp.restricted import is_restricted

if TYPE_CHECKING:
    from collections.abc import Iterable

    from skybuyfly_mcp.upstream_models import ProductHead

logger = logging.getLogger(__name__)
RESTRICTED_NOTICE: Final = "Tobacco and nicotine products are not shown."
"""A list answer's ``notice`` when the screen left a product out of it."""


class RestrictedProductError(ToolError):
    """A product the assistant may not show (tobacco or nicotine)."""

    def __init__(self) -> None:
        """Explain the policy without naming the product."""
        super().__init__("This product is not available through the SkyBuyFly assistant app (tobacco/nicotine).")


@dataclass(frozen=True, slots=True)
class Screened[T: ProductHead]:
    """The products that may be shown, in their order, and how many were withheld."""

    shown: list[T]
    withheld: int


def screened[T: ProductHead](products: Iterable[T]) -> Screened[T]:
    """Leave out every tobacco and nicotine product.

    Returns:
        The products that may be shown and the number withheld.
    """
    listed = list(products)
    shown = [
        product
        for product in listed
        if not is_restricted(product.title, product.brand, product.category, product.description)
    ]
    withheld = len(listed) - len(shown)
    if withheld:
        logger.info("event=restricted_withheld withheld=%d shown=%d", withheld, len(shown))
    return Screened(shown, withheld)


def notice(withheld: int) -> str | None:
    """Return a list answer's notice.

    Returns:
        ``RESTRICTED_NOTICE`` when the screen withheld a product of the answer, else ``None``.
    """
    return RESTRICTED_NOTICE if withheld else None


def require_admitted[T: ProductHead](product: T) -> T:
    """Return a single product that may be shown.

    Returns:
        The product.

    Raises:
        RestrictedProductError: It is tobacco or nicotine.
    """
    if screened([product]).withheld:
        raise RestrictedProductError
    return product
