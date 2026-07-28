# Implementation progress

Tracks status against `design/migration-plan.md`. Updated as phases land.

## Phase A — Foundations

**Status**: done. **Commit**: `feat: Phase A foundations - tokens, primitives, fonts, test runner`.

- Files changed: `theme/tokens.ts`, `theme/useBreakpoint.ts` (new), `components/ui.tsx`
  (added `Panel`/`StatTile`/`IconButton`/`ConnectionRow`/`FilterChip`),
  `lib/symbolColor.ts`, `lib/indicators/registry.ts`, `app/_layout.tsx` (font
  loading), `app/settings.tsx` (2 accessibility labels), `apps/client/package.json`
  + `Makefile` (test runner wiring), `lib/useConnectionSync.ts` (exported
  internals) + new `lib/useConnectionSync.test.ts`.
- Tests run: `npm run typecheck` (clean), `npm run test` — 27/27 passing
  (the four previously-orphaned test files now actually execute), `npm run
  export:web` (clean production build).
- Screenshots reviewed: **not captured** — no browser-automation tool
  available in this environment, and the live backend has no demo-mode
  fallback (real production Plaid credentials), so I can't log in to
  capture the real screens myself. Unresolved; needs the user's own
  logged-in session if strict before/after screenshots are wanted.
- Unresolved findings: none blocking. The `colors.line`→`hairline` rename
  design-system-proposal.md suggested was deliberately deferred — renaming
  now would touch every screen ahead of its own migration for no visual
  benefit; each screen adopts the semantic `roles.*` layer when it's
  actually migrated instead.
- Next dependency: Phase B needed the token/primitive layer — satisfied.

## Phase B — Application shell

**Status**: done. **Commit**: `feat: Phase B+C - shell redesign and the unified Position Spine`.

- Files changed: `components/AppShell.tsx`, `components/AssistantDrawer.tsx`,
  `components/AssistantChat.tsx`, `app/assistant.tsx`.
