# Copyright (c) 2026 PitchAI. Licensed under the MIT License (see LICENSE).
"""Readable shop names of offers (``Offer.retailer``); the store domain itself stays in ``Offer.retailer_domain``.

The API names a product's shops in the labels of its stored offers (``/api/mobile/product/{id}``,
``retailer_name``): an airport offer is "<airport location> — <shop>" ("Vienna International Airport (VIE) · Austria
— Heinemann"), a retailer-wide online listing "<shop> (multiple locations)" ("Heinemann Duty Free (multiple
locations)"). The rule, per store domain of one product (``ShopNames``):

1. the shop an airport offer's label names ("Heinemann");
2. else the shop a listing label names, without " (multiple locations)" ("Heinemann Duty Free");
3. else the domain made readable (``readable_domain``): "www." and the public suffix dropped, dots and hyphens as
   spaces, each word capitalised ("www.dublinandcorkdutyfree.ie" -> "Dublinandcorkdutyfree", "www.heinemann-shop.com"
   -> "Heinemann Shop").

An airport offer's retailer is the shop ("Heinemann"); an online-shop offer's is "<shop> online shop" ("Heinemann
online shop"). The live stream names only the domain of an offer: its offers take the names the product's stored
offers give, so the product and live views agree.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from skybuyfly_mcp.contract import OfferScope
    from skybuyfly_mcp.upstream_models import RetailerOffer

_SHOP_SEPARATOR: Final = " — "
_LISTING_SUFFIX: Final = " (multiple locations)"
_HOST_PREFIX: Final = "www."
_TWO_PART_SUFFIXES = frozenset({"co.uk", "co.in", "co.jp", "co.kr", "co.nz", "com.au", "com.cn", "com.my", "com.sg"})


def readable_domain(domain: str) -> str:
    """Return a store domain as a name (rule 3 of the module docstring).

    Returns:
        The domain without "www." and its public suffix, words capitalised ("www.heinemann-shop.com" -> "Heinemann
        Shop").
    """
    host = domain.strip().casefold().removeprefix(_HOST_PREFIX)
    labels = host.split(".")
    suffix_labels = 2 if ".".join(labels[-2:]) in _TWO_PART_SUFFIXES else 1
    kept = labels[:-suffix_labels] if len(labels) > suffix_labels else labels
    words = " ".join(kept).replace("-", " ").split()
    return " ".join(word.capitalize() for word in words)


def _labelled_shop(label: str) -> tuple[int, str] | None:
    """Return the shop a stored offer's label names, with its rule (1: an airport offer's, 2: a listing's).

    Returns:
        ``(rule, shop)``, or ``None`` when the label names no shop.
    """
    if _SHOP_SEPARATOR in label:
        return 1, label.rsplit(_SHOP_SEPARATOR, 1)[1].strip()
    if label.endswith(_LISTING_SUFFIX):
        return 2, label.removesuffix(_LISTING_SUFFIX).strip()
    return None


@dataclass(frozen=True, slots=True)
class ShopNames:
    """The shop name of each store domain of one product (the module docstring's rule)."""

    by_domain: Mapping[str, str]

    @classmethod
    def from_offers(cls, offers: Iterable[RetailerOffer]) -> ShopNames:
        """Name each store domain by the labels of a product's stored offers (rules 1 and 2).

        Returns:
            The names.
        """
        best: dict[str, tuple[int, str]] = {}
        for offer in offers:
            named = _labelled_shop(offer.retailer_name or "")
            known = best.get(offer.source_domain)
            if named is not None and named[1] and (known is None or named[0] < known[0]):
                best[offer.source_domain] = named
        return cls({domain: name for domain, (_, name) in best.items()})

    def retailer(self, domain: str, scope: OfferScope) -> str:
        """Return an offer's retailer: its shop, or "<shop> online shop" for a retailer-wide online listing.

        Returns:
            The readable retailer name.
        """
        shop = self.by_domain.get(domain) or readable_domain(domain)
        return f"{shop} online shop" if scope == "online_shop" else shop
