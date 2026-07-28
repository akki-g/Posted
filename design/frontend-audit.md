# Posted frontend audit — architecture map, risk areas, redesign boundaries

Scope: `apps/client/src/` on branch `frontend-redesign`, read-only audit. Paths below are
relative to `apps/client/src/` unless given in full. Companion documents:
`design/screen-inventory.md`, `design/component-inventory.md`, `design/reusable-foundations.md`.

## 1. High-level architecture

- **Router**: Expo Router file-based routing. `app/_layout.tsx` wraps everything in
  `SafeAreaProvider` → `QueryClientProvider` (single `QueryClient` with
  `staleTime: 30_000, retry: 1, refetchOnWindowFocus: false`) → `AuthProvider` → `Stack`
  (`headerShown: false`, `animation: 'fade'`). Every screen except `login.tsx` and
  `login/callback.tsx` renders inside `AppShell`.
- **Shell**: `components/AppShell.tsx` owns navigation chrome (desktop sidebar vs. mobile
  bottom tab bar), the top bar, the account menu, the "Ask Posted" toggle, the auth gate,
  and hosts `AssistantDrawer`. Pages only supply `title`, `eyebrow`, `children`,
  `headerAction`, `scroll`, `refreshing`/`onRefresh`, and `assistantContext(Label)`.
- **Data layer**: `lib/api.ts` (`api.*`) covers dashboard/holdings/feed/connections/money/
  settings/assistant/SMS endpoints; `lib/marketApi.ts` (`marketApi.*`) covers stock search,
  quotes, history, insiders, and the news-refresh trigger used by the stock/insiders screens.
  Both are thin wrappers around one `request<T>()` in `api.ts` (bearer token from
  `lib/auth.ts` + `credentials: 'include'` for the Google OAuth cookie flow).
- **Auth**: `lib/AuthContext.tsx` holds a single TanStack Query (`['auth-me']` →
  `api.me()`), gated by `hasToken` (`typeof window !== 'undefined'`, i.e. web-only — see
  §4.9). `lib/auth.ts`'s `getToken`/`setToken` only touch `window.localStorage` and are
  no-ops off web, so **native (iOS/Android) has no persisted session today**; this is
  pre-existing and out of scope for a visual redesign, but any redesign work that touches
  auth-adjacent UI (login, settings account row) should not assume it works on native.
- **Assistant**: a single `AssistantChat` component renders both the full-page
  `assistant.tsx` and the floating/docked `AssistantDrawer`. Screens feed it a
  `screenContext` string (see §4.4) that becomes `screen_context` in
  `api.sendAssistantMessage`. `lib/assistantSection.ts` is a tiny external store
  (`useSyncExternalStore`) that screens call via `setAssistantSection('money' |
  'investing' | 'general')` in a `useEffect` on mount — this drives which section pill
  is preselected in the assistant, independent of the `assistantContext` string.
- **Theme**: `theme/tokens.ts` — flat `colors`, `spacing`, `radius`, `cardShadow`,
  `breakpoints` (`mobileNav: 920`, `assistantDock: 1600`), `type` (font sizes). No dark-mode
  variants; no semantic re-export layer (screens import `colors.teal` etc. directly).
- **Chart interaction primitives** (`lib/chartScrub.ts`, `chartZoom.ts`, `chartInteraction.ts`,
  `chartMomentum.ts`) are shared, headless hooks (pan/pointer handling, index-for-x math,
  momentum-color lookup) consumed by `PortfolioChart`, `StockPriceChart`, and the inline
  `SentimentChart` in `insiders.tsx`. These are already properly factored out of the visual
  layer — see `design/reusable-foundations.md` §2.

## 2. Route → layout → components → queries → endpoints map

