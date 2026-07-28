# Posted component inventory

One entry per file in `apps/client/src/components/`. "Used by" lists every screen/component
call site found during this audit. Line numbers refer to the files as read on the
`frontend-redesign` branch.

---

## `AppShell.tsx`

- **Purpose**: the single layout shell for every authenticated screen — desktop
  sidebar/topbar/bottom-nav switch, auth gate, account menu, "Ask Posted" toggle + drawer
  host, pull-to-refresh wiring, and page heading (`eyebrow`/`title`).
- **Props**: `title: string`, `eyebrow?: string`, `children: ReactNode`,
  `headerAction?: ReactNode`, `scroll?: boolean` (default `true`), `refreshing?: boolean`,
  `onRefresh?: () => void`, `assistantContext?: string | (() => string)`,
  `assistantContextLabel?: string`.
- **Used by**: every route under `app/` except `login.tsx` and `login/callback.tsx` (14
  call sites).
- **Notable internals**: `assistantSectionForPath(pathname)` (lines 87-107) derives which
  assistant section pill is preselected purely from the URL, independent of each screen's
  own `setAssistantSection` call in `lib/assistantSection.ts` — two parallel mechanisms
  driving the same concept (see `frontend-audit.md` for why this matters). The auth-gate
  `useEffect` (lines 129-133) and loading/redirect render branch (lines 163-171) are the
  single most safety-critical piece of logic in this file (see audit §3.2).
- **Duplication note**: the 38×38 `assistantButton`/`avatar`-adjacent icon-button sizing
  pattern used elsewhere (index/money/invest icon buttons) is not itself defined here, but
  `AppShell`'s own `avatar` (34×34, lines 448-455) and `assistantButton` (height 38, lines
  431-443) are two more instances of undersized touch targets in the same family.

---

## `AssistantChat.tsx`

- **Purpose**: the actual chat UI (conversation history, section pills, suggested prompts,
  composer) — shared verbatim between the full-page `assistant.tsx` and the docked/floating
  `AssistantDrawer`.
- **Props**: `compact?: boolean`, `initialSection?: AssistantSection`,
  `screenContext?: string | (() => string)`.
- **Used by**: `app/assistant.tsx` (non-compact), `AssistantDrawer.tsx` (compact).
- **Notable internals**: `suggestedPrompts(section, screenContext)` (lines 24-65) does
  substring-matching on the *rendered* `screenContext` copy (e.g. checks for `'technical
  indicator'`/`'reviewing insider activity'` in the lowercased string) to decide which
  starter prompts to show — this is a real coupling between the assistant-context prose
  written into each screen's `AppShell` call and this component's prompt logic. Changing the
  wording of a screen's `assistantContext` string (even for tone/style reasons during
  redesign) can silently change which suggested prompts appear. `pending` local state
  (optimistic user message shown before the mutation resolves, lines 73, 89-99) and
  `send`/`clear` mutations both invalidate `['assistant-messages']`.

---

## `AssistantDrawer.tsx`

- **Purpose**: positions `AssistantChat` as either a fixed right-hand dock (`width >=
  breakpoints.assistantDock`, 1600px) or a floating panel — full floating card on wider
  compact widths, or a bottom-sheet-style floating panel that floats above the mobile bottom
  tab bar (`width < breakpoints.mobileNav`, 920px), lines 21-25.
- **Props**: `contextLabel: string`, `initialSection: AssistantSection`,
  `onClose: () => void`, `screenContext: string | (() => string)`.
- **Used by**: `AppShell.tsx` only (rendered conditionally when `assistantOpen`).
- **Notable internals**: three near-duplicate positioning styles (`panelDocked`,
  `panelFloating`, `panelFloatingCompact`, lines 81-117) each hand-tuning
  width/height/shadow — a reasonable place to consolidate shared shadow/radius values once a
  new design system exists, though the three positioning *strategies* themselves are
  legitimately different (dock vs. floating-desktop vs. floating-above-tab-bar) and should
  stay distinct.

---

## `BrandMark.tsx`

- **Purpose**: the small teal square + two bars mark, with or without the "POSTED" wordmark.
- **Props**: `compact?: boolean`.
- **Used by**: `AppShell.tsx` (both sidebar and mobile-topbar contexts), `login.tsx` (nav
  row).
- **Notable**: no logic; pure presentation; every color reference goes through
  `theme/tokens.ts`. One of the cleanest, most reusable components in the codebase.

