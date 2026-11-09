# SkyBuyFly tools

The `skybuyfly` MCP server compares airport duty-free prices for the same product. All tools are read-only.
SkyBuyFly does not sell anything: it cannot reserve, order or pay.

- `search_products`: find products by name, brand or category. Pass `airports` (IATA codes such as `VIE`,
  `BER`) to compare specific airports and `currency` (ISO 4217, default `USD`) for the prices.
- `lookup_barcode`: find the product for a barcode (EAN-8, UPC-A, EAN-13 or GTIN-14 digits).
- `get_product`: every stored airport offer of one product (`product_id` from a search).
- `get_live_prices`: confirm a product's prices now on each airport shop's page (about 5 to 15 seconds).
  Each offer is live-confirmed or a stored price with its date. If the result is `rate_limited`, use
  `get_product` and say the prices are stored.
- `get_price_history`: observed prices per airport over time.
- `list_airports`, `list_currencies`, `get_featured_products`, `get_catalogue_stats`: reference data.

When you answer, name the airport and currency of every price, say whether it was confirmed live or is stored
(and when), and give the product's SkyBuyFly link. Tobacco and nicotine products are not available.
