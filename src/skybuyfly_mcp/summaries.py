# Copyright (c) 2026 PitchAI. Licensed under the MIT License (see LICENSE).
"""The short text each tool result carries for the model (hosts with the widget show the structured result)."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime

    from skybuyfly_mcp.contract import (
        AirportHistory,
        HistoryResult,
        LiveResult,
        Money,
        Offer,
        ProductCard,
        ProductResult,
    )
    from skybuyfly_mcp.contract_reference import AirportsResult, CurrenciesResult, StatsResult

_LISTED = 10
_LIVE_HINT = (
    "Prices are stored observations; call get_live_prices with a product_id to confirm them at the airports now."
)
_LIVE_LABEL = {
    "live_confirmed": "live-confirmed",
    "stored": "stored,",
    "live_check_failed": "stored (live check failed),",
    "live_timeout": "stored (the shop did not answer in time),",
    "live_blocked": "stored (no live check possible),",
}


def _money(money: Money | None) -> str:
    return "no price" if money is None else f"{money.currency} {money.amount:,.2f}"


def _day(moment: datetime | None) -> str:
    return "unknown date" if moment is None else f"{moment.day} {moment:%b %Y}"


def _card_line(card: ProductCard) -> str:
    """Return a card's line: its lowest price, where (an airport, or an online shop) and when, and its airports.

    Returns:
        ``- <title> [<brand>]: from <price> at <airport> (<n> airport(s), seen <date>). product_id <id>, <link>``.
    """
    at = (
        f"at {card.airports[0].code}"
        if card.lowest_price_scope == "airport" and card.airports
        else "at an online shop serving several airports"
    )
    where = (
        f"from {_money(card.lowest_price)} {at} ({len(card.airports)} airport(s), seen {_day(card.price_observed_at)})"
        if card.lowest_price is not None
        else "no comparable price"
    )
    brand = f" [{card.brand}]" if card.brand else ""
    size = f" ({card.size})" if card.size else ""
    return f"- {card.title}{size}{brand}: {where}. product_id {card.product_id}, {card.skybuyfly_url}"


def _place(offer: Offer) -> str:
    if offer.scope == "online_shop":
        return f"the {offer.retailer} (multiple airports)"
    return f"{offer.airport_code} {offer.airport_name}"


def _state(offer: Offer) -> str:
    when = f"{offer.observed_at:%H:%M} UTC" if offer.source == "live" else f"seen {_day(offer.observed_at)}"
    return f"{_LIVE_LABEL[offer.status]} {when}"


def _offer_line(offer: Offer) -> str:
    return f"- {_place(offer)}: {_money(offer.display_price)} ({_state(offer)}) {offer.skybuyfly_url}"


def _cheapest_line(offer: Offer) -> str:
    """Return where the lowest price is: an airport, or a retailer's online shop serving several airports.

    Returns:
        ``Cheapest: from <price> at <place>; <state>. <link>``.
    """
    return f"Cheapest: from {_money(offer.display_price)} at {_place(offer)}; {_state(offer)}. {offer.skybuyfly_url}"


def product_list_summary(
    products: list[ProductCard],
    subject: str,
    notice: str | None,
    *,
    more: bool = False,
    nothing: str | None = None,
) -> str:
    """Return the text of a product list (``subject``: "for 'chanel'", "for barcode 3145891165203", ...).

    Returns:
        One line per product (at most ten), or ``nothing`` (default "No products found <subject>.") when there is
        none, the restricted-goods notice when set, and how to continue (``more``: a next page exists).
    """
    empty = f"No products found {subject}." if nothing is None else nothing
    lines = [f"Found {len(products)} product(s) {subject}:" if products else empty]
    lines.extend(_card_line(card) for card in products[:_LISTED])
    if notice:
        lines.append(notice)
    if products:
        lines.append(_LIVE_HINT)
    if more:
        lines.append("More results: call search_products again with the same query and cursor=next_cursor.")
    return "\n".join(lines)


def product_summary(result: ProductResult) -> str:
    """Return the text of a product with its offers.

    Returns:
        The product, then one line per offer, cheapest first, and where the lowest price is.
    """
    product = result.product
    size = f" ({product.size})" if product.size else ""
    lines = [f"{product.title}{size}, {len(result.offers)} offer(s) ({product.skybuyfly_url}):"]
    lines.extend(_offer_line(offer) for offer in result.offers[:_LISTED])
    priced = [offer for offer in result.offers if offer.display_price is not None]
    if priced:
        lines.append(_cheapest_line(priced[0]))
    lines.append(_LIVE_HINT)
    return "\n".join(lines)


def live_summary(result: LiveResult) -> str:
    """Return the text of a live price check.

    Returns:
        How the check went, then one line per offer, cheapest first.
    """
    title = result.product.title
    if result.live_status == "rate_limited":
        wait = f" in {result.retry_after_seconds} s" if result.retry_after_seconds else " shortly"
        return f"Live price checks are busy right now; try again{wait}, or use get_product for the stored prices."
    if result.live_status == "no_offers":
        return f"SkyBuyFly knows no airport offer of {title} to check yet; it is now searching the shops for it."
    summary = result.summary
    head = {
        "complete": f"Live check of {title}: {summary.live_confirmed} of {len(result.offers)} offer(s) confirmed now.",
        "partial": f"Live check of {title}: {summary.live_confirmed} of {len(result.offers)} offer(s) confirmed; "
        "the others show their stored price.",
        "unavailable": f"Live checks are unavailable now ({result.reason}); stored prices of {title}:",
    }[result.live_status]
    lines = [head]
    lines.extend(_offer_line(offer) for offer in result.offers[:_LISTED])
    if result.cheapest is not None:
        lines.append(_cheapest_line(result.cheapest))
    return "\n".join(lines)


def _history_line(airport: AirportHistory) -> str:
    place = f"{airport.code} {airport.name}" if airport.code else f"the {airport.name} online shop"
    latest = f"latest {_money(airport.latest)} ({_day(airport.points[-1].date)}"
    return f"- {place}: lowest {_money(airport.lowest)}, {latest}, {len(airport.points)} point(s))"


def history_summary(result: HistoryResult) -> str:
    """Return the text of a price history: the dates it covers, then each airport's lowest and latest price.

    Returns:
        The covered dates (SkyBuyFly answers its 50 newest observations) and one line per airport.
    """
    if not result.airports:
        return f"SkyBuyFly has no observed prices of {result.title} yet."
    dates = [point.date for airport in result.airports for point in airport.points]
    head = (
        f"Observed prices of {result.title} per airport (in {result.currency}). SkyBuyFly's most recent observations "
        f"cover {_day(min(dates))} to {_day(max(dates))}; older prices are not available here. Each airport lists "
        "its price changes (the first and last observation of each price):"
    )
    lines = [head]
    lines.extend(_history_line(airport) for airport in result.airports)
    lines.append(f"SkyBuyFly page: {result.skybuyfly_url}")
    return "\n".join(lines)


def airports_summary(result: AirportsResult) -> str:
    """Return the text of an airport list.

    Returns:
        The airports' codes and names.
    """
    listed = ", ".join(f"{airport.code} ({airport.city})" for airport in result.airports)
    return f"{result.total} airport(s): {listed}." if result.airports else "No airport matches."


def currencies_summary(result: CurrenciesResult) -> str:
    """Return the text of the currency list.

    Returns:
        The currency codes.
    """
    codes = [entry.code for entry in result.currencies]
    return f"{len(codes)} display currencies: {', '.join(codes)}."


def stats_summary(result: StatsResult) -> str:
    """Return the text of the catalogue statistics.

    Returns:
        The catalogue's size, airports and date.
    """
    return (
        f"SkyBuyFly compares {result.total_products:,} products at {result.airports} airports "
        f"(as of {result.generated_at:%Y-%m-%d %H:%M} UTC)."
    )
