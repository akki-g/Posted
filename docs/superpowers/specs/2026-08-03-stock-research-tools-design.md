# Stock research tools for the financial assistant

## Goal

Give Posted's existing financial assistant (`backend/app/services/assistant.py`) real
independent stock-research capability: technical indicators, SEC filings, and an
on-demand deep-research bundle that pulls quote, fundamentals, indicators, insider
sentiment, news, and filings together. This must work identically through both entry
points that already share the assistant — the in-app chat (`/assistant/messages`) and
the Telnyx SMS bridge (`app/services/sms.py`) — since both call the same
`send_message`/`run_assistant_turn` functions.

## Current state

The assistant already does real Anthropic tool-use (a hand-rolled `TOOLS` list +
`_execute_tool` dispatch, not the Model Context Protocol) on `claude-haiku-4-5`, with
tools for money/portfolio data, a portfolio-scoped news/impact feed, ad hoc company
news search, insider activity (Finnhub MSPR + deterministic interpretation), and
Anthropic's hosted `web_search` restricted to a fixed set of reliable domains.
Market data comes from Alpaca (IEX quotes/history), Finnhub (fundamentals, earnings,
insider transactions/sentiment, search), and Yahoo (fallback), with a demo-data path
for unconfigured environments. `SecEdgarAdapter` (SEC filings) exists in
`app/providers/sec/client.py` but is not wired into any live code path today. No
technical-indicator calculation exists anywhere in the codebase.

Brokerage-backed tools (`get_portfolio_overview`, `get_portfolio_holdings`,
`get_insider_activity`) are gated through `sync_stale_brokerage_connections` before
they read — this is how Schwab/Plaid holdings stay fresh (lazy sync-on-read, not a
cron job). This gating must be preserved for any new tool that reads position data.

## Decisions from brainstorming

- Extend the existing hand-rolled tool-use pattern; do not migrate to the MCP
  protocol. No new process or protocol-translation layer.
- Indicator set: SMA/EMA + MACD (trend), RSI + Stochastic (momentum), Bollinger
  Bands + ATR (volatility), volume vs. its own moving average.
- Deep research is a distinct, explicitly-triggered tool (`run_stock_research`), not
  the default behavior for every ticker mention — keeps ordinary questions fast and
  SMS-friendly.
- Include SEC filings (8-K/10-K/10-Q) in the research bundle via `SecEdgarAdapter`.
- Escalate to `claude-sonnet-5` for the remainder of a turn once `run_stock_research`
  is called, to get materially better synthesis over the dense bundle; ordinary
  turns stay on `claude-haiku-4-5`.

## New tools

### `get_technical_indicators(symbol)`

