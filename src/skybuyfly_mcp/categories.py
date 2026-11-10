# Copyright (c) 2026 PitchAI. Licensed under the MIT License (see LICENSE).
"""The popular categories ``get_featured_products`` shows: the home screen's list, cleaned of shop-feed artefacts.

The home screen counts the catalogue's raw category labels, which mix real categories with labels that shop feeds
use for other things (recorded 9 Nov 2026: "Athens Duty Free EN", "Arlanda T5F EN Duty Free", "Brands", and
"champagne" in lower case next to "Champagne & Wine"). The rule, applied in this order:

1. Leave out a label that names a shop or site (it contains "duty free", in any case), the label "Brands" (a
   navigation entry, not a category), and a label whose last word is a language code (``EN``, ``NL``: a shop's
   per-language feed name).
2. Merge labels that are equal ignoring case, adding up their counts; the merged label is spelt as its most
   counted spelling, with a first capital letter when that spelling has none ("champagne" -> "Champagne").
3. Sort by count, highest first (ties keep the home screen's order).

Nothing is renamed beyond that capital letter and no category is added: "Champagne" and "Champagne & Wine" stay
two categories, as the catalogue counts them.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from skybuyfly_mcp.contract import PopularCategory

if TYPE_CHECKING:
    from collections.abc import Iterable

    from skybuyfly_mcp.upstream_browse import HomeCategory

_SHOP_MARKER = "duty free"
_NAVIGATION = frozenset({"brands"})
_LANGUAGE_CODES = frozenset({"EN", "NL"})


def is_category(name: str) -> bool:
    """Tell whether a home screen label is a product category (rule 1 of the module docstring).

    Returns:
        ``False`` for a shop or site name, ``Brands`` and a language-suffixed feed name.
    """
    words, folded = name.split(), name.casefold()
    if not words or _SHOP_MARKER in folded or folded in _NAVIGATION:
        return False
    return words[-1] not in _LANGUAGE_CODES


def _spelling(spellings: dict[str, int]) -> str:
    """Return the most counted spelling (the first seen on a tie), with a first capital letter.

    Returns:
        The label to show.
    """
    best = max(spellings, key=lambda spelling: spellings[spelling])
    return best if best[:1].isupper() else best[:1].upper() + best[1:]


def popular_categories(categories: Iterable[HomeCategory]) -> list[PopularCategory]:
    """Clean the home screen's popular categories (the module docstring's rule).

    Returns:
        The categories with their product counts, most products first.
    """
    merged: dict[str, dict[str, int]] = {}
    for category in categories:
        name = " ".join(category.name.split())
        if is_category(name):
            spellings = merged.setdefault(name.casefold(), {})
            spellings[name] = spellings.get(name, 0) + category.count
    spelling_counts = merged.values()
    shown = [PopularCategory(name=_spelling(spellings), count=sum(spellings.values())) for spellings in spelling_counts]
    return sorted(shown, key=lambda category: -category.count)
