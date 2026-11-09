---
name: skybuyfly
description: Compare airport duty-free prices with the SkyBuyFly tools. Use when the user asks what a product costs at airport duty-free shops, which airport sells it for less, whether a price is current, how a price has changed, or which product a barcode belongs to.
---

# Compare duty-free prices with SkyBuyFly

SkyBuyFly compares the prices of airport duty-free shops for the same product. Its tools are read-only: they
search SkyBuyFly's catalogue and can confirm a price on the airport shop's own page. SkyBuyFly does not sell
anything, so it cannot reserve, order or pay for a product.

## Steps

1. **Find the product.** Call `search_products` with the product name, brand or category, for example
   `Chanel Coco Mademoiselle 100 ml`. If the user names airports, pass their IATA codes in `airports`, for
   example `["VIE", "BER"]`. If the user gives a barcode, call `lookup_barcode` with its digits instead.
   If you do not know an airport's code, call `list_airports` first.
2. **Compare.** Each product card lists the airports that sell the product, cheapest first. Call `get_product`
   with the `product_id` to see every stored offer for one product.
3. **Check live when it matters.** When the user wants current prices, call `get_live_prices` with the
   `product_id`. It takes about 5 to 15 seconds. Every offer comes back as live-confirmed or as a stored price
   with the date it was observed. If `live_status` is `rate_limited`, call `get_product` and say that the prices
   shown are stored prices.
4. **History.** For "has the price changed" or "is this a good price", call `get_price_history`.
5. **Currency.** Pass `currency` (an ISO 4217 code such as `EUR`) to show prices in the user's currency;
   `list_currencies` lists the supported codes.

## How to answer

- Name the airport for every price and give the currency.
- Say whether a price was confirmed live just now or is a stored price, and give its date.
- Link to the product with its `skybuyfly_url`.
- If nothing is found, say so; do not estimate prices.
- Tobacco and nicotine products are not available through SkyBuyFly.
