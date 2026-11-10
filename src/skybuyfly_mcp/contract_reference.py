# Copyright (c) 2026 PitchAI. Licensed under the MIT License (see LICENSE).
"""The reference tools' structured output: airports, display currencies and catalogue statistics."""

from __future__ import annotations

from skybuyfly_mcp import contract


class AirportEntry(contract.Contract):
    """One airport and the store domains of its shops."""

    code: str
    name: str
    city: str
    store_domains: list[str]


class AirportsResult(contract.Contract):
    """``list_airports``."""

    airports: list[AirportEntry]
    total: int


class CurrencyEntry(contract.Contract):
    """A display currency."""

    code: str
    name: str
    symbol: str


class CurrenciesResult(contract.Contract):
    """``list_currencies``."""

    currencies: list[CurrencyEntry]


class StatsResult(contract.Contract):
    """``get_catalogue_stats``."""

    total_products: int
    airports: int
    generated_at: contract.Timestamp
