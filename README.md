# SkyBuyFly for AI assistants

![SkyBuyFly](assets/icon-192.png)

SkyBuyFly compares duty-free prices for the same product across airport shops: about 258,000 products at
87 airports, with prices collected from the airport shops' own websites (shops such as Heinemann, Avolta,
Schiphol and Aelia). Connect SkyBuyFly to your AI assistant and ask what a product costs at the airports you fly
through. SkyBuyFly can also confirm a price live on the airport shop's own page.

**MCP server URL:** `https://skybuyfly.pitchai.net/mcp` (Streamable HTTP, no sign-in, read-only tools)

SkyBuyFly compares prices; it does not sell anything and cannot reserve, order or pay. Links open SkyBuyFly's
product and offer pages, which hand off to the airport shop's website. Tobacco and nicotine products are not
included.

This repository holds the client manifests and documentation for connecting AI assistants to SkyBuyFly. The MCP
server itself is operated by PitchAI at the URL above; its source code is not part of this repository.

Full documentation: https://skybuyfly.pitchai.net/mcp/docs

## What this repository contains and does

It contains no executable code. The manifests configure one remote MCP server,
`https://skybuyfly.pitchai.net/mcp`, and one skill with instructions for using its tools. When your assistant
calls a SkyBuyFly tool, it sends the tool's inputs (search text, product IDs, barcodes, airport codes, a
currency) to that server, and the server answers with product information, prices and links to
`skybuyfly.pitchai.net`. Nothing else is sent anywhere.

| File | Used by |
|---|---|
| `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json` | Claude plugin and Claude Code marketplace (the MCP server is declared inline in `plugin.json`) |
| `skills/skybuyfly/SKILL.md` | the skill for Claude and Cursor |
| `.cursor-plugin/plugin.json`, `mcp.json` | Cursor plugin |
| `gemini-extension.json`, `GEMINI.md` | Gemini CLI extension |
| `server.json` | Official MCP Registry entry (`net.pitchai.skybuyfly/skybuyfly`) |
| `glama.json` | Glama |
| `assets/` | icons |

## Install

### ChatGPT

In ChatGPT on the web, open https://chatgpt.com/plugins, select the plus button and **Add custom MCP server**.
Enter the name `SkyBuyFly`, put `https://skybuyfly.pitchai.net/mcp` under **Connection**, choose
**No authentication**, confirm, and select **Create as a plugin**. Install it from your plugins and mention it
with `@` in a chat. OpenAI's help centre lists custom MCP servers for ChatGPT Business and Enterprise/Edu on the
web; on Business, an admin or owner adds them.

### Claude (claude.ai, Claude Desktop)

