# Handoff — frontend redesign + backend assistant account-data tools

Written 2026-07-28 for a fresh agent picking up this work with no conversation
history. Read this whole file before touching anything. It supersedes nothing
in `design/implementation-progress.md` — read that too, it's the authoritative
phase-by-phase log for the frontend redesign specifically.

## Status update — 2026-07-28, later same day

Both workstreams below (frontend tab merge, backend sync-before-read) are now
**done, uncommitted**. Standing constraints (no commit/push, env-leak prefix,
SignalWire signing key, no browser automation) all still apply unchanged.

**Backend (workstream 3, "sync-before-read")** — implemented as originally
recommended: extended the existing native tool-use loop rather than building a
literal MCP server. New `backend/app/services/connection_sync.py` owns
`is_stale()` (5min, mirrors the frontend's `AUTO_SYNC_STALE_MS`) and
`sync_stale_brokerage_connections()`/`sync_stale_money_connections()`;
`backend/app/services/assistant.py`'s `_execute_tool` now gates 6 tools by
domain — `_MONEY_BACKED_TOOLS` (`get_money_overview`,
`get_recent_transactions`, `get_recurring_subscriptions`) and
`_BROKERAGE_BACKED_TOOLS` (`get_portfolio_overview`, `get_portfolio_holdings`,
and **`get_insider_activity`** — it looked independent at first glance but its
`get_insider_analysis` call reads `get_holdings`, so it needed the same
brokerage-freshness guarantee). `backend/app/api/routes/connections.py` and
`plaid.py` were refactored to reuse the same adapters/`sync_plaid_money_connection`
instead of duplicating them (per the original recommendation). Full backend
suite: 196 passed, ruff clean.

An 8-angle automated review (+ manual follow-up) caught two real bugs that are
now fixed, both worth knowing about if you touch this code again:
- The sync helpers originally swallowed exceptions without `session.rollback()`
  — a failure after a partial DB flush left the shared `AsyncSession` needing a
  rollback, so the very read the sync was meant to protect would raise
  `PendingRollbackError` instead of running. Fixing this naively then exposed a
  second bug: rolling back mid-loop expires every ORM object already fetched in
  that loop, so a second stale connection's `.status`/`.provider` access after
  the first one's rollback raised `sqlalchemy.exc.MissingGreenlet`. Both
  functions now re-fetch each connection by id right before syncing it instead
  of holding long-lived ORM references across a possible rollback boundary —
  see `test_connection_sync.py`'s `*_rolls_back_after_*`/`*_recovers_for_a_later_connection_after_rollback`
  tests for the regression coverage.
- `get_insider_activity` was originally left out of the sync gate.

**Deliberately deferred** (reported, not fixed — reasoned tradeoffs, not
oversights):
- A successful sync can trigger a mid-turn `session.commit()` (via
  `sync_plaid_transactions`'s own internal commit), persisting `send_message`'s
  flushed-but-uncommitted user message before the assistant's reply exists. If
  something later in that turn raises an uncaught exception (not one of the
  three explicitly handled Anthropic error types), the conversation could end
  up with two consecutive `user`-role messages, which the Anthropic API
  rejects — breaking that conversation until cleared. Low probability, real;
  a full fix would mean restructuring `send_message`'s commit boundary or the
  shared sync adapters' internal commits (used correctly elsewhere), which
  felt like more surgery than this task warranted.
- No backoff for a permanently-broken connection (revoked OAuth/Plaid item) —
  every connection-backed tool call retries the doomed sync since
  `is_stale()` never returns false. A circuit-breaker is out of scope here.
- Minor cleanup left as-is: `PlaidClient`/`SchwabOAuthClient` construction is
  now duplicated 3-4x across `connections.py`/`plaid.py`/`connection_sync.py`;
  the account-upsert loop in `plaid.py`'s `exchange_plaid_public_token` mirrors
  `sync_plaid_money_connection`'s loop; stale connections sync sequentially
  rather than concurrently. None are bugs, all are candidates for a future
  pass if this area gets touched again.

**Frontend (workstream 1, tab merge)** — completed by a different agent
working concurrently in this same working tree while the backend work above
was in review. Fully documented in `design/implementation-progress.md`'s new
"Phase D.1 — Portfolio detail tab merge" section — read that for the real
detail. One bug from that work was caught by the same review pass and fixed
here: `InsidersTab.tsx`'s auto-select-first-holding effect depended on
`portfolio.tsx`'s `selectSymbol`, which was a fresh function on every render,
so the effect re-ran every render (behaviorally harmless, just wasteful) —
`selectSymbol` is now wrapped in `useCallback`. Frontend: `npm run typecheck`
clean, `npm run test` 30/30 passing.

**Still open, unchanged from before**: workstream 2 (live click-test of both
the sync-on-open frontend fix and the new backend sync-before-read behavior)
— still blocked on no browser-automation tool + real prod Plaid credentials in
this environment. Needs the user's own logged-in session.

## Standing constraints — read first, these override default behavior

1. **Do not `git commit` or `git push` anything.** The user's explicit
   instruction mid-project was "dont commit or push anything but continue to
   the next phases." Everything must stay in the working tree until the user
   says otherwise. Verify current state with `git status --porcelain` before
   doing anything — as of this writing: branch `frontend-redesign`, 13
   modified files, nothing staged, nothing committed (see below for the list).
2. **Never echo, log, or write a live secret value anywhere.** Early in the
   original session a `.env` line containing what looked like a live secret
   (`PT...`-style token) was surfaced via a system reminder. It was never
   needed again, but the rule stands: if any `.env` contents are ever
   surfaced, don't repeat the values in chat, files, memory, or subagent
   prompts.
3. **Launching the backend from a Claude Code shell leaks env vars.** Claude
   Code's own `ANTHROPIC_BASE_URL`/`ANTHROPIC_API_KEY` (its Anthropic gateway
   credentials) shadow the app's own `.env`-configured keys if you just run
   `make api` from this shell. Prefix with
   `env -u ANTHROPIC_BASE_URL -u ANTHROPIC_API_KEY` when starting the backend
   from here, e.g. `env -u ANTHROPIC_BASE_URL -u ANTHROPIC_API_KEY make api`.
4. **SignalWire webhook signature verification needs the Dashboard "Signing
   Key", not the API token.** `settings.signalwire_signing_key` ≠
   `settings.signalwire_api_token` — mixing these up was the root cause of a
   401 bug already fixed. Don't reintroduce it.
5. **No browser-automation tool is available in this environment**, and the
   live backend runs with real production Plaid credentials
   (`DEMO_MODE=false` confirmed via `curl` against `/plaid/status` and
   `/auth/me`). You cannot log in or click through screens yourself. Verify
   frontend work via `npm run typecheck`, `npm run test` (27/27 passing as of
   the last full pass), and `npm run export:web` (production build) — and say
   so explicitly rather than claiming visual verification you didn't do.
   Recommend the user do a live pass in their own logged-in session.

## What "Posted" is

A personal finance + portfolio app. Expo/React Native client
(`apps/client/`, web + iOS + Android via `react-native-web`) talking to a
FastAPI backend (`backend/`, Python 3.12, SQLAlchemy async, SQLite/Postgres).
Plaid for banking + some brokerages, Schwab OAuth for Schwab specifically,
Finnhub/Alpaca for market data, Anthropic Claude for a financial-assistant
chat feature reachable from both the web app and an SMS bridge.

## The three workstreams in flight

### 1. Frontend redesign ("The Position Spine") — mostly done

A full visual/structural redesign moving away from a generic fintech/SaaS
template feel. Full detail, rationale, and phase-by-phase status lives in:

- `design/approved-design-system.md` — the approved direction + design
  system (source of truth for tokens, primitives, IA)
- `design/migration-plan.md` — the phased rollout plan (Phases A–F)
- `design/implementation-progress.md` — **the authoritative running log**,
  updated after every phase. Read it in full; don't re-derive status from
  git diffs.

**Status in one line**: Phases A (foundations), B (shell), C (Position Spine
screen), D (remaining core screens migrated to the new design system) are
all functionally done. Nothing has been committed — Phase A/B/C landed in
earlier commits *before* the no-commit instruction was given (see git log:
`5e4cab5`, `df1712f`, etc. are unrelated backend fixes; the redesign commits
are further back), and all of Phase D is sitting uncommitted in the working
tree right now (13 modified files per `git status`).

**The one deliberately-unfinished piece, explicitly confirmed by the user as
next**: collapsing `feed.tsx`, `news.tsx`, `holdings.tsx`, and `insiders.tsx`
from four separate routes into one destination with in-page tabs, per the
approved IA. Right now they're four separate screens all reachable from the
"Explore" dropdown in `apps/client/src/components/AppShell.tsx` (a flat
7-item list: Holdings, Transactions, Subscriptions, Impact feed, News,
Insider activity, Settings). The user said "yes, do that" when last asked
whether to continue into this merge — it has not been started. When you
pick it up:
- Follow `design/approved-design-system.md`'s IA section for the target
  shape (a single "Portfolio detail" destination, tabbed).
- Reuse `apps/client/src/components/spine/Band.tsx` and the `Panel`/
  `StatTile`/`FilterChip`/`useBreakpoint()` primitives already used
  throughout Phase D — don't reinvent layout patterns.
- Do **not** touch chart interaction internals in `stock/[symbol].tsx`
  (`SentimentChart`, `StockPriceChart`, `chartContextRef`) — frozen per
  `design/frontend-audit.md` §3.4/§3.8, already respected during Phase D.
- Two screens (`insiders.tsx`, `stock/[symbol].tsx`) still compute their own
  ad hoc breakpoints via raw `useWindowDimensions` instead of
  `useBreakpoint()` — this was a deliberate, flagged exception (genuine
  content-specific thresholds), not an oversight. Leave as-is unless the tab
  merge naturally touches that code anyway.
- Update `design/implementation-progress.md` with a new phase-D-completion
  entry (or Phase E, depending how you want to label it) when done, same
  format as the existing entries.

### 2. Sync-on-open / real-refresh-triggers-sync (frontend) — done, unverified live

Earlier in this effort, the user asked to fix stale-data-on-open across the
Money and Investing overview pages: opening a page with stale Plaid/Schwab
data should auto-sync, and the on-page refresh button/pull-to-refresh should
always trigger a *real* provider sync, not just re-fetch cached data. This
shipped as `apps/client/src/lib/useConnectionSync.ts` — exports `isStale()`
(5-minute threshold), `targetConnections()` (live-first, demo-fallback), and
a `useConnectionSync({connections, syncFn, invalidateKeys})` hook doing
auto-sync-once-if-stale-on-mount + a manual `sync` mutation that always
force-syncs. It's wired into `apps/client/src/app/index.tsx` (now the
Position Spine screen, replacing separate `money.tsx`/`invest.tsx`) for both
brokerage and money connections. Verified via typecheck/tests/manual read of
the query-key wiring — never click-tested live (see standing constraint #5).
An in-flight `run` skill invocation to actually launch the backend + web
client and click-test this was interrupted by the user's request for this
handoff — **that live verification is still an open TODO** if you have a way
to do it (e.g. the user provides credentials or does it themselves).

### 3. Backend: give the assistant real, always-fresh account-data tools — not started, scoped below

**The user's exact request** (verbatim): *"add some MCP tools for the agent
to actually be able to query all the users' account data without just like
and have it be synced to every time it queries so it's not like outdated
data and make sure that it's available on both the webpage chat and the
messaging chat."*

**Important finding — read before writing any code**: this is *not* a
greenfield feature. The backend already has a real Claude tool-use agent in
`backend/app/services/assistant.py`. Investigate that file first; most of
what's being asked already exists in some form.

#### What already exists

`backend/app/services/assistant.py`:
- `MODEL = "claude-haiku-4-5"`, `MAX_TOOL_ITERATIONS = 6`.
- A `TOOLS` list of **8 native Anthropic tool-use tools** (standard
  `tools=[...]` + `tool_use`/`tool_result` loop, *not* Model Context
  Protocol): `get_money_overview`, `get_recent_transactions`,
  `get_recurring_subscriptions`, `get_portfolio_overview`,
  `get_portfolio_holdings`, `get_impact_feed`, `search_company_news`,
  `get_insider_activity` — plus a restricted `web_search_20250305` tool
  (domain-allowlisted, see `RELIABLE_DOMAINS`).
- `_execute_tool()` dispatches each tool name to an existing read-only
  service function (`get_money_overview`, `get_dashboard`, `get_holdings`,
  `get_money_transactions`, `get_recurring_streams`, `get_feed`,
  `get_insider_analysis` — all pre-existing, imported from
  `app.services.dashboard`, `app.services.money`,
  `app.services.insider_analysis`).
- `run_assistant_turn()` is the actual agentic loop: builds `system` +
  `SECTION_FRAMING` (money/investing/general) + optional sanitized
  `screen_context`, calls `client.messages.create(...)`, loops on
  `stop_reason == "tool_use"` up to `MAX_TOOL_ITERATIONS`, handles
  `refusal`/`pause_turn`/rate-limit/connection/status errors distinctly.
- `send_message()` is the single entry point everything else calls: persists
  the user + assistant `AssistantMessage` rows, calls `run_assistant_turn`,
  commits.

**Both surfaces already call the same `send_message()` — this is the key
fact that simplifies the whole task:**
- **Webpage chat**: `backend/app/api/routes/assistant.py` —
  `GET/POST/DELETE /assistant/messages` — `POST` calls `send_message`
  directly. Frontend side: `apps/client/src/lib/api.ts`'s
  `sendAssistantMessage`, consumed by `AssistantChat.tsx` /
  `AssistantDrawer.tsx` / `app/assistant.tsx`.
- **SMS/messaging chat**: `backend/app/services/sms.py`'s
  `process_inbound_sms()` calls the *same* `send_message()` (see line ~118),
  just with a different `section` (derived via `section_for_sms()`) and a
  `screen_context` noting the channel. The inbound webhook is
  `backend/app/api/routes/signalwire.py` (`POST /webhooks/signalwire`).

  **⚠️ The SMS provider is SignalWire, not Telnyx, despite the README.**
  `backend/app/api/routes/telnyx.py` **does not exist** — there is no such
  file. The actual route is `app/api/routes/signalwire.py`, and the send
  path is `app.providers.signalwire.client.send_sms`. The README's "Telnyx
  SMS local test" section (bottom of `README.md`, still present as of this
  writing) describes the *old* provider and is stale documentation left
  over from before a provider migration (see project memory: "SMS provider
  plan: SignalWire now, Telnyx later" — Telnyx is a *future* switch-back
  target for 10DLC/EIN reasons, not what's running now). **Do not follow the
  README's Telnyx setup steps to test SMS locally** — use the SignalWire
  webhook (`/webhooks/signalwire`), `SIGNALWIRE_*` env vars, and
  `signalwire_signature.py`'s verification instead. Consider updating the
  README's stale section while you're in this area (flagged, not yet done —
  wasn't in scope for the original ask, but it's actively misleading now).

  **Conclusion**: because both channels already funnel through
  `send_message()` → `run_assistant_turn()` → the shared `TOOLS`/
  `_execute_tool()`, *any* tool or sync-freshness improvement made in
  `assistant.py` automatically reaches both the webpage chat and SMS chat
  with no separate integration work needed. You do not need to build or
  wire anything twice.

#### The actual gap to close

None of the 8 existing tools trigger a sync before reading. `_execute_tool`
calls straight into read-only service functions that read whatever is
currently in the DB. If the user hasn't opened the app (which now
auto-syncs stale connections per workstream #2 above) or manually synced
recently, the assistant can answer from stale data — exactly the problem
already solved on the frontend via `useConnectionSync`, but not yet solved
server-side. This is what "make sure it's synced every time it queries" is
asking for.

**Existing sync primitives to reuse (do not reinvent)**:
- `backend/app/services/schwab_sync.py` — `sync_schwab_connection(session,
  connection, idempotency_key, credential_store, oauth_client,
  trader_factory)`
- `backend/app/services/plaid_investments_sync.py` —
  `sync_plaid_investments_connection(session, connection, idempotency_key,
  credential_store, client)`
- `backend/app/services/plaid_sync.py` — `sync_plaid_transactions(...)` (the
  bank/money-side Plaid sync; also has a `sync_transactions` method on some
  class inside the same file — read the whole file, it's short)
- `backend/app/services/brokerage_sync.py` — `sync_brokerage_snapshot(...)`,
  looked like a higher-level orchestrator; read it to see if it already
  wraps per-provider dispatch (would simplify calling from the assistant
  layer to one function instead of branching on `connection.provider`
  yourself)
- `backend/app/services/dashboard.py` — `run_demo_sync(...)` for demo-mode
  connections (mirrors what `connections.py`'s route does when
  `settings.demo_mode and connection.status == "demo"`)
- **The exact per-provider dispatch pattern to copy** is already written in
  `backend/app/api/routes/connections.py`: a `_SYNC_ADAPTERS: dict[str,
  Callable]` keyed by `connection.provider` (`"schwab"` →
  `_run_schwab_sync`, `"plaid_investments"` → `_run_plaid_investments_sync`),
  used by `POST /connections/{connection_id}/sync`. The assistant's
  sync-before-read step should almost certainly reuse this exact adapter
  map/pattern rather than re-deriving it — importing/refactoring it into a
  shared helper both `connections.py` and `assistant.py` can call is
  probably cleaner than duplicating it.
- **Staleness data model**: both `BrokerageConnection` and
  `FinancialConnection` (`backend/app/db/models.py`) have a
  `last_synced_at: Mapped[datetime | None]` column. Mirror the frontend's
  staleness threshold from `apps/client/src/lib/useConnectionSync.ts`'s
  `isStale()` (5 minutes) for consistency between "the page auto-synced
  because it was stale" and "the assistant synced because it was stale" —
  consider whether that threshold constant should be centralized
  (currently only exists frontend-side in TypeScript; the backend has no
  equivalent constant yet).

**Recommended shape** (not yet approved by the user — this is a design
recommendation for the next agent to confirm or adjust, not a decision
already made): before `_execute_tool` reads sync-connection-backed data
(certainly `get_money_overview`, `get_recent_transactions`,
`get_recurring_subscriptions`, `get_portfolio_overview`,
`get_portfolio_holdings`; check whether `get_impact_feed` and
`get_insider_activity` are similarly connection-backed or independently
fresh via direct Finnhub/news-provider fetches — if the latter, they may not
need this treatment), look up the user's relevant connection(s), check
`last_synced_at` staleness, and `await` the matching sync adapter inline
before calling the existing read function — so every tool result reflects
data that was just confirmed fresh. This adds latency to tool calls (a real
Plaid/Schwab network round-trip) — consider whether to sync only if stale
(cheap in the common case) vs. always sync (guarantees freshness but is
slower and hits provider rate limits harder on every single chat turn);
"stale-then-sync" mirrors the frontend pattern and is almost certainly the
right default given the user's own phrasing ("so it's not like outdated
data" — read as "not stale", not literally "sync unconditionally on every
message").

#### Ambiguity to resolve before deep implementation: "MCP tools"

The user said "MCP tools" twice in their request. Model Context Protocol
(MCP) is a distinct Anthropic-ecosystem protocol for exposing tools/
resources to *external* MCP clients (Claude Desktop, other agents, etc.) —
architecturally different from the native Anthropic `tools=[...]` /
`tool_use` mechanism already used in `assistant.py`. Posted's assistant is a
first-party, in-app-only feature with no external MCP client in the
picture — there is no evidence anywhere in this codebase of an intent to
expose these tools to any third-party MCP consumer. The pragmatic read is
that "MCP tools" is being used loosely to mean "more agent tools the AI can
call," not a literal request to stand up an MCP server. **Recommended
default**: keep extending the existing native tool-use `TOOLS`/
`_execute_tool()` in `assistant.py` (same pattern as the 8 tools already
there) rather than building a real MCP server, since a real MCP server
would add an entire new protocol/transport layer with no actual consumer
today. If you want certainty rather than a judgment call, ask the user one
clarifying question before committing significant implementation time to
either path — but don't block the sync-freshness fix on that answer, since
it's valuable and correct under either interpretation.

Also worth a quick judgment call: do the existing 8 tools already cover
"all the user's account data," or is there an obvious gap (e.g. a
connections-status/account-list tool, more granular category/time-range
spending queries)? Skim `apps/client/src/app/settings.tsx`'s connection
lists and the money/portfolio overview screens for anything the assistant
currently can't answer that a user would reasonably ask about, and add 1–2
tools only if there's a clear gap — don't pad the tool list speculatively.

#### Files to touch / reference for this workstream

- `backend/app/services/assistant.py` — the core file: `TOOLS`,
  `_execute_tool()`, `run_assistant_turn()`. Almost all new code goes here.
- `backend/app/api/routes/assistant.py` — webpage chat HTTP surface, likely
  untouched (already correctly wired).
- `backend/app/services/sms.py`, `backend/app/api/routes/signalwire.py` —
  SMS channel, likely untouched (already correctly wired via shared
  `send_message`).
- `backend/app/services/schwab_sync.py`, `plaid_investments_sync.py`,
  `plaid_sync.py`, `brokerage_sync.py` — sync primitives to invoke.
- `backend/app/api/routes/connections.py` — the `_SYNC_ADAPTERS` dispatch
  pattern to reuse/extract into a shared helper.
- `backend/app/db/models.py` — `BrokerageConnection`/`FinancialConnection`
  for `last_synced_at`.
- `backend/app/tests/test_assistant.py` — existing test coverage; extend it
  to cover sync-triggering (e.g. assert a sync adapter is called when a
  connection is stale, assert it's *not* called when fresh, to avoid
  spamming providers on every chat turn during tests).
- `backend/app/tests/test_sms_link.py` — SMS-side tests, may need a new
  case if SMS-triggered assistant calls should be covered explicitly (they
  already reuse `send_message`, so this may already be covered implicitly).
- `apps/client/src/lib/useConnectionSync.ts` — the frontend pattern to
  mirror conceptually (staleness threshold, sync-if-stale-else-skip logic).

## Memory files already available (auto-loaded each session)

Check `MEMORY.md` in the memory directory — as of this writing it references:
- SMS provider plan (SignalWire now, Telnyx later; Telnyx is EIN-free and
  the eventual target once Telnyx premium plan review clears — not urgent).
- Backend gateway env leak (`env -u ANTHROPIC_BASE_URL -u
  ANTHROPIC_API_KEY`), described above.
- SignalWire signing key ≠ API token, described above.

## Suggested order of operations for the next agent

1. Re-read `git status`/`git diff --stat` to confirm nothing has changed
   since this handoff was written, and re-read
   `design/implementation-progress.md` for the latest phase status.
2. Decide (or quickly confirm with the user) the MCP-literal-vs-tool-use
   question above; default to extending native tool use if you need to move
   without waiting on an answer.
3. Implement sync-before-read in `assistant.py`'s `_execute_tool`, reusing
   the existing sync adapters and the `_SYNC_ADAPTERS`-style dispatch from
   `connections.py`. Add/extend tests in `test_assistant.py`.
4. Resume and complete the Portfolio-detail tab merge (Feed/News/Holdings/
   Insiders → one tabbed destination), per `design/approved-design-system.md`
   and the notes under workstream #1 above. Update
   `design/implementation-progress.md` when done.
5. If there's a safe way to do it, actually launch the backend (with the
   `env -u` prefix) and the Expo web client to click-test both the
   sync-on-open frontend fix (workstream #2) and the new assistant
   sync-before-read behavior (workstream #3) live — this has not been done
   yet in this environment for either workstream.
6. Throughout: do not commit or push anything without the user explicitly
   asking for it in that specific moment.
