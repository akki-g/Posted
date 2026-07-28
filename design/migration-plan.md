# Posted — migration plan

Executes `design/approved-design-system.md` (Direction B, "The Position
Spine"). Phased per the master redesign brief's recommended order, right-
sized for a solo project per `design/testing-strategy.md`'s own scoping
(no Storybook/visual-regression SaaS, no enterprise CI infra — a real, small
set of automated checks plus manual screenshot baselines).

Each phase below lists: scope, files, acceptance checks, and the next
dependency. Every phase gets its own commit(s); nothing here is one giant
commit. No screen is deleted until its replacement is implemented, tested,
and in use.

## Phase A — Foundations

**Scope**: tokens, primitives, breakpoint hook, test runner wiring, screenshot
baselines. No screen is visually redesigned yet.

Files: `theme/tokens.ts` (add semantic `color.*` roles, `chartCategorical`,
`elevation`, `size`, updated `type`/`radius`/`breakpoints`, `motion`),
`theme/useBreakpoint.ts` (new), `components/ui.tsx` (add `Panel`, `StatTile`,
`IconButton`, `ConnectionRow`, `FilterChip`; keep `SectionHeader`,
`ActionButton`, `DemoBanner`, `LoadingState`, `ErrorState`, `LevelPill`
unchanged), `lib/symbolColor.ts` + `lib/indicators/registry.ts` (consume
`chartCategorical`, drop `teal`/`blue`/`warning` from categorical use per
`design-system-proposal.md` §2.7), font loading in `app/_layout.tsx`
(`@expo-google-fonts/space-mono`, `@expo-google-fonts/manrope`), `settings.tsx`
(two missing `accessibilityLabel`s on the notification switches — trivial,
do now rather than waiting for that screen's full pass), `apps/client/package.json`
(add a `test` script wiring Node's built-in test runner per
`testing-strategy.md`, zero new dependency — the four existing orphaned test
files start running in CI/`make check` for the first time).

**Acceptance**:
- [ ] `npm run typecheck` and `npm run export:web` both pass.
- [ ] `node --test` runs the four existing test files green, wired into
      `apps/client/package.json` and `make check`.
- [ ] New primitives have no consumers yet — this phase adds them, Phase C+
      migrates screens onto them. (Exception: the two `accessibilityLabel`
      fixes and the categorical-palette fix ship immediately, since they're
      correctness fixes independent of any visual redesign.)
- [ ] Screenshot baseline captured for all 15 current screens at 2 viewports
      (mobile ~390px, desktop ~1440px) per `testing-strategy.md`'s exact list,
      before any screen's visual code changes in Phase C+.
- [ ] `useConnectionSync.ts`'s `isStale`/`targetConnections` exported (one-line
      visibility change, no behavior change) so Phase-A-adjacent tests can
      cover them directly, per `testing-strategy.md`.

**Next dependency**: Phase B needs the token/primitive layer to exist.

## Phase B — Application shell

**Scope**: `AppShell.tsx` navigation redesign (lens-chip + Explore-rail model
from the approved IA), `AssistantDrawer.tsx` (focus trap, Escape-to-close,
return-focus — accessibility-baseline criticals #2, plus the "expand to
`/assistant`" affordance), mobile bottom nav redesigned around the new IA
(not the current four-items-by-omission set), loading/transition behavior
for nav/drawer open-close (200ms per the motion tokens).

Files: `components/AppShell.tsx`, `components/AssistantDrawer.tsx`,
`theme/useBreakpoint.ts` consumption (AppShell stops hand-rolling its own
breakpoint checks where `useBreakpoint()` now covers them).

**Acceptance**:
- [ ] Keyboard: Tab reaches every nav item, lens chip, and the assistant
      toggle; opening the drawer moves focus in, Escape closes and returns
      focus (accessibility-baseline critical #2 — verified, not assumed).
- [ ] `/assistant` has a real navigation path (accessibility/IA fix,
      `product-workflows.md` finding d) — verify by tapping the expand
      affordance and landing on the route with context carried over.
- [ ] Existing routes (`/`, `/money`, `/invest`) still resolve — they become
      redirects to the lensed spine, not 404s, so deep links / bookmarks /
      the mobile nav's existing `/money` target don't break.
- [ ] Screenshot diff against Phase A's baseline for shell chrome only
      (nav, topbar, drawer) — content below the fold is still the old
      screens at this point, that's expected and fine.

**Next dependency**: Phase C needs the shell's lens-chip contract finalized
before the spine can consume it.

## Phase C — Representative workflow: the Position Spine

**Scope**: the single most important redesign deliverable. Build the new
unified overview — Position / Movement / Sync / Attention / Ledger bands,
lensed by Everything/Cash/Investments — replacing `index.tsx`'s dashboard and
`money.tsx`/`invest.tsx`'s overview content as the landing view on **every**
platform (the fix for the debrief-stranded-on-web problem). This is the
"prove the direction end-to-end" phase — new visual identity, new IA, new
signature interaction (the sync spine), accessibility, responsiveness, and
preserved sync/query logic all have to work together here before anything
else is migrated.

Files: new `app/index.tsx` (becomes the spine, renders identically on
web/native — the `Platform.OS !== 'web'` redirect in current `index.tsx` is
removed, not preserved), `money.tsx`/`invest.tsx` reduced to redirects (`
router.replace('/')` with a lens param) kept only for deep-link compatibility,
new spine-band components (`Position`, `Movement`, `SyncSpine`, `Attention`,
`Ledger` — colocated under a new `components/spine/` directory, following the
`StockPriceChart/` colocation pattern the skill names as the model to match).
`useConnectionSync` is consumed, not modified — its `invalidateKeys` per
lens/band must cover both money and brokerage query keys now that one screen
shows both.

**Must not change**: query keys, `useConnectionSync`'s hook contract, the
`assistantContext`/`assistantSection` plumbing (the spine still feeds it,
now driven by "which lens/band is in view" instead of "which route").

**Acceptance**:
- [ ] Functional: net cash, portfolio value, sync status, and impact/
      recurring items all still render correctly for demo and live data;
      manual sync and auto-sync-when-stale still work exactly per
      `useConnectionSync`'s existing contract.
- [ ] The sync spine's tick colors are real, not decorative — verified by
      forcing a stale connection (mock an old `last_synced_at`) and
      confirming the tick actually reads amber/red, not hardcoded green.
- [ ] Runs on native mobile with full content parity to desktop (band order,
      not layout, is what's platform-invariant) — the current
      `Platform.OS !== 'web'` redirect is gone and this is directly verified,
      not assumed.
- [ ] Accessibility: lens chips are a real `tablist`/`tab` roving-focus group
      (keyboard-operable on web); sync ticks have accessible values, not just
      color.
- [ ] Screenshot comparison against Phase A's baseline for `/`, `/money`,
      `/invest` — expect a real, described difference, not a diff tool
      complaining about noise.
- [ ] `node --test` still green; a new test covers the lens-filter logic
      (pure function, testable without rendering) per `testing-strategy.md`'s
      guidance to test logic, not just render trees.

**Next dependency**: Phase D migrates the remaining screens onto the same
primitives now proven here.

## Phase D — Core screens

**Scope**: migrate remaining primary screens in groups, per
`frontend-audit.md` §5's risk-ordered sequencing:

1. `login.tsx` first — isolated, low-risk, and the one screen allowed a
   bolder moment (fix the centered-hero-plus-feature-cards genericness
   finding explicitly here, per `competitor-similarity-audit.md` finding #1).
2. Read-mostly screens: `feed.tsx`, `holdings.tsx`, `transactions.tsx`,
   `subscriptions.tsx`, `news.tsx`, `event/[id].tsx` — collapse
   Feed/News/Holdings/Insiders into the "Portfolio detail" tabbed destination
   per the approved IA.
3. `settings.tsx` — adopt `ConnectionRow`, fix the ~90% duplicated banking/
   investing blocks, move connection *health* display to the Sync band
   (§Settings note in the approved design system) while keeping add/remove
   here.
4. `insiders.tsx`, `stock/[symbol].tsx` last — most complex colocated
   components, carry the assistant-context-ref coupling
   (`frontend-audit.md` §3.4) that needs the most care.

**Acceptance per group**: typecheck, `node --test`, manual screenshot
comparison against Phase A baseline, and the specific accessibility item
that touches that group (e.g., group 4 must verify the chart keyboard-path
fix, accessibility-baseline critical #1).

## Phase E — Supporting screens and states

**Scope**: login (folded into D.1 above — no separate pass needed), empty/
loading/error states audited for the "explain what went wrong, invite an
action" standard already met by `ErrorState`/`LoadingState` (validate, these
are already correct per `reusable-foundations.md` — don't rebuild what
works), demo-mode's new permanent ambient treatment (replacing the 3
divergent implementations found — `DemoBanner`, the settings pill, the
sidebar dot), partial-data states for the causal Movement note (must fall
back to a plain delta if confidence is low, per the risk noted in
`redesign-directions.md` Direction B), and the SMS-assistant-link visibility
gap (`product-workflows.md` finding f) — surface "also reachable by text" in
the assistant UI.

**Acceptance**: each state manually exercised (demo mode, a forced sync
error, a stale-for-days connection, zero transactions) and screenshotted;
no state renders a blank screen.

## Phase F — Cleanup

**Scope**: delete `index.tsx`/`money.tsx`/`invest.tsx`'s old implementations
once Phase C's replacement has been in place and used for a real session;
remove the now-dead duplicate style blocks (the 9-file Panel, 7-file
StatTile, 5-file IconButton, 4-file hero panel — confirm zero remaining
references before deleting each); remove `colors.purple/pink/orange/indigo/
brown` as direct top-level exports once `chartCategorical` fully replaces
their call sites; update `README.md`'s "frontend visual language" paragraph
(currently describes the old system) to match what actually shipped; confirm
no screen still declares its own ad hoc breakpoint number.

**Acceptance (final completion criteria)**: every primary route uses the
approved design system; `/`, `/money`, `/invest` all resolve correctly (spine
+ redirects); native mobile has full parity with web for the daily-check
workflows; `node --test` and `npm run typecheck`/`export:web` all pass;
critical accessibility findings (the 5 listed in the approved design system)
are fixed and spot-checked, not just planned; no screen still hand-rolls a
Panel/StatTile/IconButton/hero-panel/breakpoint; `git grep` for the old
duplicated style blocks returns nothing outside git history.