Go to **Customize > Connectors** (https://claude.ai/customize/connectors), select **Add custom connector**,
enter the name `SkyBuyFly` and the URL `https://skybuyfly.pitchai.net/mcp`, choose **No sign-in**, and select
**Add**. On the Free plan you can add one custom connector. On Team and Enterprise plans, an Owner adds it under
**Organization settings > Connectors**, and members then select **Connect**. Turn it on in a chat with
**+ > Connectors**.

### Claude Code

```bash
claude mcp add --transport http skybuyfly https://skybuyfly.pitchai.net/mcp
```

Or install the plugin, which adds the server and the SkyBuyFly skill:

```text
/plugin marketplace add Pitch-A-I/skybuyfly-mcp
/plugin install skybuyfly@skybuyfly
```

### VS Code

[Install in VS Code](https://vscode.dev/redirect?url=vscode%3Amcp%2Finstall%3F%257B%2522name%2522%253A%2522skybuyfly%2522%252C%2522type%2522%253A%2522http%2522%252C%2522url%2522%253A%2522https%253A%252F%252Fskybuyfly.pitchai.net%252Fmcp%2522%257D)
(opens VS Code, which shows the server for review before you install it), or run:

```bash
code --add-mcp '{"name":"skybuyfly","type":"http","url":"https://skybuyfly.pitchai.net/mcp"}'
```

or add it to `.vscode/mcp.json`:

```json
{
  "servers": {
    "skybuyfly": {
      "type": "http",
      "url": "https://skybuyfly.pitchai.net/mcp"
    }
  }
}
```

### Cursor

Use the "Add to Cursor" button on https://skybuyfly.pitchai.net/mcp/docs, or paste this install link into your
browser's address bar (Cursor asks before it installs the server):

```text
cursor://anysphere.cursor-deeplink/mcp/install?name=SkyBuyFly&config=eyJ1cmwiOiJodHRwczovL3NreWJ1eWZseS5waXRjaGFpLm5ldC9tY3AifQ==
```

or add it to `~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "skybuyfly": {
      "url": "https://skybuyfly.pitchai.net/mcp"
    }
  }
}
```

### Gemini CLI

```bash
gemini extensions install https://github.com/Pitch-A-I/skybuyfly-mcp
```

or add only the server:

```bash
gemini mcp add --transport http skybuyfly https://skybuyfly.pitchai.net/mcp
```

### Windsurf (Devin Desktop)

Windsurf is now part of Devin Desktop. In the Cascade MCP settings, select **Add Server** or open the MCP
config file, and add:

```json
{
  "mcpServers": {
    "skybuyfly": {
      "serverUrl": "https://skybuyfly.pitchai.net/mcp"
    }
  }
}
```

Then press the refresh button. On Enterprise plans, MCP has to be switched on in the settings first.

### Mistral Vibe (Le Chat)

Le Chat is now Mistral Vibe (https://chat.mistral.ai). Open **Connectors** in the sidebar, select
**+ Add Connector**, open the **Custom MCP Connector** tab, enter the name `SkyBuyFly` and the server URL
`https://skybuyfly.pitchai.net/mcp`, and select **Connect**. Vibe detects that no authentication is needed. Adding
connectors is an administrator feature; on Free, Pro and Student plans the account owner is the administrator.

### Perplexity

Open **Plugins** in the sidebar (or **Customize > Connectors**), choose **Add custom > Connector >
Add MCP connector**, select **Remote**, enter the name `SkyBuyFly` and the MCP server URL
`https://skybuyfly.pitchai.net/mcp`, set **Authentication** to **None** and **Transport** to **Streamable HTTP**,
accept the notice and select **Add**. Then select the connector card to turn it on. Perplexity offers custom
connectors on its Pro, Max and Enterprise plans.

### Other MCP clients

Add a remote MCP server with the Streamable HTTP transport and the URL `https://skybuyfly.pitchai.net/mcp`.
No authentication or headers are needed.

## Tools

All tools are read-only. Every tool that shows prices takes an optional `currency` (ISO 4217, default `USD`).

| Tool | What it does |
|---|---|
| `search_products` | Search by product name, brand or category; optionally only at given airports (IATA codes). One card per product with its price at every airport shop that sells it, cheapest first. |
| `get_product` | One product's description, size, every stored airport offer and similar products. |
| `get_live_prices` | Confirm the product's prices now on each airport shop's page (about 5 to 15 seconds). Every offer is marked live-confirmed or stored with its date. |
| `get_price_history` | Observed prices per airport over time, with the lowest and latest price. |
| `lookup_barcode` | Find the product for an EAN-8, UPC-A, EAN-13 or GTIN-14 barcode. |
| `list_airports` | The airports SkyBuyFly compares, with IATA code, name, city and store domains. |
| `get_featured_products` | Featured products and popular categories (not personalised). |
| `list_currencies` | The currencies prices can be shown in. |
| `get_catalogue_stats` | Number of products and airports, and when the figures were generated. |

## Example prompts

- What does Chanel Coco Mademoiselle Eau de Parfum 100 ml cost at Vienna, Berlin and Vilnius duty free right now?
- Show the price history of Dior Sauvage Eau de Parfum 100 ml at airport duty-free shops.
- Which airport shops sell the product with barcode 3145891165203?
- Compare Lagavulin 16 at Copenhagen and Düsseldorf duty free in euros.
- Which London airports does SkyBuyFly compare?

## Limits

- A live check usually takes 5 to 15 seconds (the tool waits at most 20 seconds).
- Up to 300 tool calls per minute per requesting address and 1,200 in total; live checks are limited to 20 new checks per
  minute and 4 at a time across all users. When a limit is reached, the tool says how long to wait, and stored
  prices stay available.

## Privacy, terms and support

- Privacy notice for SkyBuyFly in AI assistants: https://skybuyfly.pitchai.net/mcp/privacy
  (no account, no cookies, no analytics or tracking; the server receives only tool inputs, never your
  conversation)
- Terms of use for SkyBuyFly in AI assistants: https://skybuyfly.pitchai.net/mcp/terms
- Support: https://skybuyfly.pitchai.net/mcp/support (contact form https://skybuyfly.pitchai.net/contact, or info@pitchai.net)

## License

The manifests and documentation in this repository are licensed under the MIT License (see `LICENSE`).
SkyBuyFly, its MCP server and its data are operated by PitchAI and are not covered by this license.
