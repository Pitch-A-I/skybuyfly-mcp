# Copyright (c) 2026 PitchAI. Licensed under the MIT License (see LICENSE).
"""Reference data the tools validate against: the airports (IATA code to store domains) and display currencies.

Tools take IATA codes (``VIE``, case-insensitive); the search API takes store domains (``heinemann:VIE``), from
``/api/mobile/airports``. Several airports can share one store (Dublin and Cork); an airport has every store
domain listed for it. An unknown code or currency is a tool error naming it.

``/api/mobile/currencies`` still lists currencies ISO 4217 has withdrawn (EEK, HRK, LTL, ZMK and BGN were recorded on
9 Nov 2026). ``WITHDRAWN_CURRENCIES`` is the one list of them: they are not display currencies here (left out of
``list_currencies``) and a price request in one is refused, naming its successor.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from mcp.server.mcpserver.exceptions import ToolError

from skybuyfly_mcp.contract_reference import AirportEntry, CurrencyEntry

if TYPE_CHECKING:
    from collections.abc import Iterable

    from skybuyfly_mcp.upstream_models import AirportsResponse, CurrenciesResponse

_CODE_SUFFIX = re.compile(r"\s*\([A-Z0-9]{3}\)\s*$")
WITHDRAWN_CURRENCIES: dict[str, str] = {
    "BGN": "EUR",
    "CYP": "EUR",
    "EEK": "EUR",
    "HRK": "EUR",
    "LTL": "EUR",
    "LVL": "EUR",
    "MTL": "EUR",
    "SIT": "EUR",
    "SKK": "EUR",
    "ZMK": "ZMW",
}
"""ISO 4217 codes withdrawn from circulation, each with the currency that replaced it."""


class UnknownAirportError(ToolError):
    """Airport codes SkyBuyFly does not compare."""

    def __init__(self, codes: Iterable[str]) -> None:
        """Name every unknown code."""
        named = ", ".join(codes)
        super().__init__(
            f"Unknown airport code(s): {named}. SkyBuyFly compares the duty-free shops of the airports that "
            "list_airports returns; use their IATA codes.",
        )


class WithdrawnCurrencyError(ToolError):
    """A currency that is no longer in circulation."""

    def __init__(self, code: str) -> None:
        """Name the currency and its successor."""
        successor = WITHDRAWN_CURRENCIES[code]
        super().__init__(
            f"{code} is a withdrawn currency (replaced by {successor}); use a current ISO 4217 code that "
            "list_currencies returns.",
        )


class UnsupportedCurrencyError(ToolError):
    """A currency SkyBuyFly does not display prices in."""

    def __init__(self, code: str) -> None:
        """Name the currency."""
        super().__init__(f"Unsupported currency {code!r}: use an ISO 4217 code that list_currencies returns.")


@dataclass(frozen=True, slots=True)
class AirportDirectory:
    """Every compared airport, by IATA code."""

    airports: tuple[AirportEntry, ...]

    @classmethod
    def from_response(cls, response: AirportsResponse) -> AirportDirectory:
        """Group the airport shops by IATA code (names without their ``(IATA)`` suffix), sorted by code.

        Returns:
            The directory.
        """
        grouped: dict[str, AirportEntry] = {}
        for shop in response.airports:
            code = shop.iata_code.strip().upper()
            known = grouped.get(code)
            domains = [] if known is None else known.store_domains
            grouped[code] = AirportEntry(
                code=code,
                name=_CODE_SUFFIX.sub("", shop.name) if known is None else known.name,
                city=shop.city if known is None else known.city,
                store_domains=domains if shop.domain in domains else [*domains, shop.domain],
            )
        codes = sorted(grouped)
        airports = [grouped[code] for code in codes]
        return cls(tuple(airports))

    def store_domains(self, codes: Iterable[str]) -> tuple[str, ...]:
        """Return the store domains of ``codes`` (IATA, any case), each once, in the order given.

        Returns:
            The search API's ``airports`` values.

        Raises:
            UnknownAirportError: A code is no compared airport.
        """
        by_code = {airport.code: airport for airport in self.airports}
        normalized = [code.strip().upper() for code in codes]
        wanted = list(dict.fromkeys(normalized))
        unknown = [code for code in wanted if code not in by_code]
        if unknown:
            raise UnknownAirportError(unknown)
        domains: list[str] = []
        for code in wanted:
            domains.extend(by_code[code].store_domains)
        return tuple(dict.fromkeys(domains))

    def matching(self, query: str | None) -> list[AirportEntry]:
        """Return the airports whose code, name or city contains ``query`` (case-insensitive); all without one.

        Returns:
            The matching airports, sorted by code.
        """
        if query is None or not query.strip():
            return list(self.airports)
        needle = query.strip().casefold()
        return [
            airport for airport in self.airports if needle in f"{airport.code} {airport.name} {airport.city}".casefold()
        ]


@dataclass(frozen=True, slots=True)
class CurrencyBook:
    """Every display currency."""

    currencies: tuple[CurrencyEntry, ...]

    @classmethod
    def from_response(cls, response: CurrenciesResponse) -> CurrencyBook:
        """Keep each current currency's code, name and symbol (withdrawn ones are left out).

        Returns:
            The book.
        """
        current = (entry for entry in response.available_currencies if entry.code not in WITHDRAWN_CURRENCIES)
        entries = (CurrencyEntry(code=entry.code, name=entry.name, symbol=entry.symbol) for entry in current)
        return cls(tuple(entries))

    def require(self, code: str) -> str:
        """Return ``code`` when SkyBuyFly displays prices in it.

        Returns:
            The code.

        Raises:
            WithdrawnCurrencyError: ISO 4217 has withdrawn it.
            UnsupportedCurrencyError: It is no display currency.
        """
        if code in WITHDRAWN_CURRENCIES:
            raise WithdrawnCurrencyError(code)
        if all(entry.code != code for entry in self.currencies):
            raise UnsupportedCurrencyError(code)
        return code
