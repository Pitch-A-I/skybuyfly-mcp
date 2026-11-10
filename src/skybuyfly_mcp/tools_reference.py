# Copyright (c) 2026 PitchAI. Licensed under the MIT License (see LICENSE).
"""The three reference tools (no widget): airports, currencies and catalogue statistics."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

import mcp_types

from skybuyfly_mcp import browse, contract_reference, descriptions, inputs, runtime, summaries
from skybuyfly_mcp.tools import ToolCard

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

    from skybuyfly_mcp.services import Services
    from skybuyfly_mcp.tools import ToolFunction

AirportsAnswer = Annotated[mcp_types.CallToolResult, contract_reference.AirportsResult]
CurrenciesAnswer = Annotated[mcp_types.CallToolResult, contract_reference.CurrenciesResult]
StatsAnswer = Annotated[mcp_types.CallToolResult, contract_reference.StatsResult]
AirportFilter = inputs.AirportFilter
LIST_AIRPORTS = ToolCard(
    "list_airports",
    "List the compared airports",
    descriptions.LIST_AIRPORTS,
    "Listing airports…",
    "Listed airports",
)
LIST_CURRENCIES = ToolCard(
    "list_currencies",
    "List the display currencies",
    descriptions.LIST_CURRENCIES,
    "Listing currencies…",
    "Listed currencies",
)
GET_CATALOGUE_STATS = ToolCard(
    "get_catalogue_stats",
    "Catalogue size and freshness",
    descriptions.GET_CATALOGUE_STATS,
    "Reading catalogue statistics…",
    "Read catalogue statistics",
)


def register_reference_tools(server: MCPServer, services: Services) -> dict[str, ToolFunction]:
    """Register the reference tools on ``server``.

    Returns:
        Each tool's function by name (``arguments`` checks their arguments).
    """
    catalogue, runner = services.catalogue, services.runner

    @server.tool(
        name=LIST_AIRPORTS.name,
        title=LIST_AIRPORTS.title,
        description=LIST_AIRPORTS.description,
        annotations=LIST_AIRPORTS.annotations(),
        meta=LIST_AIRPORTS.meta(),
        structured_output=True,
    )
    async def list_airports(query: AirportFilter = None) -> AirportsAnswer:
        async def work() -> runtime.Rendered:
            airports = (await catalogue.airports()).matching(query)
            result = contract_reference.AirportsResult(airports=airports, total=len(airports))
            return runtime.Rendered(result, summaries.airports_summary(result))

        return await runner.run("list_airports", work, query=query)

    @server.tool(
        name=LIST_CURRENCIES.name,
        title=LIST_CURRENCIES.title,
        description=LIST_CURRENCIES.description,
        annotations=LIST_CURRENCIES.annotations(),
        meta=LIST_CURRENCIES.meta(),
        structured_output=True,
    )
    async def list_currencies() -> CurrenciesAnswer:
        async def work() -> runtime.Rendered:
            result = contract_reference.CurrenciesResult(currencies=list((await catalogue.currencies()).currencies))
            return runtime.Rendered(result, summaries.currencies_summary(result))

        return await runner.run("list_currencies", work)

    @server.tool(
        name=GET_CATALOGUE_STATS.name,
        title=GET_CATALOGUE_STATS.title,
        description=GET_CATALOGUE_STATS.description,
        annotations=GET_CATALOGUE_STATS.annotations(),
        meta=GET_CATALOGUE_STATS.meta(),
        structured_output=True,
    )
    async def get_catalogue_stats() -> StatsAnswer:
        async def work() -> runtime.Rendered:
            result = await browse.catalogue_stats(catalogue)
            return runtime.Rendered(result, summaries.stats_summary(result))

        return await runner.run("get_catalogue_stats", work)

    return {
        "list_airports": list_airports,
        "list_currencies": list_currencies,
        "get_catalogue_stats": get_catalogue_stats,
    }