New module `app/market/indicators.py`, pure Python (no numpy/pandas — consistent
with the codebase's existing use of `statistics.fmean` for similar math), operating
on the `list[PriceBar]` daily bars already returned by `get_stock_history(symbol,
period="1Y")`.

Computed, each as a single latest value plus a short plain-language read:

- SMA(20), SMA(50), SMA(200), EMA(12), EMA(26)
- MACD line, signal line (EMA9 of MACD), histogram
- RSI(14) (Wilder smoothing)
- Stochastic %K/%D(14)
- Bollinger Bands(20, 2 std): upper/middle/lower vs. latest close
- ATR(14) (Wilder smoothing)
- Volume trend: latest volume vs. 20-day average volume, as a ratio

Only latest values are returned, not full series — keeps tool-result tokens bounded
regardless of chat or SMS. When there isn't enough history for a given window (e.g.
a recent IPO can't support SMA200), that indicator is `null` with a short note
instead of failing the whole call. No brokerage data involved, so this tool is not
gated on brokerage sync.

### `get_sec_filings(symbol, limit?)`

Wraps `SecEdgarAdapter.fetch_recent_filings`, which needs a CIK, not a ticker.
Today `Security.cik` is only populated for three hand-seeded demo securities, so a
new cached resolver is required for arbitrary tickers: fetch and cache (in-memory,
~24h TTL) SEC's public `company_tickers.json` ticker→CIK mapping, added to
`SecEdgarAdapter` as `resolve_cik(symbol)`. The tool then calls
`fetch_recent_filings` with a 90-day window and maps each `ProviderEventEnvelope` to
`{form_type, headline, source_url, published_at}`. Uses the existing
`settings.sec_user_agent`. Not brokerage-gated.

### `run_stock_research(symbol)`

The deep-research bundle, described to the model as the tool to call when the user
clearly wants a full workup ("give me a full research report on X", "do a deep dive
on Y"), as opposed to quick single-fact questions which keep using the lighter
existing tools. Internally, concurrently:

- `get_stock_detail` for quote/company profile/earnings/position
- indicator computation (same function `get_technical_indicators` uses)
- insider summary + interpretation, reusing `summarize_insider_activity` /
  `interpret_insider_activity` directly against `get_stock_detail`'s already-fetched
  `insider_transactions`/`insider_sentiment` (not a second call through
  `get_insider_analysis`, which would re-fetch `get_stock_detail`/`get_stock_history`
  a second time)
- a fresh multi-source news search via the same call `search_company_news` uses
  (`get_stock_detail.related_news` only reflects the portfolio event store, which is
  usually empty for a stock the user doesn't hold, so it isn't sufficient on its own
  for independent research)
- SEC filings, via the same logic as `get_sec_filings`

Returns one structured bundle as the tool result; the model performs the synthesis
in its own response text. Because `get_stock_detail` resolves the user's position,
`run_stock_research` joins `_BROKERAGE_BACKED_TOOLS` so it's gated on
`sync_stale_brokerage_connections` exactly like `get_portfolio_holdings` and
`get_insider_activity` today — this is what keeps Schwab/Plaid data fresh before a
research turn reads it.

## Model escalation

`run_assistant_turn`'s per-iteration model choice becomes conditional: it starts
each turn on `claude-haiku-4-5`; once a `tool_use` block for `run_stock_research`
is executed, all subsequent `messages.create` calls within that same turn use
`claude-sonnet-5` instead. The next user turn starts back on haiku by default. This
applies identically in chat and SMS since both flow through this one function.

## System prompt updates

`SYSTEM_PROMPT` gets guidance for when to reach for `run_stock_research` vs. the
lighter tools (explicit deep-dive language vs. a quick fact lookup), and the
existing hard rules (no buy/sell/hold recommendations, no price predictions, cite
only what tools actually returned, separate reported facts from inference) extend
to indicators and filings the same way they already apply to insider activity and
news.

## SMS

No SMS-specific code changes are needed. SMS already shares `send_message`/
`run_assistant_turn` with chat, and the existing screen-context framing already
instructs the model to keep SMS replies concise plain text. A deep-research request
over SMS gets the same bundle as chat; the model's own reply is just a tighter
summary, per the existing prompt instructions.

## Testing

- Unit tests for each indicator in `app/market/indicators.py` against hand-computed
  values on a fixed bar series, including the insufficient-history degradation path.
- A test for `get_sec_filings` / CIK resolution against a mocked EDGAR/ticker-map
  response.
- `test_assistant.py`-level tests verifying: `run_stock_research` triggers the
  sonnet escalation for the rest of the turn; `run_stock_research` is included in
  `_BROKERAGE_BACKED_TOOLS` and triggers `sync_stale_brokerage_connections`; the
  three new tools are present in `TOOLS` with valid schemas.

## Out of scope

- Migrating the assistant to the actual MCP protocol.
- Any new paid/external data provider beyond what's already integrated
  (Alpaca, Finnhub, Yahoo, SEC EDGAR, Anthropic web search).
- Changes to the Schwab/Plaid sync mechanism itself (only reuse of the existing
  gate).
- Making deep research the default behavior for every ticker mention.