---

## `DebriefPanel.tsx`

- **Purpose**: the dashboard's right-rail "Today's debrief" — AI summary, top-4 holdings by
  weight, weekly spending vs. income + top-3 categories, and up-to-3 upcoming recurring
  charges.
- **Props**: `debrief?: MorningDebriefResponse`, `debriefLoading: boolean`,
  `holdings: HoldingSummary[]`, `money: MoneyOverviewResponse | undefined`,
  `moneyLoading: boolean`, `privateMode: boolean`.
- **Used by**: `app/index.tsx` only.
- **Notable**: purely presentational given its props — all fetching/loading-state
  bookkeeping happens in `index.tsx` and is threaded in. Safe to restyle freely; the
  `privateMode` masking convention (`privateMode ? '$••••' : money(x)`) matches the same
  convention used inline in `index.tsx`/`money.tsx`/`invest.tsx` but is not itself a shared
  helper — each screen re-implements the `privateMode ? mask : money(x)` ternary locally
  rather than calling one `concealed()`-style utility (money.tsx does define a local
  `concealed` closure, line 56, but it isn't shared with `DebriefPanel` or the other two
  screens).

---

## `EventList.tsx`

- **Purpose**: the feed/dashboard event row list — score rail (colored by level), level
  pill, relative time, unread dot, headline, AI-insight preview, symbols/source footer,
  impact score block, chevron.
- **Props**: `events: EventSummary[]`, `onSelect?: (id: string) => void`,
  `selectedId?: string`.
- **Used by**: `app/index.tsx` (top 3 events), `app/feed.tsx` (full filtered list),
  `app/news.tsx` (full list, with `onSelect`/`selectedId` for master-detail).
- **Notable**: when `onSelect` is omitted it defaults to `router.push('/event/[id]')`
  itself (lines 23-27) — i.e. this component owns its own default navigation behavior rather
  than the parent always deciding. Fine as-is, but worth knowing if a redesign wants every
  navigation decision centralized in the route file.

---

## `HoldingsList.tsx`

- **Purpose**: the securities table/list — desktop table with sortable-looking columns
  (Security/Quantity/Last price/Market value/Today/Weight) vs. a compact mobile row layout,
  switched by its own internal breakpoint.
- **Props**: `holdings: HoldingSummary[]`, `limit?: number`, `compact?: boolean`.
- **Used by**: `app/index.tsx` (`limit={5} compact`), `app/invest.tsx` (`limit={6}`),
  `app/holdings.tsx` (full list).
- **Notable internals**: **owns its own responsive breakpoint** (`desktop = width >= 760`,
  line 37) independent of every page-level breakpoint discussed in the audit — i.e. it can
  disagree with its parent screen about what counts as "desktop" (e.g. inside `holdings.tsx`,
  which has no page-level breakpoint of its own at all). `AssetBadge` (lines 10-24) special-
  cases the literal symbol `'CASH'`; every other symbol goes through `symbolColor()`
  (`lib/symbolColor.ts`) for a deterministic hash-based color. Cash rows are non-interactive
  (`onPress: undefined`, `accessibilityRole: undefined`, lines 47-57, 92-102) — a design
  decision to keep, not an oversight.

---

## `MarketSearch.tsx`

- **Purpose**: the ticker/company search box, in three visual modes: full promo block (dark,
  with copy), `compact` (header-embedded, no copy), and `compact` at narrow mobile widths
  (`mobileCompact`).
- **Props**: `compact?: boolean`, `initialValue?: string`,
  `destination?: 'stock' | 'insiders'`.
- **Used by**: `app/invest.tsx` (full promo), `app/holdings.tsx` (full promo),
  `app/insiders.tsx` (`compact`, `destination="insiders"`), `app/stock/[symbol].tsx`
  (`compact`).
- **Notable internals**: 240ms debounce on the query (line 40-43); `results` are absolutely
  positioned with hand-tuned `zIndex` (1100/1110/1120, lines 172-227) that must stay above
  whatever container each call site wraps it in — see audit §3.10 for the cross-file z-index
  fragility this creates. `onBlur` uses a 180ms `setTimeout` (line 96) purely to let a result
  tap register before the dropdown unmounts — a real (if small) piece of interaction logic
  a visual restyle must not remove while "cleaning up" the blur handler.

---

## `MoneyLists.tsx`

Three named exports, all pure presentational list renderers:

