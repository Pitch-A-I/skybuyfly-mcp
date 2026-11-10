# SkyBuyFly MCP connector

![SkyBuyFly](assets/icon-192.png)

SkyBuyFly compares duty-free prices for the same product across airport shops: hundreds of thousands of
products at more than 80 airports, with prices collected from the airport shops' own websites (shops such as
Heinemann, Avolta and Dubai Duty Free). This repository is the open source SkyBuyFly connector for AI assistants:
a read-only [Model Context Protocol](https://modelcontextprotocol.io) server, its results widget and the client
manifests (Claude plugin, Cursor plugin, Gemini CLI extension, MCP Registry entry). Connect it to your AI
assistant and ask what a product costs at the airports you fly through; it can also confirm a price live on the
airport shop's own page.

**MCP server URL:** `https://skybuyfly.pitchai.net/mcp` (Streamable HTTP, no sign-in, read-only tools)

SkyBuyFly compares prices; it does not sell anything and cannot reserve, order or pay. Links open SkyBuyFly's
product and offer pages, which hand off to the airport shop's website. Tobacco and nicotine products are not
included.

Full documentation: https://skybuyfly.pitchai.net/mcp/docs

## How it works

The connector is a thin facade over the public SkyBuyFly JSON API (`https://skybuyfly.pitchai.net/api`). It holds
no credentials, keeps no state and calls only public read routes; prices, the catalogue and live price checks are
served by SkyBuyFly's own (private) backend behind that API. Each tool validates its inputs, calls the API, shapes
the answer into product cards and offers with their freshness (live-confirmed or stored, with its date), removes
tobacco and nicotine products, and links only to `skybuyfly.pitchai.net`. The server adds its own rate limits, a
cap on concurrent live checks and a short response cache, so it stays inside the API's own limits.

When your assistant calls a SkyBuyFly tool, it sends the tool's inputs (search text, product IDs, barcodes, airport
codes, a currency) to the server, and the server answers with product information, prices and links. Nothing else
is sent anywhere.

| Path | What it is |
|---|---|
| `src/skybuyfly_mcp/` | the MCP server (`mcp` SDK, `httpx`, `uvicorn`): tools, API client, shaping, tobacco screen, limits, widget, service pages |
| `Dockerfile` | the server image (non-root, read-only root filesystem, health check) |
| `.claude-plugin/`, `skills/skybuyfly/SKILL.md` | Claude plugin and Claude Code marketplace (the MCP server is declared inline in `plugin.json`) |
| `.cursor-plugin/plugin.json`, `mcp.json` | Cursor plugin |
| `gemini-extension.json`, `GEMINI.md` | Gemini CLI extension |
| `server.json` | Official MCP Registry entry (`net.pitchai.skybuyfly/skybuyfly`) |
| `.mcp.json`, `glama.json` | project-scope MCP configuration; Glama |
| `assets/` | icons |

## Install

The server needs no sign-in. Every option below connects to `https://skybuyfly.pitchai.net/mcp` directly; the
plugin and extension installs in the Claude Code and Gemini CLI sections add the skill or context file of this
repository as well.

### ChatGPT

In ChatGPT on the web, open https://chatgpt.com/plugins, select the plus button and **Add custom MCP server**.
Enter the name `SkyBuyFly` and, under **Connection**, the server URL `https://skybuyfly.pitchai.net/mcp`. Choose
**No authentication**, review the risk warning and select **I understand and want to continue**, then select
**Create as a plugin**. Install it from your plugins, then type `@` in the prompt box and select SkyBuyFly.
OpenAI's help centre lists custom MCP servers on ChatGPT on the web for Business and Enterprise/Edu, and for Pro
with read and fetch permissions. On Business, an admin or owner adds them.

### Claude (claude.ai, Claude Desktop)