| Route | AppShell mode | Key shared components | Query keys | Endpoints (via `api`/`marketApi`) |
|---|---|---|---|---|
| `app/index.tsx` (web-only; native `<Redirect href="/money"/>`, line 29-31) | scroll, `onRefresh` | `DebriefPanel`, `EventList`, `HoldingsList`, `PortfolioChart`, `ui.{ActionButton,DemoBanner,ErrorState,LoadingState,SectionHeader}` | `['dashboard']`, `['connections']`, `['morning-debrief']`, `['money-overview']` | `GET /dashboard`, `GET /connections`, `GET /feed/debrief`, `GET /money/overview`; `useConnectionSync` → `POST /connections/{id}/sync` |
| `app/money.tsx` | scroll, `onRefresh` | `MoneyAccountList`/`TransactionList`/`SubscriptionList` (`MoneyLists.tsx`), `ui.*` | `['money-overview']`, `['money-connections']` | `GET /money/overview`, `GET /money/connections`; `useConnectionSync` → `POST /money/connections/plaid/{id}/sync` |
| `app/invest.tsx` | scroll, `onRefresh` | `HoldingsList`, `MarketSearch`, `ui.*` | `['dashboard']`, `['connections']` | same as index.tsx sync path (`api.sync`) |
| `app/transactions.tsx` | scroll (no refresh) | `TransactionList`, `ui.{ErrorState,LoadingState,SectionHeader}` | `['money-transactions']` | `GET /money/transactions?limit=500` |
| `app/subscriptions.tsx` | scroll, `onRefresh` | `SubscriptionList`, `ui.*` | `['subscriptions']` | `GET /money/subscriptions` |
| `app/holdings.tsx` | scroll (no refresh) | `HoldingsList`, `MarketSearch`, `ui.*` | `['holdings']` | `GET /holdings` |
| `app/insiders.tsx` | scroll, `onRefresh`, custom `assistantContext` | `MarketSearch`, `ui.{DemoBanner,ErrorState,LoadingState,SectionHeader}`, local `SentimentChart`/`WatchCard` | `['portfolio-insiders']`, `['market-insiders', symbol]` (shared cache key with stock screen — see §4.7) | `GET /market/insiders/portfolio`, `GET /market/stocks/{symbol}/insiders` |
| `app/news.tsx` | scroll, `onRefresh` | `EventList`, `ui.{ErrorState,LevelPill,LoadingState}` | `['feed','news-tab']`, `['event', selectedId]` | `GET /feed?limit=100`, `GET /feed/{id}`, `POST /feed/refresh` (invalidates `['feed']`) |
| `app/feed.tsx` | scroll (no refresh) | `EventList`, `ui.{ErrorState,LoadingState}` | `['feed', filter, unreadOnly]` | `GET /feed?level=…&unread_only=…` |
| `app/assistant.tsx` | scroll, custom `assistantContext` | `AssistantChat` | `['assistant-messages']` | `GET/POST/DELETE /assistant/messages` |
| `app/settings.tsx` | scroll (no refresh) | `PlaidLinkButton`, `PlaidInvestmentLinkButton`, `ui.{ErrorState,LoadingState,SectionHeader}` | `['connections']`, `['schwab-status']`, `['money-connections']`, `['plaid-status']`, `['plaid-investments-status']`, `['preferences']`, `['sms-link-status']` | `GET /connections/schwab/status`, `GET /money/connections/plaid/status`, `GET /connections/plaid-investments/status`, `GET/PUT /settings`, `GET /connections/schwab/authorize`, `POST /connections/{id}/sync`, `POST /money/connections/plaid/{id}/sync`, `DELETE /connections/{id}`, `DELETE /money/connections/plaid/{id}`, `GET/POST/DELETE /settings/sms/*` |
| `app/login.tsx` | **no AppShell** | `BrandMark` | none | `GET /auth/google/authorize` (redirect) |
| `app/login/callback.tsx` | **no AppShell** | none | none (reads `useLocalSearchParams`, calls `AuthContext.signIn`) | none |
| `app/event/[id].tsx` | scroll, custom headerAction (back button) | `ui.{ErrorState,LevelPill,LoadingState}` | `['event', id]` | `GET /feed/{id}`, `POST /feed/{id}/read` (invalidates `['event', id]`, `['feed']`, `['dashboard']`) |
| `app/stock/[symbol].tsx` | scroll, `onRefresh`, custom `assistantContext` (function form) | `MarketSearch`, `StockPriceChart`, `ui.*` | `['market-stock', symbol]`, `['market-history', symbol, period]`, `['market-insiders', symbol]` | `GET /market/stocks/{symbol}`, `GET /market/stocks/{symbol}/history?period=`, `GET /market/stocks/{symbol}/insiders`, `POST /feed/refresh` |

`AuthContext` additionally owns `['auth-me']` → `GET /auth/me`, consumed indirectly by
every screen through `useAuth()`/`AppShell`.

**Cross-screen cache coupling worth knowing before touching either screen**: `insiders.tsx`
(line 53-57) and `stock/[symbol].tsx` (line 69-74) both key their insider-analysis query as
`['market-insiders', symbol]` against the same `marketApi.insiders(symbol)` call — they share
one cache entry. Changing the query params or response shape consumed by one screen changes
what the other reads too.