- **`MoneyAccountList({ accounts })`** — bank/card account rows with a credit-utilization
  bar for liability accounts (computed inline, lines 23-26). Used by `app/money.tsx` (both
  desktop and `MobileMoneyOverview`).
- **`TransactionList({ transactions, emptyLabel? })`** — transaction rows with
  transfer/inflow/outflow icon variants, a pending badge, and a `width >= 720` toggle for
  showing the category badge column (line 66-67, its own independent breakpoint, separate
  from any page-level one). Used by `app/money.tsx`, `app/transactions.tsx`.
- **`SubscriptionList({ streams })`** — recurring-charge rows with next-expected-date and
  confidence %. Used by `app/money.tsx`, `app/subscriptions.tsx`. **No `emptyLabel`-style
  prop** — unlike `TransactionList`, there is no built-in empty state here, so a
  first-time/no-subscriptions user sees a blank panel wherever this is used (flagged in
  `screen-inventory.md` under `subscriptions.tsx`).
- **Duplication note**: all three share the same row anatomy (icon block, two-line identity,
  right-aligned amount block) reimplemented three times with separate style objects rather
  than one shared `ListRow` primitive with icon/identity/amount slots.

---

## `PlaidLinkButton.tsx` / `PlaidLinkButton.native.tsx`

- **Purpose**: initiates Plaid Link for **money/banking** connections, exchanges the
  resulting public token, triggers an immediate sync, and shows busy/error/success text.
  Two files resolved by Expo's platform-extension convention: `.tsx` (web, uses
  `react-plaid-link`'s `usePlaidLink` hook) and `.native.tsx` (iOS/Android, uses
  `react-native-plaid-link-sdk`'s `createPlaidLinkSession`).
- **Props**: `disabled?: boolean` (both files).
- **Used by**: `app/settings.tsx` (banking connections panel).
- **Duplication note**: ~90% identical — same `container`/`button`/`help`/`error`/`success`
  styles, same button copy, same success-message construction
  (`Connected and imported N transactions…`), same `refreshMoneyQueries` invalidation set.
  The only real differences are the SDK-specific token/session API shape. A redesign touching
  this button's visuals must edit **both files** identically (audit §3.7); consider whether a
  shared presentational sub-component (button + help/error/success text) wrapping two thin
  platform-specific "open Link" hooks would remove the duplication without touching the SDK
  boundary.

---

## `PlaidInvestmentLinkButton.tsx`

- **Purpose**: the brokerage-side sibling of `PlaidLinkButton` — same shape, but for
  **investing/Plaid-Investments** connections (`exchangePlaidInvestmentsToken`, syncs via
  `api.sync` rather than `api.syncMoneyConnection`).
- **Props**: `disabled?: boolean`.
- **Used by**: `app/settings.tsx` (investing connections panel).
- **Notable**: web-only file (no `.native.tsx` sibling exists for this one) — i.e. connecting
  a brokerage via Plaid Investments is not available on native today. Same ~90%-duplicate
  relationship to `PlaidLinkButton.tsx` as that file has to its own native sibling: identical
  container/button/help/error/success styling and copy pattern, different endpoint/mutation
  wiring.

---

## `PortfolioChart.tsx`

- **Purpose**: the dashboard's 30-day portfolio-value line chart with scrub-to-inspect,
  gradient fill, crosshair, and a momentum-colored dot.
- **Props**: `points: ChartPoint[]`, `onSelectionChange?: (point: ChartPoint | null) => void`.
- **Used by**: `app/index.tsx` only.
- **Notable internals**: `useChartScrub(points.length, 'point')` drives the selection
  index; `momentumColor()` (`lib/chartMomentum.ts`) colors the crosshair dot based on local
  trend around the selected point, independent of the dashboard's own positive/negative
  palette elsewhere. `onSelectionChange` firing is the direct source of `index.tsx`'s live
  `assistantContext` interpolation (audit §3.4) — the visual layer (SVG paths, gradient,
  colors) is safe to redesign; the scrub hook wiring and the accessibility props
  (`accessibilityRole="adjustable"`, `accessibilityValue`, `onAccessibilityAction`, lines
  166-173) must be preserved.
- **Empty state**: "Portfolio history unavailable… Sync your portfolio to begin tracking its
  movement" when fewer than 2 points (lines 53-60).

---

## `StockPriceChart/` (colocated component + hook/type siblings)

