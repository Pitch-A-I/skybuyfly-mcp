# Copyright (c) 2026 PitchAI. Licensed under the MIT License (see LICENSE).
"""The tools' input fields: their bounds (validated before a tool runs) and their descriptions for the model.

Each description states the field's format; an argument outside it is answered with that description
(``arguments``).
"""

from __future__ import annotations

from typing import Annotated

from pydantic import AfterValidator, Field

DEFAULT_CURRENCY = "USD"
DEFAULT_LIMIT = 8
DEFAULT_WAIT_SECONDS = 12

Query = Annotated[
    str,
    Field(
        min_length=1,
        max_length=200,
        description="1-200 characters: what the traveller is looking for, a product name, brand, category or a mix of "
        "them, e.g. 'Chanel Coco Mademoiselle 100 ml', 'Lagavulin 16', 'sunscreen'.",
    ),
]
IataCode = Annotated[str, Field(pattern=r"^[A-Za-z]{3}$", description="An airport's 3-letter IATA code, e.g. VIE.")]
Airports = Annotated[
    Annotated[list[IataCode], Field(max_length=10)] | None,
    Field(
        description="Up to 10 airport IATA codes, e.g. ['VIE', 'BER']: only products the catalogue lists at every one "
        "of these airports and with a current price at one of them at least; each card then shows the current prices "
        "at these airports only (an airport without a current price is left off the card). Leave it out, or pass [], "
        "to search every airport. list_airports has the airports SkyBuyFly compares.",
    ),
]
Currency = Annotated[
    str,
    Field(
        pattern=r"^[A-Za-z]{3}$",
        description="A 3-letter ISO 4217 currency code, e.g. EUR (any case; default USD), that every price is shown "
        "in; list_currencies has every one.",
    ),
    AfterValidator(str.upper),
]
"""A currency code as the client writes it, read in capitals ("eur" is EUR)."""
Limit = Annotated[int, Field(ge=1, le=20, description="How many products to return: a whole number from 1 to 20.")]
Cursor = Annotated[
    str | None,
    Field(
        max_length=4096,
        description="The next_cursor of the previous answer, unchanged, to get the next page of the same search.",
    ),
]
PRODUCT_ID_PATTERN = r"^(?:[0-9a-f]{32}|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$"
"""The two forms the API writes product ids in: 32 hex characters, or a dashed UUID (passed on unchanged)."""
ProductId = Annotated[
    str,
    Field(
        pattern=PRODUCT_ID_PATTERN,
        description="A SkyBuyFly product_id exactly as search_products, lookup_barcode or get_featured_products "
        "answered it: 32 lowercase hex characters or a dashed UUID.",
    ),
]
Barcode = Annotated[
    str,
    Field(
        pattern=r"^\d{8,14}$",
        description="The barcode's 8 to 14 digits (EAN-8, UPC-A, EAN-13 or GTIN-14), e.g. 3145891165203.",
    ),
]
WaitSeconds = Annotated[
    int,
    Field(
        ge=5,
        le=20,
        description="Seconds to wait for the airports' shops to answer: a whole number from 5 to 20 (default 12); "
        "offers not confirmed by then are returned with their stored price.",
    ),
]
AirportFilter = Annotated[
    str | None,
    Field(
        max_length=100,
        description="Up to 100 characters: only airports whose IATA code, name or city contains this text, e.g. "
        "'London'.",
    ),
]
