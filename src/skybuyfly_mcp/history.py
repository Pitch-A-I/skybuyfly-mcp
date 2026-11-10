# Copyright (c) 2026 PitchAI. Licensed under the MIT License (see LICENSE).
"""Price history: a product's observed prices grouped per airport (``/api/mobile/product/{id}/snapshots``).

A snapshot names its airport in its location label ("Vienna International Airport (VIE) · Austria"); an online
shop serving several airports has none and is listed under its shop domain. A snapshot without a price or an
observation time is no point on a price chart and is left out. The snapshots route converts into the requested
currency and answers USD when it cannot: any other currency than requested is an error, never shown as if
converted.

The route answers at most the 50 newest observations across every airport (``catalogue.HISTORY_SNAPSHOTS``; it has
no parameter for older ones), and frequent live checks of a popular product repeat one price many times. So each
airport's points are its price changes: of every run of consecutive observations at one price, the first and the
last are kept (``change_points``), and the text says which dates the observations cover.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from skybuyfly_mcp.contract import AirportHistory, HistoryPoint, HistoryResult, Money
from skybuyfly_mcp.shaping import CurrencyMismatchError

if TYPE_CHECKING:
    from skybuyfly_mcp.links import Links
    from skybuyfly_mcp.upstream_models import HistoryResponse, HistorySnapshot, ProductHead

_LOCATION = re.compile(r"^(?P<name>.*?)\s*\((?P<code>[A-Z0-9]{3})\)")


@dataclass(frozen=True, slots=True)
class _Place:
    code: str | None
    name: str


def _place(snapshot: HistorySnapshot) -> _Place:
    match = _LOCATION.match(snapshot.location or "")
    if match is None:
        return _Place(None, snapshot.location or snapshot.domain)
    return _Place(match.group("code"), match.group("name"))


def change_points(points: list[HistoryPoint]) -> list[HistoryPoint]:
    """Keep the first and the last observation of each run of consecutive equal prices (points oldest first).

    Returns:
        The points where a price was first and last seen, oldest first.
    """
    kept: list[HistoryPoint] = []
    for index, point in enumerate(points):
        starts = index == 0 or points[index - 1].price != point.price
        ends = index == len(points) - 1 or points[index + 1].price != point.price
        if starts or ends:
            kept.append(point)
    return kept


def price_history(response: HistoryResponse, currency: str, product: ProductHead, links: Links) -> HistoryResult:
    """Group a product's snapshots per airport into its price changes, oldest first; lowest-priced airports first.

    Returns:
        The price history in ``currency``, headed by the product's title, brand, image and SkyBuyFly page.

    Raises:
        CurrencyMismatchError: The API answered prices in another currency.
    """
    points: dict[_Place, list[HistoryPoint]] = {}
    for snapshot in response.snapshots:
        if snapshot.price_unit != currency:
            raise CurrencyMismatchError(currency, snapshot.price_unit)
        if snapshot.price is None or snapshot.crawl_date is None:
            continue
        point = HistoryPoint(date=snapshot.crawl_date, price=Money(amount=snapshot.price, currency=currency))
        points.setdefault(_place(snapshot), []).append(point)
    airports: list[AirportHistory] = []
    for place, observed in points.items():
        ordered = change_points(sorted(observed, key=lambda point: point.date))
        lowest = min(ordered, key=lambda point: point.price.amount).price
        airports.append(
            AirportHistory(code=place.code, name=place.name, points=ordered, lowest=lowest, latest=ordered[-1].price),
        )
    airports.sort(key=lambda airport: (airport.lowest.amount, airport.code or "~"))
    return HistoryResult(
        product_id=response.product_id,
        title=product.title,
        brand=product.brand,
        image_url=links.image(product),
        skybuyfly_url=links.product(response.product_id),
        currency=currency,
        airports=airports,
    )
