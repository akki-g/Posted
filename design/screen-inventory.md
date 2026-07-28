# Posted screen inventory

One entry per file in `apps/client/src/app/`. "Layout shape" describes the actual
`useWindowDimensions()`-driven branch points found in the file, not an idealized grid.
Line numbers refer to the file as read during this audit (frontend-redesign branch).

---

## `app/index.tsx` — Portfolio overview ("Dashboard")

- **Purpose / moment**: the web-desktop landing screen — "what a person checks first thing,
  after not looking for a day or two, to know if their investing net worth moved and whether
  anything needs attention." Native platforms never see this screen (line 29-31:
  `Platform.OS !== 'web'` → `<Redirect href="/money"/>`); it is a web-only concept today.
- **Data shown**: total portfolio value, day change, all-time gain, unread event count
  (4 top metric cards); 30-day portfolio value chart with scrub/inspect; Schwab account list
  with per-account day change; top 5 holdings; top 3 impact-feed events; a right-rail
  "Today's debrief" panel (AI summary + top holdings + weekly spending + upcoming recurring).
- **Key interactions**: private-mode toggle (masks dollar figures, line 65-74), "Sync now"
  button + pull-to-refresh (both drive `useConnectionSync`, line 53-61), chart scrub
  (`PortfolioChart`'s `onSelectionChange` feeds live `assistantContext`, line 86-90),
  "All holdings"/"Open feed" text links to `/holdings` and `/feed`.
- **Layout shape**: three width tiers with **locally defined** breakpoints (not from
  `theme/tokens.ts`): `desktop = width >= 1080` (line 39, controls 4-up metric row and
  2-column panels vs. stacked), `sideBySideSidebar = width >= 1680` (line 43, controls
  whether the debrief rail sits beside or under the main column). No distinct "mobile"
  layout exists in this file — mobile users never reach it due to the redirect.
- **Notable state**: loading (`LoadingState`) and error (`ErrorState` with retry) gate the
  whole body on `dashboard.isLoading`/`isError`; demo banner shown when
  `dashboard.data.portfolio.demo_mode`; debrief panel has its own independent loading state
  (`debrief.isLoading`) and a "no AI summary available" fallback text; sync errors are not
  surfaced inline in this screen (contrast with `invest.tsx`, which shows `sync.error.message`).

---

## `app/money.tsx` — Money overview

- **Purpose / moment**: the everyday-finances landing screen; on mobile this is the actual
  app home (`mobileNav`'s "Home" tab points here, `AppShell.tsx` line 69). "What changed in my
  cash position and spending since I last looked."
- **Data shown**: net cash position, weekly spending/income, card balances, monthly recurring
  total; a weekly spending bar chart + category breakdown bars; connected bank/card account
  list; recent transactions; recurring-charge preview.
- **Key interactions**: private-mode toggle; "Manage accounts" → `/settings` (desktop only,
  hidden under `mobile`, line 70-76); "Sync now" via pull-to-refresh only (no explicit header
  sync button, unlike `index.tsx`/`invest.tsx`); on mobile, three quick-action tiles
  (Activity/Recurring/Accounts) replace the desktop's inline links.
- **Layout shape**: genuinely different mobile layout — `mobile = width < 700` (line 34)
  switches to an entirely separate `MobileMoneyOverview` sub-component (line 173-275) with a
  dark hero card, quick-action row, and stacked single-column sections, rather than a
  reflowed desktop grid. `desktop = width >= 1080` (line 33) additionally controls whether
  the desktop 4-up metric row wraps.
- **Notable state**: `query.isLoading`/`isError` gates both mobile and desktop bodies;
  `DemoBanner` shown with a money-specific message when `query.data.demo_mode`; sync errors
  are not surfaced inline here either.

---

## `app/invest.tsx` — Investing

- **Purpose / moment**: a mobile-first investing home (mobile tab bar's "Invest" item points
  here) that also happens to render on desktop with no distinct desktop layout — see gap
  noted below.
- **Data shown**: total portfolio value + today/total-return metrics; largest holdings
  (limit 6); Schwab account list; an "Insider activity & sentiment" promo card linking to
  `/insiders`; a stock search box (`MarketSearch`).
- **Key interactions**: private-mode toggle; "Sync all" button (`useConnectionSync`, disabled
  when no connections, line 139-144, shows `sync.error.message` inline unlike
  `index.tsx`/`money.tsx`); "Connection" link to `/settings`; tapping a holding row (via
  `HoldingsList`) routes to `/stock/[symbol]`.
- **Layout shape**: **no responsive branch at all** — no `desktop`/`mobile` boolean is
  computed from `useWindowDimensions` anywhere in this file (contrast every other primary
  screen). The single-column layout just reflows via `flexWrap` on the metric row. This is
  the one primary screen that doesn't have "genuinely different mobile layouts" that the
  skill doc calls out as already true for Money/Portfolio — worth deciding deliberately
  whether the redesign gives Invest its own desktop treatment or keeps it single-column by
  design (it may be intentionally mobile-first since the bottom nav routes here).
- **Notable state**: `dashboard.isLoading || connections.isLoading` shows `LoadingState`;
  `DemoBanner` with an investing-specific message; sync error text rendered inline
  (`styles.error`, line 150).

---

## `app/transactions.tsx` — Transactions

- **Purpose / moment**: searchable ledger across all connected money accounts — "did that
  charge post, and what else came from this merchant."
- **Data shown**: visible-activity count / visible-outflow total / data-source summary tiles;
  a filterable, searchable list of up to 500 transactions.
- **Key interactions**: free-text search over merchant/description/category (client-side
  `useMemo` filter, line 32-51); 5-way pill filter (All/Spending/Income/Recurring/Pending);
  search box relocates from the section header (desktop) to a dedicated row under the header
  (mobile), lines 87-113.
- **Layout shape**: single `compact = width < 680` boolean (line 25) — hides the third
  summary tile and moves the search input; otherwise no structural mobile/desktop split (no
  separate mobile component, unlike money.tsx).
- **Notable state**: `query.isLoading`/`isError`; no empty-state copy for "0 results after
  filtering" (only `TransactionList`'s generic `emptyLabel` prop would show if the list
  itself were empty — filtering to zero client-side still renders `TransactionList` with an
  empty array, which does show `MoneyLists.tsx`'s built-in empty state, line 68-73).

---

## `app/subscriptions.tsx` — Recurring charges

- **Purpose / moment**: review-before-trusting a detected recurring charge — "what's about
  to bill me, and how confident is Posted that this is really a subscription."
- **Data shown**: estimated monthly/annual commitment, active-stream count, next-expected
  charge; full detected-subscription list; a static "how detection works" panel (3 evidence
  bullets) and a legal-style notice ("detection is not cancellation").
- **Key interactions**: pull-to-refresh only; no filters/search (simplest screen in the app).
- **Layout shape**: `desktop = width >= 900` (2-column layout: list + insights rail vs.
  stacked, line 17) and separately `mobile = width < 700` (line 18) swaps the 3-tile summary
  row for a dark hero card + 2-tile row (`mobileHero`/`mobileSummaryRow`, lines 34-47) — a
  genuinely different mobile layout, similar in spirit to `money.tsx`.
- **Notable state**: `query.isLoading`/`isError`; no explicit empty state for "no recurring
  charges detected yet" beyond `SubscriptionList` rendering nothing (no
  `emptyLabel`-equivalent prop is passed here, unlike `TransactionList`'s call sites) — worth
  checking during redesign since a first-time/no-data user gets a blank panel.

---

## `app/holdings.tsx` — Holdings

- **Purpose / moment**: the full securities table — "let me scan and compare every position,
  sorted, not a grid of cards" (this screen already follows the skill's stated preference for
  a table over a card grid).
- **Data shown**: invested-assets total, security count, largest position + its portfolio
  weight; full holdings table/list with search.
- **Key interactions**: free-text symbol/name search (client `useMemo` filter, line 19-26);
  `MarketSearch` full-width promo above the summary tiles; tapping a row routes to
  `/stock/[symbol]` (non-cash rows only, handled inside `HoldingsList`).
- **Layout shape**: **no page-level responsive branch** — the file itself has no `desktop`/
  `mobile` boolean. The only responsiveness comes from `HoldingsList`'s own internal
  `desktop = width >= 760` check (`HoldingsList.tsx` line 37), which swaps a compact table
  for stacked mobile rows. The 3-tile summary row and search box just wrap/reflow.
- **Notable state**: `query.isLoading`/`isError`; no explicit "0 results for this search"
  empty-state copy (falls through to `HoldingsList` rendering an empty view with nothing
  shown — no message at all, unlike `MoneyLists.tsx`'s transaction empty state).

---

## `app/insiders.tsx` — Insider activity

- **Purpose / moment**: "what are the people who actually run this company doing with their
  own shares, and does that context change how I read the stock." One of the two most complex
  screens in the app (with `stock/[symbol].tsx`).
- **Data shown**: a horizontal watchlist of portfolio holdings with 3-month MSPR + trend
  arrow; for the selected symbol — quote hero with signal pill, 4 summary metrics (latest
  MSPR, 3-month MSPR, net insider shares, 1-month price move), an AI-narrative panel, a
  12-month MSPR sentiment bar chart (scrubbable), a transaction ledger, an evidence-based
  interpretation card, portfolio exposure card, interpretation caveats, and linked recent news.
- **Key interactions**: symbol comes from the `?symbol=` route param; if absent, an effect
  auto-redirects to the first watchlist item (line 61-66, see audit §3.5 for the risk this
  creates); `MarketSearch` in the header (desktop, `width >= 720`) or below it (mobile);
  refresh re-fetches both the watchlist and the selected analysis; the sentiment chart's
  scrub selection feeds `assistantContext` live (lines 74-82); tapping a watch card or a
  linked news row navigates within/away from the screen.
- **Layout shape**: `desktop = width >= 980` (line 44) toggles a 2-column content grid
  (AI/chart/ledger main column + interpretation/exposure/news side column) vs. stacked;
  separately `width >= 720` controls header-vs-inline search placement (line 90-105).
- **Notable state**: two independent loading/error pairs (`watch.*` for the watchlist,
  `analysis.*` for the selected symbol); a "no equity holdings to track yet" empty state
  (lines 146-152) when the watchlist is empty; a "select or search a ticker" empty state
  (lines 155-164) when no symbol is chosen at all; per-section empty states for transactions
  (line 270-277) and recent news (line 360-366); `DemoBanner` when `analysis.data.is_demo`;
  AI-unavailable fallback text distinguishing "not configured" vs. "temporarily unavailable"
  (lines 238-247).

---

## `app/news.tsx` — News stories

- **Purpose / moment**: browse every story feeding the impact feed and open one for the full
  AI-annotated picture, without navigating away (master-detail, not push navigation).
- **Data shown**: story list (`EventList`) with total count; detail panel per selection —
  level pill, headline/summary, portfolio-impact score bar, AI insight, affected holdings,
  "why this score" reasons, source link.
- **Key interactions**: "Refresh providers" button (`refreshNews` mutation + refetch, shows
  provider/fetched/inserted counts or a warning, lines 66-75); selecting a list row loads
  detail in-place (`selectedId` state) rather than navigating to `/event/[id]`; close button
  clears the selection.
- **Layout shape**: `desktop = width >= 920` (line 17) toggles side-by-side list+detail vs.
  stacked (detail presumably appears below/instead-of on narrow widths — no separate mobile
  detail treatment beyond the stack).
- **Notable state**: list-level `feed.isLoading`/`isError`; detail-level
  `detail.isLoading`/`isError` independent of the list; refresh has its own pending/error/
  success text states (lines 66-75) distinct from the list's own loading state.
- **Design inconsistency to note**: this screen's `listPanel`/`detailPanel` styles (lines
  195, 234-241) omit `radius.lg`/`cardShadow` that every other panel in the app uses — see
  `frontend-audit.md` §4.1.

---

## `app/feed.tsx` — Impact feed

- **Purpose / moment**: the ranked, filterable stream of "does this news actually matter to
  my portfolio" — narrower and simpler than `news.tsx` (no detail pane, always routes to
  `/event/[id]` on tap via `EventList`'s default behavior).
- **Data shown**: result count; full event list with score rail, headline, AI insight
  preview, symbols, source.
- **Key interactions**: free-text search (client-side, over headline + security symbols,
  line 31-39); 4-way level filter (all/urgent/important/notable) plus an independent
  "unread only" toggle — both filters are sent to the server as query params
  (`?level=`/`?unread_only=`, line 22-29), unlike transactions' client-side-only filtering.
- **Layout shape**: no responsive branch at all in this file — filters wrap via `flexWrap`.
- **Notable state**: `query.isLoading`/`isError`; no distinct empty state for zero results
  after client-side search narrows a non-empty server response.

---

## `app/assistant.tsx` — Assistant (full-page)

- **Purpose / moment**: the dedicated, full-screen version of "Ask Posted" for users who
  want the whole viewport rather than the docked/floating drawer.
- **Data shown / interactions / state**: entirely delegated to `AssistantChat` (see
  `component-inventory.md`) — this file is a 13-line wrapper providing a static
  `assistantContext` string ("the user opened the full assistant workspace…") and no other
  logic.
- **Layout shape**: whatever `AssistantChat` renders in non-compact mode; no
  `useWindowDimensions` usage in this file.

---

## `app/settings.tsx` — Settings

- **Purpose / moment**: the connections-and-preferences control panel — sign-in identity,
  bank/brokerage link management, SMS linking, notification prefs, and static
  data-handling disclosures. The single screen with the most independent mutation flows
  (9 `useMutation` calls) but the least amount of custom visual design (plain stacked panels).
- **Data shown**: signed-in identity; bank connections list (each with sync/unlink or a DEMO
  badge); Plaid Link readiness + connect button; brokerage connections list (same
  sync/unlink/demo pattern); Schwab readiness + connect/reconnect button (reacts to
  `?schwab=connected|error` redirect params, lines 385-394); Plaid Investments connect
  button; SMS link status (none/pending/verified) with phone/code input flows; push +
  morning-briefing toggles; static security/data-provider disclosure rows.
- **Key interactions**: per-connection sync and unlink (unlink goes through
  `confirmDestructive`'s platform-branched confirm, lines 113-141); Schwab OAuth kickoff
  (opens `authorization_url` in the browser); SMS request-code / verify-code / resend /
  unlink flow; preference `Switch` toggles that immediately mutate.
- **Layout shape**: no responsive branch — single column, `maxWidth: 920` (line 599), same
  on all viewport widths.
- **Notable state**: five independent query loading/error states (connections, schwab
  status, money connections, plaid status, plaid investments status, preferences, sms
  status — 7 total `useQuery` calls); per-row pending labels distinguish which specific
  connection is mid-sync/unlink via `variables === connection.id` checks (lines 240,
  250-253, 319-322, 331-334); inline success/error text for Schwab and SMS flows.
- **Duplication to note**: the banking-connections panel (lines 206-284) and
  investing-connections panel (lines 286-402) are near-identical block structures — see
  `frontend-audit.md` §4.5.

---

## `app/login.tsx` — Login (marketing/sign-in)

- **Purpose / moment**: Posted's only real first-impression surface (per the skill doc, the
  one place a bolder hero moment is earned) — convince + convert a first-time visitor into
  Google OAuth sign-in.
- **Data shown**: static marketing headline/subheadline, a 4-item "what Posted does" feature
  card (banking+investing unified, impact feed, Ask Posted, insider activity), legal
  disclaimer.
- **Key interactions**: "Continue with Google" button (web only — native shows static text
  "Sign-in is available on the web app for now", lines 87-99) triggers `authorizeGoogle`
  mutation and a full-page redirect (`window.location.href`, line 56).
- **Layout shape**: `desktop = width >= 920` (line 46) toggles a two-column hero (copy +
  feature card side-by-side) vs. stacked.
- **Notable state**: redirects immediately to `/` if already signed in (`useEffect`, line
  49-51, so this screen never really "shows" to an authenticated user); `authorize.isPending`
  ("Redirecting…") / `authorize.isError` inline error text.
- **No AppShell** — renders its own `BrandMark` + top nav row directly.

---

## `app/login/callback.tsx` — Login callback

- **Purpose / moment**: the OAuth redirect landing target; not a designed "screen" so much
  as a transient interstitial.
- **Data shown**: "Signing you in…" text, or a cancellation message if `?error=` is present.
- **Key interactions**: none from the user; a `useEffect` reads `?session=`, calls
  `AuthContext.signIn(token)`, and replaces route to `/`.
- **Layout shape**: single centered column, no responsive branching.
- **Notable state**: only two textual states (signing-in vs. error); no loading spinner, no
  `AppShell` (renders directly, matching `login.tsx`).

---

## `app/event/[id].tsx` — Event analysis

- **Purpose / moment**: full-detail deep-dive on a single impact-feed event, reached by
  tapping any `EventList` row that doesn't have an in-place detail pane (i.e. from
  `feed.tsx`, `index.tsx`'s feed panel, or `insiders.tsx`'s linked news rows).