Go to **Customize > Connectors** (https://claude.ai/customize/connectors), select **+ Add** and then
**Add custom connector**. Enter the name `SkyBuyFly` and the remote MCP server URL
`https://skybuyfly.pitchai.net/mcp`, select **Continue**, choose **No sign in** and select **Add**. Turn it on in a
chat with **+ > Connectors**. Custom connectors are available on every Claude plan; on the Free plan you can add
one. On Team and Enterprise plans, an Owner adds it under **Organization settings > Connectors** (**Add**, then
**Custom > Web**), and members then select **Connect** under **Customize > Connectors**.

### Claude Code

```bash
claude mcp add --transport http skybuyfly https://skybuyfly.pitchai.net/mcp
```

This adds the server to the current project; add `--scope user` before the name to use it in all your projects.
To add the server together with the SkyBuyFly skill, install the plugin from this repository:

```bash
claude plugin marketplace add Pitch-A-I/skybuyfly-mcp
claude plugin install skybuyfly@skybuyfly
```

or, inside Claude Code, `/plugin marketplace add Pitch-A-I/skybuyfly-mcp` and `/plugin install skybuyfly@skybuyfly`.

### VS Code

[Install in VS Code](https://vscode.dev/redirect?url=vscode%3Amcp%2Finstall%3F%257B%2522name%2522%253A%2522skybuyfly%2522%252C%2522type%2522%253A%2522http%2522%252C%2522url%2522%253A%2522https%253A%252F%252Fskybuyfly.pitchai.net%252Fmcp%2522%257D)
(opens VS Code, which shows the server for review before you install it), or run **MCP: Add Server** from the
Command Palette, choose **HTTP** and enter the server URL. To use a configuration file, add this to
`~/.copilot/mcp-config.json`:

```json
{
  "mcpServers": {
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

or add it to `~/.cursor/mcp.json` (all projects) or `.cursor/mcp.json` in a project:

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
gemini mcp add --scope user --transport http skybuyfly https://skybuyfly.pitchai.net/mcp
```

Without `--scope user`, the server is added to the current project only. Or add this entry to
`~/.gemini/settings.json`:

```json
{
  "mcpServers": {
    "skybuyfly": {
      "type": "http",
      "url": "https://skybuyfly.pitchai.net/mcp"
    }
  }
}
```

To add the server together with the SkyBuyFly context file, install the extension from this repository:

```bash
gemini extensions install https://github.com/Pitch-A-I/skybuyfly-mcp
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
- Up to 300 tool calls per minute per requesting address and 1,200 in total; live checks are limited to 20 new
  checks per minute and 4 at a time across all users. When a limit is reached, the tool says how long to wait, and
  stored prices stay available.

## Run it yourself

You need Python 3.12 and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run python -m skybuyfly_mcp
```

The server listens on `0.0.0.0:8000` (set `PORT` to change it) and answers MCP at `http://localhost:8000/mcp`,
its health at `/mcp/health` and its documentation pages at `/mcp/docs`. It calls the public SkyBuyFly API, so
it needs no configuration; every setting is an environment variable with a default (`src/skybuyfly_mcp/config.py`):

| Variable | Default | |
|---|---|---|
| `SKYBUYFLY_MCP_API_BASE_URL` | `https://skybuyfly.pitchai.net` | the SkyBuyFly API the tools call |
| `SKYBUYFLY_MCP_PUBLIC_BASE_URL` | `https://skybuyfly.pitchai.net` | the site every link points to |
| `SKYBUYFLY_MCP_CLIENT_CALLS_PER_MINUTE`, `SKYBUYFLY_MCP_GLOBAL_CALLS_PER_MINUTE` | 300, 1200 | tool calls per client address and in total |
| `SKYBUYFLY_MCP_LIVE_MAX_CONCURRENT`, `SKYBUYFLY_MCP_LIVE_RUNS_PER_MINUTE`, `SKYBUYFLY_MCP_LIVE_COALESCE_SECONDS` | 4, 20, 60 | live checks at once, started per minute, and how long one result answers identical requests |

The client address is read from `X-Real-IP`, so run the server behind a reverse proxy that sets that header. With
Docker:

```bash
docker build -t skybuyfly-mcp .
docker run --rm --read-only --tmpfs /tmp -p 127.0.0.1:8000:8000 skybuyfly-mcp
```

A server you run yourself is subject to the SkyBuyFly API's own limits for your address; for everyday use, connect
to `https://skybuyfly.pitchai.net/mcp`.

## Tests

The connector's test suite (offline unit and end-to-end tests on recorded API answers, an integration suite
against the live API, load tests and widget checks) is maintained in SkyBuyFly's private repository, together with
the hosting setup. This repository mirrors the connector code of each release.

## Privacy, terms and support

- Privacy notice for SkyBuyFly in AI assistants: https://skybuyfly.pitchai.net/mcp/privacy
  (no account, no cookies, no analytics or tracking; the server receives only tool inputs, never your
  conversation)
- Terms of use for SkyBuyFly in AI assistants: https://skybuyfly.pitchai.net/mcp/terms
- Support: https://skybuyfly.pitchai.net/mcp/support (contact form https://skybuyfly.pitchai.net/contact, or
  info@pitchai.net)

## License

The code, manifests and documentation in this repository are licensed under the MIT License (see `LICENSE`).
SkyBuyFly's API, backend and data are operated by PitchAI and are not covered by this license; using them through
this connector is subject to the terms of use above.
