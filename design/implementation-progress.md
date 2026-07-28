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

## Phase D–F — not started

Per `design/migration-plan.md`: login redesign, read-mostly screens,
Settings' `ConnectionRow` adoption, the two chart-bearing screens, supporting
states, and cleanup/legacy removal remain.

## Standing constraint (all phases)

No browser-automation tool is available in this environment, and the app's
backend is running live with real production Plaid credentials and no
demo-mode fallback — I cannot log in to click through screens or capture
screenshots myself. Every phase above has been verified via typecheck, the
unit test suite, a successful production build, and careful manual code
review, but not via an actual rendered screen. Recommend the user do a
visual pass in their own logged-in session before this branch merges.
