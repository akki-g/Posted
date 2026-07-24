# Assistant Web Search (with sourced citations)

## Goal

Give Posted's financial assistant (`backend/app/services/assistant.py`) the ability to search the live web, restricted to an allowlist of reliable sources, and show the user which sources it drew from.

## Background

The assistant is a Claude tool-use agent (`run_assistant_turn`) with a fixed set of client-executed tools (`get_money_overview`, `get_recent_transactions`, `get_portfolio_holdings`, `search_company_news` via OpenBB, etc.). It has no general web search — `search_company_news` only covers news for a specific ticker via OpenBB. There's no way for it to answer general questions ("what's the Fed doing with rates", "what does expense ratio mean") grounded in current information.

Anthropic's Claude API has a server-side `web_search` tool (current type: `web_search_20260209`) that Claude can call directly — Anthropic executes the search and fetches, and returns results with automatic citations embedded in the response text. It supports an `allowed_domains` allowlist, which is the mechanism used here to restrict results to "reliable" sources.

## Design

### 1. Add the web search tool

In `assistant.py`, add a `RELIABLE_DOMAINS` constant and append the server-side web search tool to the existing `TOOLS` list:

```python
RELIABLE_DOMAINS = [
    # Wire & financial press
    "reuters.com", "apnews.com", "bloomberg.com", "wsj.com", "cnbc.com",
    "ft.com", "marketwatch.com", "barrons.com",
    # Official / regulatory
    "sec.gov", "federalreserve.gov", "treasury.gov", "bls.gov",
    # Newswire distribution (proxy for company IR/press releases — allowed_domains
    # can't enumerate every ticker's own domain, so the wire services they publish
    # through stand in for it)
    "businesswire.com", "prnewswire.com", "globenewswire.com", "accesswire.com",
    # Reference / education
    "investopedia.com", "morningstar.com", "nerdwallet.com",
]

WEB_SEARCH_TOOL = {
    "type": "web_search_20260209",
    "name": "web_search",
    "max_uses": 5,
    "allowed_domains": RELIABLE_DOMAINS,
}
```

This is a server-executed tool — Anthropic runs the search, no `_execute_tool` handler is needed. It's appended to `TOOLS` alongside the existing custom tool dicts (mixed `tools` arrays are supported). `search_company_news` (OpenBB) is unchanged and stays as the portfolio-aware company news lookup; web search covers general/broader questions.

### 2. Handle `pause_turn`

Server tools run their own internal sampling loop (default cap 10 iterations). If that cap is hit mid-turn, the API returns `stop_reason: "pause_turn"` with partial content instead of a final answer. The current loop in `run_assistant_turn` only branches on `stop_reason in {"refusal", "tool_use"}` and otherwise treats the response as final — which would silently truncate a paused search turn.

Add a branch: on `pause_turn`, append the assistant's response to `messages` and continue the loop (re-send, no `tool_result` needed) rather than returning it as the final reply. This shares the existing `MAX_TOOL_ITERATIONS` outer cap, so it can't loop forever.

### 3. Capture sources

Once a turn produces a genuine final answer (`stop_reason` is `end_turn` or similar, not `tool_use`/`pause_turn`/`refusal`), scan the response's `text` content blocks for their `citations` list (auto-populated by the web search tool when a claim is grounded in a search result — no opt-in needed, unlike document citations). Collect unique `{title, url}` pairs across all text blocks in the response.

`AssistantTurnResult` gains a `sources: list[dict[str, str]]` field (default empty list) alongside `reply` and `tool_calls_made`.

### 4. Persistence

- `AssistantMessage` (`backend/app/db/models.py`): add `sources: Mapped[list[dict] | None] = mapped_column(JSON)`, matching the existing `JSON` column pattern used on `MarketEvent.reasons` / `SyncRun.warnings`.
- `send_message` in `assistant.py` passes `result.sources` into the new `AssistantMessage` row when saving the assistant's reply. User-authored rows have no sources.
- **No migration tooling exists in this repo** (`Base.metadata.create_all` only creates missing tables, it doesn't alter existing ones). The local `backend/posted.db` (and `posted-live.db` if present) will need to be deleted once so they're recreated with the new column on next backend startup. This is local dev/demo data, not a real migration — acceptable for this MVP-stage project.
- `AssistantMessageSummary` (`backend/app/api/schemas.py`): add `sources: list[SourceItem] | None`, where `SourceItem = {title: str, url: str}` (or reuse a plain `dict[str, str]`).

### 5. System prompt

Add a line to `SYSTEM_PROMPT` telling the assistant to use web search for questions needing current information beyond the app's own data (rates, market conditions, definitions, general finance questions), and reinforcing that answers must be grounded in what was actually retrieved — consistent with the existing "never invent numbers" rule.

### 6. Frontend

- `AssistantMessageSummary` (`apps/client/src/lib/types.ts`): add `sources?: { title: string; url: string }[] | null`.
- `apps/client/src/app/assistant.tsx`: under an assistant bubble whose message has `sources`, render a small "Sources" row of pressable links via `Linking.openURL`, following the existing pattern in `apps/client/src/app/event/[id].tsx` (`ExternalLink` icon + `sourceLink`/`sourceLinkText` styles) rather than inventing a new UI convention.

## Out of scope

- `ai_insights.py` (event insights / morning debrief) is not touched — this is scoped to the interactive assistant chat only.
- No UI for editing/configuring the domain allowlist — it's a fixed backend constant for now.
- No dedup/ranking of sources beyond unique `{title, url}` pairs.
