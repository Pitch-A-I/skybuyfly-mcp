# Copyright (c) 2026 PitchAI. Licensed under the MIT License (see LICENSE).
"""What the model reads: the server instructions and each tool's description (when to use it and when not)."""

from __future__ import annotations

INSTRUCTIONS = (
    "SkyBuyFly compares the prices of airport duty-free shops (perfume, cosmetics, spirits, wine, sweets, "
    "electronics, fashion); get_catalogue_stats tells how many products and airports it covers. It does not sell "
    "anything: every link opens the product or deal page on skybuyfly.pitchai.net, which hands off to the shop.\n"
    "- Start with search_products (or lookup_barcode for a barcode). Each card shows the product's price at every "
    "airport that sells it, cheapest first, and its lowest price, which may be a retailer's online shop serving "
    "several airports; pass airports=[IATA codes] to compare specific airports.\n"
    "- Prices are per airport shop and are the latest stored observations. When the traveller wants current "
    "prices, call get_live_prices with the product_id: it confirms each airport's price on the shop's page now "
    "(5-15 s) and marks every offer live-confirmed or stored with its date. If it is rate limited, use get_product "
    "for the stored offers.\n"
    "- get_price_history shows how prices developed; list_airports and list_currencies give the valid airport "
    "codes and currencies; get_featured_products gives inspiration.\n"
    "- Every price names its airport shop and whether it is live-confirmed or stored (and when). Tobacco and "
    "nicotine products are not available."
)

SEARCH_PRODUCTS = (
    "Search SkyBuyFly's price comparison of airport duty-free shops by product name, brand or category. Returns "
    "one card per product with its price at every airport shop that sells it (cheapest first, in the requested "
    "currency), its lowest price (an airport's or an online shop's), its product_id and a link to its SkyBuyFly "
    "page. Relevant when a traveller asks what something costs at airports, where it is cheapest, or whether an "
    "airport sells it. With airports (IATA codes) it returns only the products listed at every one of them, each "
    "card showing those airports' prices. Prices are the latest stored observations, each with its date; this tool "
    "does not check them live."
)
GET_PRODUCT = (
    "Get one SkyBuyFly product by its product_id: its description and size, every stored offer per airport shop "
    "(the shop's own price, the price in the requested currency, when it was observed, a link to the SkyBuyFly "
    "deal page) and similar products. Relevant when a traveller wants every airport and shop for one product. The "
    "prices are stored observations; this tool does not check them live."
)
GET_LIVE_PRICES = (
    "Check a product's prices live at every airport shop that sells it: SkyBuyFly opens each shop's page now and "
    "confirms the current price. Every offer comes back marked live_confirmed (checked just now) or stored (the last "
    "observed price, with its date), cheapest first. Takes about 5-15 seconds. Relevant when a traveller wants "
    "current prices or is deciding where to buy. A check of the same product within a minute returns the same "
    "result; when SkyBuyFly's price service is busy the answer is rate_limited and lists no offers."
)
GET_PRICE_HISTORY = (
    "Get a product's observed prices per airport over time: SkyBuyFly's 50 most recent observations (the answer "
    "says which dates they cover), as each airport's price changes, with the lowest and latest price. Relevant when "
    "a traveller asks whether a price is good, has changed or how it developed. It does not check current prices."
)
LOOKUP_BARCODE = (
    "Find the SkyBuyFly product that carries a barcode (the digits of an EAN-8, UPC-A, EAN-13 or GTIN-14, e.g. "
    "read from a box or a photo) with its price at each airport shop that has an offer for that code, and when it "
    "was seen. An empty list means no airport shop SkyBuyFly compares sells it. It does not search by name."
)
GET_FEATURED_PRODUCTS = (
    "Get SkyBuyFly's featured airport duty-free products with their airport prices, and the most popular catalogue "
    "categories. Not personalised. Relevant when a traveller wants inspiration or asks what is popular at duty free."
)
LIST_AIRPORTS = (
    "List the airports whose duty-free shops SkyBuyFly compares: IATA code, name, city and the shops' store "
    "domains, optionally only those matching a text (code, name or city). Relevant for finding an airport's IATA "
    "code or answering which airports are covered."
)
LIST_CURRENCIES = (
    "List the currencies SkyBuyFly shows prices in (ISO 4217 code, name, symbol). Every price tool takes one of "
    "these codes as currency."
)
GET_CATALOGUE_STATS = (
    "Get the size and freshness of SkyBuyFly's price comparison catalogue: the number of products, the number of "
    "airports and when the figures were generated. Relevant when asked how much SkyBuyFly covers."
)