## 3. Safe-to-restyle-freely vs. tightly-coupled areas

### Safe (pure presentation, no state/business logic of its own)
- All `StyleSheet.create({...})` blocks in every route file — none encode behavior.
- Leaf list/row renderers: `EventList`, `HoldingsList`, `MoneyLists.tsx`'s three exports,
  `DebriefPanel`'s render tree (it receives already-fetched data as props), `BrandMark`,
  and `ui.tsx`'s `LevelPill`/`SectionHeader`/`DemoBanner`/`LoadingState`/`ErrorState`/
  `ActionButton`. These take data via props and format/lay it out; restyle freely as long as
  the prop contracts (names/shapes) and call sites stay in sync.
- `login.tsx`'s entire visual layer — the skill doc explicitly calls this out as the one
  screen allowed a bolder hero moment. Its only real logic is the `authorize` mutation
  (`api.authorizeGoogle`, line 53-58) and the redirect-if-already-signed-in `useEffect`
  (line 49-51); both must stay wired but everything visual is free game.
- The visual/paint layer of `PortfolioChart` and `StockPriceChart` (colors, stroke widths,
  gradients, dot styling, panel chrome) — separable from the interaction hooks they call
  (see §3, tightly-coupled list below).
- Settings' `Switch` controls' visual chrome — the `value`/`onValueChange` wiring to
  `updatePreference` (settings.tsx line 168-172) must stay intact, but the control's look is
  free.

### Tightly coupled — handle carefully during redesign
1. **`useConnectionSync` (`lib/useConnectionSync.ts`)**, wired into `index.tsx` (line 53-61),
   `invest.tsx` (line 31-39), and `money.tsx` (line 42-55). It auto-syncs once per mount if
   any live (non-demo) connection's `last_synced_at` is stale (>5 min, `AUTO_SYNC_STALE_MS`),
   and exposes a `mutate()` a page's "Sync now" button / pull-to-refresh can call
   unconditionally. The `autoSyncAttempted` ref + `eslint-disable-next-line
   react-hooks/exhaustive-deps` on line 64 are deliberate — they ensure the auto-sync effect
   fires exactly once per "connections finished loading" event, not on every subsequent
   re-render. A restyle that:
   - drops `disabled={sync.isPending}` from the sync button,
   - stops wiring `onRefresh`/`refreshing` through to `AppShell`, or
   - changes `invalidateKeys` while copy-pasting the pattern to a new screen
   will silently break dedup/staleness behavior without any visible error. Treat this hook's
   call signature and each screen's `invalidateKeys` array as load-bearing, not decorative.
2. **`AppShell`'s auth gate** (`AppShell.tsx` lines 129-133, 163-171): while `isLoading` or no
   `user`, it renders only a centered `ActivityIndicator` and never renders `children`; a
   `useEffect` redirects to `/login` once loading finishes with no user. Any redesign of
   `AppShell` must preserve this exact ordering (block-then-redirect, not
   render-then-hide) — moving this logic to individual pages, or letting `children` render
   before the gate resolves, would introduce an authenticated-content flash.