The most complex component in the app; the skill doc names this directory as the pattern to
match for future complex components (own hook/types colocated with the component).

- **`index.tsx`** — the composed chart: resolution switcher (source/5m/15m/1w bar
  aggregation, `aggregateBars`, lines 50-66), indicator instance management (add/remove/
  update params, lines 296-334), signal computation (crossovers/RSI zone exits/MACD/
  stochastic crosses via `lib/indicators/signals.ts`), pan/zoom (`useChartZoom`) composed
  with scrub (`useChartScrub`), and the `onContextChange` callback that feeds
  `stock/[symbol].tsx`'s assistant context (lines 253-294 — this is the single densest piece
  of business logic disguised as a "chart" in the whole app; see audit §3.4/§3.8).
  **Props**: `points: PriceBar[]`, `sourceInterval: '1Min' | '1Day'`,
  `onContextChange?: (context: string) => void`. **Used by**: `app/stock/[symbol].tsx` only.
- **`IndicatorToolbar.tsx`** — the add/remove/configure UI for indicator instances, plus
  signal-rule/direction mute toggles. Consumed only by `index.tsx`.
- **`OscillatorPanel.tsx`** — renders sub-panels for oscillator-kind indicators (RSI,
  stochastic, MACD) below the price panel, each with its own settings popover.
- **`PricePanel.tsx`** — the actual OHLC/line price panel with overlay indicator lines,
  signal markers, and the scrub crosshair; exports `priceToY` used by `index.tsx`'s own
  `chartGeometry`.
- **`RangeBrush.tsx`** — the bottom mini-map/brush control that sets the zoom range.
- **`ParamPopover.tsx`** — the per-indicator parameter-editing popover shared by toolbar and
  oscillator panel settings.
- **`formatting.ts`** (+ `formatting.test.ts`) — `formatAxisDate`, `formatTrackingDate`,
  `formatVolume` — pure formatting helpers, already unit-tested; safe to leave as-is.
- **Redesign guidance**: the visual layer (line/candlestick styling, panel chrome, toolbar
  button look) is freely restylable; the indicator/zoom/scrub/signal computation and the
  `onContextChange` callback's informational content must be preserved (see audit §3.8).

---

## `ui.tsx` — shared primitives

- **`SectionHeader({ title, caption?, action? })`** — the title+caption+trailing-action row
  used at the top of nearly every panel. Used in essentially every screen with a panel
  (index, money, invest, transactions, subscriptions, holdings, insiders, stock). One of the
  best-adopted shared primitives in the app — **note it is always placed inside a
  hand-rolled panel container** (see audit §4.1) rather than a shared `Panel`, so the
  header is shared but its usual wrapper is not.
- **`ActionButton({ label, onPress, icon?, disabled? })`** — the filled teal CTA button
  (e.g. "Sync now", "Sync all", "Manage accounts"). Used in `index.tsx`, `money.tsx`,
  `invest.tsx`.
- **`DemoBanner({ message? })`** — full-width "DEMO" badge + message banner. Default message
  is hardcoded to a Schwab-specific string (line 55: `'Sample portfolio and events. Connect
  Schwab to replace this data.'`) even though it's reused for money/stock/insiders contexts
  that always pass their own `message` override — the default itself is leaky/investing-
  specific and should either be made generic or required (no default) once promoted further.
  Used by `index.tsx`, `money.tsx`, `invest.tsx`, `stock/[symbol].tsx`, `insiders.tsx`.
- **`LoadingState({ label? })`** — centered spinner + label in a bordered box. Default label
  ("Loading portfolio") is also investing-specific; every non-investing call site overrides
  it explicitly, so the same "leaky default" pattern as `DemoBanner`. Used everywhere a query
  is in flight (10+ call sites across nearly every screen and `AssistantChat`).
- **`ErrorState({ message, retry })`** — bordered error box with a retry button. Used
  alongside `LoadingState` at nearly every query call site.
- **`LevelPill({ level })`** — urgent/important/notable/informational colored pill. Used by
  `EventList`, `event/[id].tsx`, `news.tsx`.
- **Not yet present but implied by duplication findings**: `Panel`/`Card`, `StatTile`/
  `MetricCard`, `IconButton`, `HeroPanel`, `ConnectionRow`, `TextLinkAction` — see
  `frontend-audit.md` §4-5 and `reusable-foundations.md` for the case for promoting each.