- **Data shown**: level pill, occurred-at time, demo flag; headline/summary; primary source
  + external link; AI insight (if present); numbered "why this matters" reasons; a dark
  portfolio-impact score card (0-100 with confidence %); affected-holdings list with weights;
  a "mark as read" action (only shown when `unread`).
- **Key interactions**: back button (`router.back()`); "Open source" external link
  (`Linking.openURL`); "Mark as read" mutation invalidates `['event', id]`, `['feed']`, and
  `['dashboard']` (so the dashboard's unread-count metric and feed lists both update).
- **Layout shape**: single `flexWrap`-based two-column layout (`mainPanel` flex:2,
  `sidePanel` flex:1, line 118) with no explicit `desktop`/`mobile` boolean — relies entirely
  on flex-wrap to stack on narrow viewports.
- **Notable state**: `query.isLoading`/`isError`; `markRead.isPending` ("Updating…") on the
  action button.
- **Design inconsistency to note**: `mainPanel`/`sidePanel` styles (line 119-120) omit the
  `radius.lg`/`cardShadow` panel treatment used elsewhere — same inconsistency as `news.tsx`,
  see `frontend-audit.md` §4.1.

---

## `app/stock/[symbol].tsx` — Stock research

- **Purpose / moment**: the deepest research surface in the app — quote, full OHLC+indicator
  price chart, earnings, linked news, insider snapshot, position detail, key statistics,
  company profile, and data-provider coverage, all for one ticker. The other most complex
  screen alongside `insiders.tsx`.
- **Data shown**: quote hero (price/change/OHLC/bid-ask/volume, freshness badge); period
  selector (1D/5D/1M/6M/1Y/5Y) driving `StockPriceChart`; earnings table; related news/filings
  list (routes to `/event/[id]`); insider activity snapshot + AI context + transaction rows
  (with a "full analysis" link to `/insiders?symbol=`); position card (if held); key
  statistics (market cap, P/E, dividend yield, beta, 52-week range); company profile
  (sector/industry tags, description, website link); data-provider coverage rows.
- **Key interactions**: period switch refetches history at a different `staleTime`
  (60s for `1D`, 10min otherwise, lines 63-68); refresh button re-triggers `refreshNews` then
  refetches detail/history/insiders; `StockPriceChart`'s pan/zoom/indicator-toolbar
  interactions (see `component-inventory.md`) feed `assistantContext` via the
  `chartContextRef` pattern (audit §3.4); `MarketSearch` appears in the header (`width >=
  760`) or inline below the quote hero otherwise.
- **Layout shape**: `desktop = width >= 980` (line 46) toggles the 2-column content grid
  (earnings/news/insiders main column + position/stats/company/coverage side column) vs.
  stacked; `showHeaderSearch = width >= 760` (line 47) independently controls search
  placement; the price-history section header's caption is hidden below `width >= 520`
  (line 192).
- **Notable state**: `detail.isLoading`/`isError` gates the whole body; `history.*` and
  `insiders.*` have their own independent loading/error states nested inside already-loaded
  `detail.data`; empty-state copy for earnings ("no earnings records are available…"),
  related news ("no normalized portfolio events are linked to this ticker yet"), and insider
  transactions, each via a shared local `EmptyPanel` helper (lines 591-597); `DemoBanner`
  when `detail.data.is_demo`; a freshness badge with 5 distinct labels
  (`freshnessLabel`, lines 599-605).