3. **`index.tsx`'s web-only branch** (line 28-34): non-web platforms get `<Redirect
   href="/money"/>` before the dashboard ever mounts. `AppShell.tsx`'s `mobileNav` array
   (line 68-73) independently points its "Home" tab at `/money`, not `/`. A redesign must
   keep these two facts in sync — the dashboard/"Portfolio overview" screen is a web-desktop
   concept only; there is no dashboard-equivalent screen on mobile today by design.
4. **Assistant context strings baked into JSX** — `assistantContext` on `AppShell` is a
   real data pipe, not copy: it flows to `AssistantDrawer` → `AssistantChat` →
   `api.sendAssistantMessage(message, section, screenContext)`. Several screens build this
   string dynamically from live component state:
   - `index.tsx` lines 86-90 interpolate `portfolioInspection` (the chart-scrub selection).
   - `insiders.tsx` lines 74-82 interpolate `sentimentInspection` and the current `symbol`.
   - `stock/[symbol].tsx` lines 49-56 use a `chartContextRef` **mutable ref**, updated
     imperatively by `StockPriceChart`'s `onContextChange` callback (line 227-230), read
     lazily inside `getAssistantContext` only when needed — deliberately not reactive state,
     to avoid re-rendering the page on every chart-drag frame (`StockPriceChart` already
     recomputes indicator series/geometry on every scrub tick). A restyle of the chart
     interaction (e.g., changing when selection fires, or turning the ref into `useState`)
     will change assistant answer quality without any visual symptom. Preserve the
     callback-firing semantics even while changing the chart's paint layer.
5. **Insiders' default-symbol redirect** (`insiders.tsx` lines 61-66): a `useEffect` calls
   `router.replace` to select the first portfolio holding's symbol when none is in the URL.
   This interacts with any new "no selection" empty state — a restyle adding a richer empty
   state should account for the brief empty-state flash before this redirect fires (or
   convert the flow to avoid the redirect entirely, but that's a logic change beyond
   redesign scope).
6. **`settings.tsx`'s `confirmDestructive`** (lines 113-127): branches to
   `window.confirm` on web vs. `Alert.alert` on native because `Alert.alert` is a no-op on
   `react-native-web`. Any redesign that replaces these with a custom modal must reimplement
   this platform branch, not just restyle the existing calls.
7. **`PlaidLinkButton` has two platform-specific files** — `PlaidLinkButton.tsx` (web,
   `react-plaid-link`) and `PlaidLinkButton.native.tsx` (iOS/Android,
   `react-native-plaid-link-sdk`) — resolved automatically by Expo's platform extension
   convention. They are ~90% identical JSX/styles (see `design/component-inventory.md`).
   Visual changes must be applied to **both** files or they will drift.
8. **`StockPriceChart`'s colocated hook/type pattern** (`components/StockPriceChart/`) is
   the one component explicitly named in the skill doc as the pattern to match for future
   complex components. Its internal state (`instances`, `resolution`, `openSettings`,
   `mutedSignalRules/Directions`) drives both the visual indicator toolbar and the
   assistant-context string (§3.4) — a redesign can change the toolbar/panel visuals but
   must keep `onContextChange` firing with equivalent informational content.
9. **Native session persistence gap** (`lib/auth.ts` lines 5-8, `AuthContext.tsx` line 19):
   `getToken()`/`hasToken` are web-`localStorage`-only. Not something to silently "fix" as
   part of a visual redesign, but worth knowing before redesigning `login.tsx`/native flows
   — there's currently no persisted-session UI state to design for on native.
10. **`MarketSearch`'s absolute-positioned results dropdown** relies on hand-tuned `zIndex`
    values that are inconsistent across call sites (root `zIndex: 1100` /
    `searchWrap: 1110` / `results: 1120` in `MarketSearch.tsx` lines 172-227; `AppShell`
    `pageHeader` at `zIndex: 1000`, `insiders.tsx` `headerActions`/`mobileSearch` both at
    `1100`, `AssistantDrawer` panel at `3000`). This is a fragile ad hoc stacking order, not
    a portal/overlay abstraction — restructuring any container that wraps a `headerAction`
    slot (e.g. wrapping it in a new `View` for spacing) can silently break which layer paints
    on top. Flag for conscious re-verification after any header/layout restructuring, and
    consider this a good candidate to fix properly (see `reusable-foundations.md`) rather
    than blindly preserve.

## 4. Duplication findings (see `component-inventory.md` for full detail)

Summarized here; each is cited with file:line in the component inventory.

1. **The bordered/rounded/shadowed "panel" container** —
   `{ borderWidth:1, borderColor: colors.line, backgroundColor: colors.surface,
   borderRadius: radius.lg, overflow:'hidden', ...cardShadow }` — is retyped verbatim in at
   least 9 files (`index.tsx`, `money.tsx`, `invest.tsx`, `transactions.tsx`, `holdings.tsx`,
   `subscriptions.tsx`, `feed.tsx`, `insiders.tsx`, `stock/[symbol].tsx`). `news.tsx` and
   `event/[id].tsx` each define a **visually inconsistent** flat variant (no `radius.lg`, no
   `cardShadow`) for what is conceptually the same panel — i.e. two screens already look
   subtly different from the rest by accident, not by design. This is the single strongest
   candidate for promotion to a shared `Panel`/`Card` primitive.
2. **"Metric card" / "summary tile" stat block** — reimplemented independently at least 6
   times with different prop names and near-identical visual spec (label/value/caption,
   ~112-134px tall, 9-10px letter-spaced label): `index.tsx` (`metricCard`),
   `money.tsx` (`Metric` component + `metric` styles), `invest.tsx` (`metricCard`),
   `transactions.tsx` (`summaryTile`), `holdings.tsx` (`summaryTile`),
   `subscriptions.tsx` (`SummaryMetric` component), `insiders.tsx` (`SummaryMetric`,
   differently shaped again). None share a component.
3. **38×38 icon-only header button** — `index.tsx` `privacyButton`, `money.tsx`
   `privacyButton`, `invest.tsx` `iconButton` are byte-for-byte identical style objects.
   `insiders.tsx` `headerIcon` and `stock/[symbol].tsx` `headerIcon` are the same pattern at
   40×40 instead — an unexplained size drift between otherwise-identical controls. All are
   below the skill's 44×44 touch-target floor; fixing this in one shared `IconButton` fixes
   it everywhere at once instead of in 5 places by hand.
4. **Dark "hero" panel** (navy background, white numerals) — `money.tsx`'s `mobileHero`,
   `invest.tsx`'s `hero`, `insiders.tsx`'s `hero`, `stock/[symbol].tsx`'s `quoteHero` are four
   independent implementations of the same visual idea (dark stat block with a label/value
   and a footer row of meta text) with different paddings/radii/font sizes each time.
5. **Settings' connection row + sync/unlink action pair** — the "Banking connections" panel
   (`settings.tsx` lines 215-258) and the "Investing connections" panel (lines 292-339) are
   near-duplicate blocks: same row shape, same demo-badge-vs-sync/unlink-button branch, same
   `syncButton`/`unlinkButton` styles, differing only in which mutation/query pair they
   reference. ~90% copy-pasted.
6. **"Text link with arrow" action chip** — `money.tsx` has a dedicated `TextAction`
   component (line 350-357); `index.tsx` inlines the identical `Pressable`+`Text`+
   `ArrowRight` JSX three times (lines 213-217, 226-230) instead of reusing it;
   `insiders.tsx`'s `stockLink`/`stockLinkText` and `stock/[symbol].tsx`'s
   `insiderAnalysisLink` are near-variants of the same idea with their own styles.
7. **Two unrelated "demo" indicators**: `ui.tsx`'s `DemoBanner` (full-width banner, used on
   dashboard/money/invest/stock/insiders) vs. `settings.tsx`'s inline `demoStatus` pill
   (lines 226-230, 305-309) vs. `AppShell`'s sidebar-footer `marketStatus`/`statusDot`
   (lines 216-223, hardcoded "Demo environment" caption that doesn't actually reflect live
   connection state). Three different visual treatments of the same underlying concept
   (demo vs. live data), none sharing a component.
8. **Inconsistent field naming for "is this connection a demo/sample one?"** across the type
   layer: `ConnectionStatus.demo_mode` (investing) vs. `MoneyConnectionStatus.is_demo`
   (money) — screens already normalize this ad hoc when mapping into `useConnectionSync`
   (`index.tsx`/`invest.tsx` map `demo_mode`, `money.tsx` maps `is_demo`). Not a redesign bug,
   but a shared "connection/demo badge" component will need a normalized boolean prop rather
   than assuming a field name.
9. **`PlaidLinkButton.tsx` vs `PlaidLinkButton.native.tsx`** — see §3.7, ~90% duplicated
   JSX/styles across the two platform files.
10. **Ad hoc, inconsistent responsive breakpoints per screen** — almost every screen defines
    its own local `desktop`/`mobile`/`compact` boolean from `useWindowDimensions().width`
    with a different numeric cutoff, instead of referencing `theme/tokens.ts`'s
    `breakpoints`: `index.tsx` uses 1080 and 1680 (`sideBySideSidebar`), `money.tsx` uses 1080
    and 700, `transactions.tsx` uses 680, `subscriptions.tsx` uses 900 and 700,
    `insiders.tsx` uses 980 and 720, `news.tsx` uses 920, `stock/[symbol].tsx` uses 980, 760,
    and 520. Only `AppShell.tsx` and `AssistantDrawer.tsx` reference
    `breakpoints.mobileNav`/`breakpoints.assistantDock`. **`invest.tsx` defines no responsive
    split at all** — it's the one primary screen that does not have a genuinely different
    mobile layout (just a reflowing single column), unlike Money/Portfolio which the skill
    doc calls out as already doing this well.

## 5. Proposed redesign boundaries / seams

**Freeze as a stable contract (pages consume, never reach around):**
- `AppShell`'s prop surface (`title`, `eyebrow`, `children`, `headerAction`, `scroll`,
  `refreshing`/`onRefresh`, `assistantContext`/`assistantContextLabel`) — the shell owns nav,
  topbar, auth gate, and assistant docking; pages should not reimplement any of these.
- `lib/api.ts` / `lib/marketApi.ts` call signatures and every existing TanStack Query key —
  these are relied on by cross-screen invalidation (`event/[id].tsx`'s `markRead` invalidates
  `['feed']`/`['dashboard']`, shared by `feed.tsx`/`news.tsx`/`index.tsx`) and by the shared
  `['market-insiders', symbol]` cache entry between `insiders.tsx` and `stock/[symbol].tsx`
  (§2). If a visual direction seems to need a different data shape, that is a signal to
  revisit the direction, not license to edit `lib/api.ts` or backend routes (per the skill's
  non-negotiable list).
- `lib/useConnectionSync.ts`'s hook signature and each screen's `invalidateKeys` array (§3.1).
- The chart interaction hooks (`chartScrub`, `chartZoom`, `chartInteraction`,
  `chartMomentum`) and the `onSelectionChange`/`onContextChange` callback contracts that feed
  the assistant (§3.4, §3.8).
- `theme/tokens.ts`'s four structural namespaces — `spacing`, `radius`, `breakpoints`,
  `type` — since they're referenced by `AppShell` and dozens of screens for layout math, not
  just decoration. Changing their *values* is fine; removing/renaming keys will ripple widely.

**The one seam designed to be swapped wholesale:**
- `theme/tokens.ts`'s `colors` map. It's already a flat, fully-indirected palette (every
  screen goes through `colors.x`, no inline hex outside `tokens.ts` and a handful of
  navy-panel-specific one-offs called out in `reusable-foundations.md`). A new art direction
  can replace every value (or restructure semantic names, e.g. add `stale`/`live` if the
  redesign wants a semantic-state palette) as long as referenced keys keep resolving.

**What the shared primitives layer (`components/ui.tsx`) should grow to own** (net-new,
replacing the duplication in §4): `Panel`/`Card` (replaces the 9-file copy-paste + fixes the
`news.tsx`/`event/[id].tsx` inconsistency), `StatTile`/`MetricCard` (replaces 6+
reimplementations), `IconButton` (replaces the 38×38/40×40 drift and fixes the touch-target
floor in one place), `HeroPanel` (replaces the 4 dark-panel variants), `ConnectionRow` (takes
a normalized `demo: boolean` prop, replaces settings.tsx's two near-identical blocks and can
absorb the sidebar/DemoBanner "is this live or demo" signaling too), `TextLinkAction`
(replaces the arrow-chip variants). Existing primitives (`SectionHeader`, `ActionButton`,
`DemoBanner`, `LoadingState`, `ErrorState`, `LevelPill`) already work well and should be kept,
per `reusable-foundations.md`.

**What should stay page-specific, not promoted:** the three charts (`PortfolioChart`,
`StockPriceChart`, `insiders.tsx`'s inline `SentimentChart`) are genuinely different
visualizations of different data (continuous portfolio line vs. full OHLC+indicator stack vs.
monthly sentiment bars) — forcing a shared chart component would fight the skill's
"signature element per screen" requirement. Keep them separate, screen-owned components that
share only the headless interaction hooks in `lib/`. Similarly, each screen's specific
domain copy (insider MSPR education strip, subscriptions' "detection is not cancellation"
notice, money's category/day bars) is intentionally screen-specific content and should not be
abstracted into a generic "info card" that would blur what's Posted-specific about the screen.

**Recommended sequencing implication for the migration plan** (not asked for explicitly, but
falls out of the above): build the new `Panel`/`StatTile`/`IconButton`/`HeroPanel` primitives
and the `colors` repaint first, since nearly every screen depends on them; then redesign
screens in order of increasing coupling risk — `login.tsx` first (isolated, low risk, and the
one screen allowed a bolder moment), then the read-mostly screens (`feed.tsx`, `holdings.tsx`,
`transactions.tsx`, `subscriptions.tsx`, `news.tsx`, `event/[id].tsx`), then the
`useConnectionSync`-bearing screens (`index.tsx`, `money.tsx`, `invest.tsx`) together since
they share the exact same risk pattern, then `settings.tsx` (many small independent mutation
flows, tedious but low-risk per-row), and last the two chart-bearing screens
(`insiders.tsx`, `stock/[symbol].tsx`) since they carry the assistant-context coupling
described in §3.4 and the most complex colocated component in the app.