- Tests run: same suite as above, all green.
- Screenshots reviewed: not captured (see Phase A note — same constraint).
- Unresolved findings: the Explore panel is a flat 7-item list (Holdings,
  Transactions, Subscriptions, Feed, News, Insider activity, Settings) — the
  approved design system calls for collapsing Feed/News/Holdings/Insiders
  into one tabbed "Portfolio detail" destination eventually (Phase D), not
  done yet. Full ARIA roving-tabindex tablist semantics for the lens chips
  were scoped down to a simpler accessible button-group pattern (each chip
  is independently keyboard-reachable and announces selected state, but
  arrow-key roving focus between chips isn't implemented) — noted as a
  deliberate, smaller-than-ideal accessibility scope, not an oversight.
- Next dependency: Phase C needed the shell's lens-chip contract — satisfied
  (built together in the same commit; see below).

## Phase C — Representative workflow: the Position Spine

**Status**: done. **Commit**: same as Phase B (built together — the shell's
nav model only makes sense with the Spine's needs in view).

- Files changed: new `app/index.tsx` (the Spine), `app/money.tsx` /
  `app/invest.tsx` (now redirect stubs), new `components/spine/Band.tsx`,
  `components/spine/SyncSpine.tsx`, `lib/format.ts` (added
  `daysUntilNumber`).
- Functional check performed: read through the full data flow by hand
  (query keys, `useConnectionSync` wiring for both brokerage and money
  connections, lens-driven band content, sync-tick freshness computed from
  real `last_synced_at` values) since a live click-through isn't available
  in this environment (see the standing screenshot/login constraint).
- Screenshots reviewed: not captured — same constraint as Phase A/B.
- Known simplifications, deliberately not carried into the new Spine (not
  silently dropped — flagged for the user to ask for back if wanted):
  the old money.tsx's daily-spending bar chart and category-breakdown bars,
  and invest.tsx's insider-activity teaser banner.
- Unresolved findings: the Movement band's causal note is deliberately
  conservative — it only fires from data already on hand (an unread
  urgent/important event with a linked security, or a spending category at
  ≥30% share) and falls back to a plain delta otherwise, per the risk
  `redesign-directions.md` flagged about generated-text reliability on a
  real financial app. The Sync band's tap-to-expand detail shows only
  factual data already available (account count, freshness, last-synced
  time) — it does not show "what changed" in the last sync, since that
  would require a backend change (out of frontend-only scope).
- Next dependency: Phase D (remaining core screens) can now build on the
  same `Panel`/`StatTile`/`IconButton`/`Band` primitives and the Explore
  nav model proven here.

## Phase D — Core screens

**Status**: done, uncommitted (working tree only, per current instruction not
to commit). No dedicated commit yet.

- `login.tsx`: replaced the centered-hero-plus-feature-cards layout
  (`competitor-similarity-audit.md` finding #1) with a single-column
  statement-style page whose hero *is* a labeled preview of the real Position
  Spine (masked/example net-worth and holdings figures), landing directly
  into the sign-in action instead of a marketing feature list.
- `transactions.tsx`, `subscriptions.tsx`, `holdings.tsx`, `feed.tsx`,
  `news.tsx`, `event/[id].tsx`: migrated onto `Panel`/`StatTile`/`FilterChip`/
  `useBreakpoint()`, replaced hardcoded on-navy hex colors in the two dark
  score cards (news detail, event detail) with the named `inkOnDark*`/
  `hairlineOnDark`/`positiveOnDark` etc. tokens from Phase A, added focus
  rings to search inputs that previously disabled the outline with nothing
  replacing it.
- `settings.tsx`: banking and investing connection lists now both use the
  `ConnectionRow` primitive (closes the ~90%-duplicated block finding);
  removed the now-dead `panel`/`connectionRow`/`demoStatus`/`unlinkButton`
  style definitions and unused icon imports this freed up.
- `insiders.tsx`, `stock/[symbol].tsx`: last, per the audit's risk ordering.
  Panel/hero-card treatment migrated to the shared primitives; every
  hardcoded on-navy hex color replaced with the named tokens (several were
  literally the exact values already promoted into `theme/tokens.ts` from
  this file during Phase A, so this was a direct swap, not a guess). Chart
  interaction code (`SentimentChart`'s scrub, `StockPriceChart`,
  `chartContextRef`) was **not** touched, per the frozen-contract warning in
  `frontend-audit.md` §3.4/§3.8.
- `AppShell.tsx` now consumes `useBreakpoint()` itself instead of computing
  `desktop` inline — one less place duplicating the breakpoint logic it
  otherwise enforces.
- `README.md`'s "frontend visual language" paragraph updated to describe
  what's actually shipped (was describing the pre-redesign system).

**Verified**: typecheck clean, 27/27 tests pass, production web export
builds successfully, after each screen and again at the end of the batch.
**Not verified**: live rendering (see standing constraint below) — this is
the largest batch of unverified-by-eye changes in the effort so far and
should be the first thing checked in a real browser.

**Deliberately not done in this pass**: collapsing Feed/News/Holdings/
Insider activity into one tabbed "Portfolio detail" destination
(`approved-design-system.md`'s IA target) — scoped down to a design-system
migration of each screen in place, reachable via the new Explore panel,
rather than a route-level merge. The four screens still exist as separate
routes. This is the main remaining gap between what's implemented and the
approved IA. **Update — now completed in Phase D.1 below.**

## Phase D.1 — Portfolio detail tab merge (IA route consolidation)

**Status**: done, uncommitted (working tree only, per current instruction not
to commit). No dedicated commit yet. Closes the main IA gap flagged at the end
of Phase D.

- Collapsed the four separate routes (`feed`, `news`, `holdings`, `insiders`)
  into one tabbed **Portfolio detail** destination at `app/portfolio.tsx`,
  landing on the tab the entry point implies (`?tab=holdings|feed|news|insiders`,
  default `holdings`; `?symbol=` deep-links straight into the Insiders tab).
  Mirrors the shipped Position Spine pattern exactly: a `FilterChip` `tablist`
  driven by `router.setParams` (no stack navigation), tab order
  **Holdings · Feed · News · Insiders**.
- New `lib/portfolioTab.ts` owns the tab set / labels / titles and a
  `normalizePortfolioTab()` helper (default + unknown-value fallback), covered
  by new `lib/portfolioTab.test.ts` (3 cases).
- Each screen's body was extracted into `components/portfolio/{HoldingsTab,
  FeedTab,NewsTab,InsidersTab}.tsx` — pure presentational units that render
  without page chrome (the container owns `AppShell`, the page header, and the
  tab row). Each keeps its own `useQuery` hooks, so only the active tab fetches.
- The four old routes are now thin `<Redirect>` shims to `/portfolio?tab=…`
  (the insiders shim forwards `?symbol=` through), matching the existing
  `money.tsx`/`invest.tsx` redirect pattern for deep links and bookmarks.
- `AppShell` Explore panel collapsed from 7 flat items to the four approved
  destinations (**Portfolio detail · Transactions · Subscriptions · Settings**);
  `assistantSectionForPath` now maps `/portfolio` → investing; three now-unused
  icon imports removed. Five outbound navigation callsites repointed
  (`index.tsx` ×2, `stock/[symbol].tsx` ×2, `MarketSearch.tsx` ×1).
- Chart interaction code in InsidersTab (`SentimentChart`, `useChartScrub`,
  and every subcomponent/style below the default export) was copied verbatim
  and **not** touched, per the frozen-contract warning in `frontend-audit.md`
  §3.4/§3.8. Only the top-level component (param plumbing + page chrome) changed.

**Deliberate simplifications, flagged (not silently dropped — ask for them
back if wanted):**
- News tab: dropped `AppShell`'s pull-to-refresh; kept the in-body "Refresh
  providers" button, which already triggers the same provider refresh.
- Insiders tab: moved the desktop header search + refresh out of the page-header
  action slot into an in-body tab-header row (now consistent with how the
  Holdings tab renders `MarketSearch` in-body).
- Insiders assistant context no longer includes the live "inspected sentiment
  bar" detail (that state now lives inside `InsidersTab`, below the container
  that owns `AppShell`). The symbol-aware context is otherwise preserved.
- Unified eyebrow "PORTFOLIO DETAIL" across tabs; each tab keeps its original
  full page title ("Holdings" / "Impact feed" / "News stories" / "Insider
  activity").

**Verified**: `npm run typecheck` clean, `npm run test` 30/30 pass (27 prior +
3 new `portfolioTab` cases), `npm run export:web` builds the production bundle
successfully.
**Not verified**: live rendering — same standing constraint as every phase
below; the tab switching, deep-link landing, and insiders auto-select should be
the first things checked in a real logged-in browser session.

## Phase E–F — not started

Per `design/migration-plan.md`: supporting/partial-data states beyond what
Phase C/D already covered, the SMS-assistant-visibility affordance
(`product-workflows.md` finding f), and cleanup (delete now-unused exports,
confirm no screen still hand-rolls a breakpoint outside the two content-
specific exceptions noted below) remain.

**Known remaining ad hoc breakpoints**: `insiders.tsx` and
`stock/[symbol].tsx` still compute their own `width >= 980` /
`width >= 760` cutoffs via raw `useWindowDimensions` rather than
`useBreakpoint()`. Left as-is rather than force-fit into the shared
breakpoint set, since these are genuine content-specific thresholds (e.g.
"does the header search fit inline") that don't cleanly map to
`compact`/`mobileNav`/`wide`/`assistantDock` — flagged here rather than
silently left inconsistent.

## Standing constraint (all phases)

No browser-automation tool is available in this environment, and the app's
backend is running live with real production Plaid credentials and no
demo-mode fallback — I cannot log in to click through screens or capture
screenshots myself. Every phase above has been verified via typecheck, the
unit test suite, a successful production build, and careful manual code
review, but not via an actual rendered screen. Recommend the user do a
visual pass in their own logged-in session before this branch merges.
