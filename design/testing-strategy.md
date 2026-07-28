# Posted frontend testing strategy — for the redesign

Research/proposal only. No code changed, no dependencies added. Grounded in direct
inspection of `apps/client/package.json`, the four existing test files, `backend/`'s
test suite and `Makefile`, and the sync/auth/link code the redesign will touch.
Companion to `design/frontend-audit.md` (architecture map, redesign boundaries) and
`design/product-workflows.md` (who this is for, what they're doing) — read those for
the "why," this is the "how do we not break it."

---

## 1. Current state, confirmed

**`apps/client/package.json` has no test script at all.** Its `scripts` block is
exactly `start`, `android`, `ios`, `dev:ios`, `dev:android`, `web`, `typecheck`,
`export:web` — no `test`, no `jest`/`vitest` devDependency, no config file
(`jest.config.*`, `vitest.config.*`) anywhere under `apps/client/`. `make check` runs
`npm run typecheck && npm run export:web` for the frontend half — it never executes
any test file.

**But four real test files already exist and already pass, today, unwired:**

- `apps/client/src/components/StockPriceChart/formatting.test.ts`
- `apps/client/src/lib/chartInteraction.test.ts`
- `apps/client/src/lib/indicators/calculate.test.ts`
- `apps/client/src/lib/indicators/signals.test.ts`

All four are written the same way — Node's own test runner, not a third-party
framework:

```ts
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { formatAxisDate, formatTrackingDate, formatVolume } from './formatting.ts';
```

I ran all four directly with no changes and no config:

```
$ node --test          # from apps/client, no path argument
ℹ tests 21
ℹ pass 21
ℹ fail 0
```

Node's test runner auto-discovers `**/*.test.ts` with zero configuration on this
machine (Node v26) because Node's native TypeScript support strips the four files'
type annotations at load time — and `tsconfig.json`'s `allowImportingTsExtensions`
is exactly why the tests import `'./formatting.ts'` with the extension rather than
extension-less: that's Node's module resolution rule, not a TS convention, so these
files were plainly authored with `node --test` in mind, not Jest/Vitest, and simply
never got a `package.json` script. There is no ambiguity to resolve here — the tests
already run, they're just not reachable via any `npm run` command or `make check`.

One caveat worth flagging precisely: Node's built-in type-stripping is default-on
only from **Node 23.6+**; on Node 22.x (the README's stated minimum) it requires the
explicit `--experimental-strip-types` flag. I confirmed the flag is accepted and
produces identical output on this machine. The wired script (§2) should pass it
explicitly rather than rely on the local Node happening to be new enough. I also
confirmed none of the four tested source files use non-erasable TS syntax (no
`enum`, no `namespace`, no decorators) — `grep -rnE '\benum |\bnamespace |@[A-Za-z]+\('`
across all four found nothing, so stripping is safe, not just lucky.

**Backend, for contrast:** `backend/app/tests/` has 30 files (`test_plaid_sync.py`,
`test_schwab_sync.py`, `test_connections_sync.py`, `test_auth_routes.py`, etc.,
~4,700 lines). The pattern (see `test_plaid_sync.py`) is consistent: in-memory
SQLite via `create_async_engine("sqlite+aiosqlite:///:memory:")`, a hand-written
`FakePlaidClient`/fake adapter standing in for the real provider, and an assertion
against the resulting DB rows — no live network, no mocking framework, just
substituting a fake at the adapter boundary. `make check` runs `ruff check` +
`pytest` with `addopts = "-m 'not user_owned'"` (backend `pyproject.toml`) — i.e. the
**agent-owned** suite. `make learning-check` runs `pytest -m user_owned` — the
executable specs for the nine hand-owned learning files listed in the root
`README.md` (`reconcile.py`, `normalize.py`, `dedupe.py`, `scoring.py`,
`orchestrator.py`, and the four money-track modules). This split is load-bearing:
**nothing proposed below touches those nine files or their `user_owned`-marked
specs.** The frontend gap this document addresses is structural (no wiring), not a
coverage gap the human is supposed to fill in personally — unlike the backend's
nine files, frontend code isn't part of the learning exercise.

There is no CI (no `.github/` directory) — every check here runs locally, by hand,
via `make` targets. That's consistent with a solo project and isn't something this
document proposes to change.

---

## 2. Test runner: Node's built-in test runner, not Jest/jest-expo, not Vitest — with one narrow, deferred exception

**Recommendation: keep using `node --test` as the one and only runner for pure-logic
unit tests, and wire it up exactly as the existing four files already expect.**

Why, specifically for this stack, not generically:

- **The four existing files already are the intended shape.** They import from
  `node:test`/`node:assert/strict`, not Jest globals or Vitest's `describe`/`expect`.
  Migrating them to Jest or Vitest means *rewriting* working, passing tests instead
  of *wiring up* orphaned ones — the opposite of the lowest-friction fix.
- **Zero new dependencies**, which matters concretely here, not just as a platitude:
  `jest-expo`'s preset version has to track the installed Expo SDK version
  (currently `~57.0.8`) release-for-release, and Expo SDK upgrades are exactly the
  kind of maintenance a solo dev doing this alone will feel as version-mismatch pain
  later. `node --test` has no such coupling — it's part of the Node runtime already
  required to run the app at all.
- **It's the right tool for what these four files (and their natural extensions)
  actually test**: pure functions with no React, no JSX, no RN native modules —
  `formatting.ts`, `chartInteraction.ts`, `indicators/calculate.ts`,
  `indicators/signals.ts`, and (new) `lib/format.ts`. Plain `.ts` modules with
  erasable-only TypeScript syntax are exactly what Node's type-stripping supports.
- **The one real limitation, and why it rules out relying on `node --test` alone
  for everything**: Node's type-stripping erases *type* syntax; it does **not**
  transform JSX. Any file that renders a component (`AppShell.tsx`, `index.tsx`,
  `invest.tsx`, `money.tsx`, `PlaidLinkButton.tsx`, …) cannot be loaded by
  `node --test` at all — not "harder to test," genuinely un-importable without a
  JSX transform. That's a hard boundary, not a style preference.

**Wiring (concrete, for whoever implements this next):**

```json
"scripts": {
  "test": "node --experimental-strip-types --test 'src/**/*.test.ts'"
}
```

and in the root `Makefile`'s `check` target, add `&& npm run test` to the existing
`cd apps/client && npm run typecheck && npm run export:web` line. This alone turns
the four orphaned files into a real, always-green regression gate with a one-line
change and no new dependency — that should be the very first PR of the redesign,
before any visual work starts (see Phase 1 in §6).

**The deferred exception — component/integration rendering.** Task §3 below asks
for "a screen against a mocked API client." That genuinely requires rendering a
`.tsx` tree, which needs a JSX transform Node doesn't have. Between Jest-via-
`jest-expo` and Vitest for that specific job:

- `jest-expo` is Expo's own maintained preset — it ships native-module mocks for
  exactly the packages this app depends on (`react-native-safe-area-context`,
  `react-native-svg`, `expo-router`, `lucide-react-native`'s RN entry point) and is
  version-pinned to the Expo SDK via `expo install jest-expo`, so it stays correct
  across SDK bumps instead of bit-rotting silently.
- Vitest has no equivalent Expo-maintained preset. Getting Vitest to render an RN
  component means hand-assembling jsdom (or happy-dom) + a React plugin + manual
  mocks for every native module transitively imported by whatever you render — for
  one dev, that's strictly more setup and more ongoing maintenance than `jest-expo`
  solves out of the box, for the same result.

So: **`jest-expo` + `@testing-library/react-native` is the correct choice if/when
component-rendering tests are wanted** — but I'm recommending it be added
*deliberately later*, not now, and scoped to exactly two tests (§3, §6 Phase 2), not
a general component-testing habit. Reason: most of the current screens are about to
be visually rewritten. A component-render test against the *current* `AppShell`/
`index.tsx` tree would be testing code that's dead within days — busywork, not
protection. The two tests worth the dependency cost are ones that protect logic
that survives the redesign unchanged (the auth-gate *decision*, the sync hook's
*behavior*), not the current visual tree.

---

## 3. Critical workflows and what actually protects them

Ranked by "how bad is it if this silently breaks during a visual rewrite," not by
how interesting the code is:

### 3.1 Sync behavior (`useConnectionSync.ts` + its three call sites) — highest priority

`apps/client/src/lib/useConnectionSync.ts` has two private, **unexported** helper
functions carrying the actual business logic:

```ts
function isStale(connections: SyncableConnection[]): boolean { ... }        // line 11
function targetConnections(connections: SyncableConnection[]): SyncableConnection[] { ... }  // line 20
```

`isStale` drives "auto-sync-once-if-stale" (>5 min since `last_synced_at`, or never
synced) on first load; `targetConnections` drives "sync every live connection, or
fall back to the single demo connection if there are no live ones." Both are pure,
both are currently untestable in isolation because they're not exported. **Concrete
fix, not a rewrite**: export both. That's it — no behavior change, just visibility,
and it turns the two riskiest lines in the sync feature into two `node --test`
cases with zero rendering machinery:

```ts
test('isStale is true when a connection has never synced', () => { ... });
test('isStale is false when the most recent sync is within 5 minutes', () => { ... });
test('targetConnections prefers live connections over the demo one', () => { ... });
test('targetConnections falls back to the first demo connection when none are live', () => { ... });
```

I confirmed all three call sites (`index.tsx` line 53, `invest.tsx` line 31,
`money.tsx` line 42) wire the hook identically: `onRefresh`/the manual "Sync"
button call `sync.mutate()` unconditionally (manual-refresh-always-syncs), while the
hook's own `useEffect` only calls `sync.mutate()` when `isStale(...)` is true
(auto-sync-if-stale, gated by a `useRef` so it only ever fires once per mount). That
consistency across all three screens is itself worth protecting — a redesign that
touches all three screens is the likeliest place for one of them to accidentally
drop the `onRefresh` wiring or change `invalidateKeys` while restyling.

### 3.2 Auth gate (`AppShell.tsx`)

```ts
useEffect(() => {
  if (!isLoading && !user) router.replace('/login');
}, [isLoading, user, router]);
```
(line 129). This single effect is the entire access-control boundary for every
screen in the app — every page is wrapped in `AppShell`. The condition itself is
too trivial to be worth a pure-function extraction (unlike §3.1, there's no real
logic here to isolate); the actual risk is integration-level: does the effect fire
exactly once, does an authenticated user never see a login flash, does a user who
resolves from `isLoading` to `!!user` mid-session correctly *not* redirect. That's
exactly the class of test `jest-expo`/RNTL is for (§2, §6 Phase 2) — render
`AppShell` with a mocked `@/lib/AuthContext` returning `{ user: null, isLoading:
false }`, assert `router.replace` was called with `/login`; then with `isLoading:
true`, assert it wasn't.

### 3.3 Plaid/Schwab Link + OAuth callback

- `PlaidLinkButton.tsx` (web, `react-plaid-link`'s `usePlaidLink`) and
  `PlaidLinkButton.native.tsx` (native, `react-native-plaid-link-sdk`'s
  `createPlaidLinkSession`) are two separately maintained files implementing the
  *same* connect → exchange → sync → format-success-message flow. I confirmed the
  success-message logic is duplicated verbatim between them:
  ```ts
  const skipped = sync.rejected > 0 ? ` ${sync.rejected} could not be read and were skipped.` : '';
  setSuccess(sync.normalized > 0 ? `Connected and imported ${sync.normalized} transactions.${skipped}` : ...);
  ```
  This is a concrete drift risk independent of the redesign: extracting this into a
  shared `formatSyncSuccessMessage(sync)` in `lib/` would (a) be one pure function
  two `node --test` cases can cover, and (b) remove the chance of the web and
  native variants silently disagreeing after either gets edited alone. Worth doing
  regardless of the redesign's visual scope.
- `PlaidInvestmentLinkButton.tsx` follows the same web-only `usePlaidLink` shape.
- `app/login/callback.tsx` (Google OAuth) is simple branching on
  `useLocalSearchParams<{ session?, error? }>()` — `session` present → `signIn` +
  redirect home; `error` present → static rejection message. Low complexity, but
  it's the one screen that's a hard dead-end if broken (can't sign in at all).
- Schwab OAuth is a full browser round trip: `settings.tsx`'s `connectSchwab`
  mutation (`api.authorizeSchwab`) opens Schwab's consent screen in the browser;
  the return trip lands back on the app with connected/cancelled state reflected
  in `settings.tsx`'s own query state. This is fundamentally not unit-testable —
  it's the strongest (arguably only) candidate for an actual browser-driven E2E
  check, not a mocked test (§4).

### 3.4 Financial formatting (`lib/format.ts`) and chart math

`lib/format.ts` (`money`, `number`, `percent`, `signedMoney`, `daysUntil`,
`relativeTime`) has **zero test coverage today** despite being the single place
every dollar figure, percentage, and date-relative string in the entire app passes
through. This is the highest-leverage, lowest-effort addition: five to eight
`node --test` cases (sign handling in `signedMoney`/`percent`, the `daysUntil`
boundary cases — "Today," "Tomorrow," the 14-day cutover to "In N weeks" — and
`relativeTime`'s minute/hour/day cutovers) would directly protect the numbers a
real user with live Plaid/Schwab data is trusting every day. `chartInteraction.ts`
and `indicators/calculate.ts`/`signals.ts` already have coverage (§1) — extending
that pattern to `format.ts` is the same shape of work, not a new one.

---

## 4. Right-sized coverage by kind

| Kind | Recommendation |
|---|---|
| **Unit** | `node --test` for all pure logic: the four existing files, new `lib/format.test.ts`, the newly-exported `isStale`/`targetConnections` from `useConnectionSync.ts`, and (if extracted per §3.3) `formatSyncSuccessMessage`. This is where nearly all the actual protection comes from, and it costs nothing beyond writing the tests. |
| **Integration** | Exactly two `jest-expo` + `@testing-library/react-native` tests, added when `AppShell` is redesigned (§6 Phase 2), not before: the auth-gate redirect behavior (§3.2), and one render of `useConnectionSync` itself via `renderHook` with a fake `QueryClient` and a spy `syncFn`, asserting the *hook's actual effect* fires once on stale mount and that calling the returned mutation always fires regardless of staleness — this exercises the real hook (not a reimplementation of its logic), which is what "integration" should mean here. Do not expand this into full-screen render tests of the pre-redesign UI — it will be replaced within the same effort. |
| **End-to-end** | Not a suite. **Detox is not worth it for this project** — no CI, one developer who already manually runs the app on their own device/simulator as part of normal work (per `README.md`'s own dev loop), and Detox's native-build/simulator wiring is a maintenance tax with no CI to amortize it against. Playwright, on the other hand, is worth a couple of one-off scripts (not a fixture-laden suite) for exactly two flows, run manually at redesign milestones rather than on every commit: (1) Google sign-in → landing on the authenticated home screen — the one universal gate everything else sits behind; (2) tapping "Sync" on one sync-bearing screen and confirming the "Updated Xm ago" timestamp actually advances — a smoke check that the exact behavior in §3.1 survived. See §5 for why Playwright specifically is realistic here at near-zero setup cost. |
| **Accessibility** | An automated `axe-core` pass against the static `expo export --platform web` output, run manually (not CI-gated) at each phase boundary in §6. Lowest-friction form: `npx @axe-core/cli` against `npx serve apps/client/dist` (or reuse the Playwright session from the E2E scripts above to inject `@axe-core/playwright` for free, since the browser is already open). This is a smoke check, not a compliance audit — it exists to catch redesign regressions like the 38×38 icon-button touch targets the `product-design` skill already flags as under WCAG's 44×44 floor, not to chase a zero-violations badge. |
| **Visual regression** | No CI-integrated pixel-diff pipeline (no Percy/Chromatic/reg-suit) — disproportionate for one developer eyeballing their own redesign. What's actually proportionate: one screenshot per screen per breakpoint, captured immediately before the redesign starts, diffed by eye against the equivalent post-redesign capture at each phase boundary. See §5 for exactly which screens and how. |

---

## 5. Screenshot baseline — which screens, and how to capture them

**Screens needing a baseline** (every routable screen under `apps/client/src/app/`,
excluding `_layout.tsx` which isn't a page): `index.tsx`, `money.tsx`, `invest.tsx`,
`feed.tsx`, `holdings.tsx`, `transactions.tsx`, `subscriptions.tsx`, `news.tsx`,
`insiders.tsx`, `event/[id].tsx`, `stock/[symbol].tsx`, `settings.tsx`, `login.tsx`,
`login/callback.tsx`, `assistant.tsx` — 15 screens.

**Viewports**: two per screen is enough — `390×844` (mobile, below both the
`breakpoints.mobileNav` = 920 token and every screen's local `mobile`/`desktop`
cutoffs, which range from 700 to 1080) and `1440×900` (desktop, above all of them,
including `index.tsx`'s own `sideBySideSidebar = 1680`... note that one specifically
needs a third, wider capture — `1728×1000` or similar — if you want the debrief
rail's side-by-side vs. stacked behavior in the baseline too, since 1440 sits below
that particular cutoff). 15 screens × 2 viewports = 30 images, +1 for the wide
`index.tsx` variant = 31. That's a half-hour of scripted capture, not a burden.

Some screens need an authenticated session to reach at all (everything except
`login.tsx`) — capture these against your own real logged-in session (this app has
one real user with live Plaid/Schwab connections; there's no seeded fixture
account to substitute), and `login/callback.tsx` specifically only renders its
"real" states mid-redirect or on an `?error=` param, so a static capture of it is
low-value — a one-line note that it was visually inspected instead is enough.

**On the "no browser-automation tool available" constraint — checked, and it's more
nuanced than that in this specific environment.** `apps/client/package.json` itself
has no Playwright/Detox dependency, confirmed. But this exact machine already has a
working Playwright + Chromium setup left over from prior work: `~/Library/Caches/
ms-playwright/chromium-1234` (a real cached browser binary, dated Jul 24), and
`output/playwright/*.png` already contains real screenshots from this app —
`money-desktop.png`, `invest-mobile.png`, `settings-schwab-mobile.png`,
`stock-aapl-desktop.png`, and others, dated Jul 22–24 — plus `.playwright-cli/`
directories with matching console logs and accessibility-tree snapshots. `output/
playwright/` is already in `.gitignore` (with the comment "Browser QA artifacts"),
so this is clearly an established, if informal, pattern in this repo already — not
something to introduce.

That said, those existing screenshots are **4–5 days stale relative to redesign
start and incomplete** (no `feed`, `insiders`, `holdings`, `subscriptions`,
`transactions` desktop, `event/[id]`, `assistant` beyond the two already in
`.playwright-cli/`, `news`, `login`) — reuse them as a sanity check that nothing
regressed between Jul 22–24 and now, but capture a fresh, complete set right before
the redesign actually starts touching pixels, since I can't independently verify no
frontend change landed in between.

**Practical capture approach, in priority order:**
1. **Preferred, and evidently low-friction on this exact machine**: `npx playwright
   screenshot --viewport-size=<W,H> <url> <file>.png` in a loop over the 15 routes,
   at both viewports, against a running `npm run web` dev server. This needs no
   `package.json` change (`npx` resolves and runs Playwright without adding it as a
   project dependency) and the Chromium binary is already cached locally, so it's
   realistically a "download nothing, install nothing" operation right now. Save
   into `output/playwright/baseline-pre-redesign/<screen>-<viewport>.png` — same
   directory convention as the existing artifacts, already gitignored.
2. **Fallback if `npx`/network isn't available in whatever environment actually
   runs this** (e.g. a future session without this machine's cache): plain macOS
   `screencapture` (confirmed present at `/usr/sbin/screencapture`) against the
   dev server opened in a real browser window resized to each target viewport, or
   the simpler `Cmd+Shift+4` interactive selection. Slower (manual per screen) but
   needs literally nothing beyond the OS and a browser — the genuinely
   zero-dependency option.

Either way, the deliverable is a flat folder of consistently named PNGs, diffed by
opening old/new side by side — no tooling beyond an image viewer.

---

## 6. Acceptance criteria per migration phase

Concrete pass/fail, not "make sure it works." Phase names match `design/
frontend-audit.md §5`'s proposed sequencing (primitives/colors first, then
`login.tsx`, then read-mostly screens, then the `useConnectionSync` trio together,
then `settings.tsx`, then the two chart screens last) folded into the five stages
requested here.

### Phase 1 — Foundations (test infra + shared primitives + token repaint)

- [ ] `npm run test` exists in `apps/client/package.json`, runs `node --test`
  against `src/**/*.test.ts`, and passes with the same 21 assertions confirmed in
  §1 — zero new `dependencies`/`devDependencies` added to do this.
- [ ] `make check` invokes the frontend test script; a deliberately broken
  assertion in one of the four files makes `make check` fail (prove the gate is
  real, not decorative).
- [ ] `lib/format.ts` has a `format.test.ts` covering every exported function's
  boundary cases (§3.4); `useConnectionSync.ts`'s `isStale`/`targetConnections`
  are exported and covered by `node --test` cases (§3.1).
- [ ] Full baseline screenshot set captured (§5) before any primitive's visual
  output changes.
- [ ] One `axe-core` smoke pass recorded against the current `expo export
  --platform web` build as the "before" reference (§4) — not required to be
  violation-free, just captured for comparison.
- [ ] `make learning-check` still passes, untouched — proves none of this work
  reached into the nine `user_owned` files.

### Phase 2 — App shell (`AppShell.tsx` nav/topbar/auth-gate redesign)

- [ ] The `jest-expo` + `@testing-library/react-native` dependency is added *now*,
  not earlier — this is the first point in the migration where a component-render
  test targets code meant to last.
- [ ] Two integration tests exist and pass: auth-gate redirects to `/login` when
  `{ user: null, isLoading: false }`, and does not redirect when `isLoading: true`
  (§3.2).
- [ ] Every `href` in `portfolioNav`/`moneyNav`/`mobileNav` (AppShell.tsx lines
  54–73) still resolves to the same route after restyling — a route, not a pixel,
  check.
- [ ] The 38×38 icon buttons the `product-design` skill flags as under the 44×44
  WCAG floor are corrected in this pass, not deferred (the skill already commits
  to this).
- [ ] `npm run typecheck` clean; manual click-through of every nav item on both
  the desktop sidebar and mobile bottom-nav.

### Phase 3 — First representative workflow

Whichever single screen is redesigned first (per `frontend-audit.md`,
`login.tsx`, as the isolated low-risk pilot) — but because this document's mandate
is protecting the sync behavior specifically, these criteria additionally gate
whenever the redesign reaches *any* of `index.tsx`/`money.tsx`/`invest.tsx` (the
audit groups them as one batch, "together, since they share the exact same risk
pattern"), even if that's not literally screen #1:

- [ ] `npm run typecheck` and `npm run test` both clean.
- [ ] For the pilot screen specifically: a manual check that opening it with
  stale `last_synced_at` data triggers exactly one automatic sync call (watch the
  backend log or network tab — one `POST` per connection, not zero, not repeated
  on re-render), and that tapping the manual sync/refresh control fires a sync
  call **even when data is fresh** (the "manual-refresh-always-syncs" contract in
  §3.1) — do this once per sync-bearing screen as each is reached, not just once
  for the whole app.
- [ ] Screenshot diff against the Phase 1 baseline for this screen at both
  viewports — differences should be exactly the intended redesign, nothing
  incidental (e.g. a dropped `DemoBanner`, a missing sync-error message like
  `invest.tsx`'s inline `sync.error.message` that `index.tsx`/`money.tsx` don't
  have — confirm that asymmetry was a deliberate decision, not an accidental loss).

### Phase 4 — Remaining screens

- [ ] Same three checks as Phase 3 (typecheck, screenshot diff, route/nav parity)
  applied per screen as it's redesigned, batched per `frontend-audit.md`'s grouping
  (read-mostly screens together, then `settings.tsx`, then the two chart screens).
- [ ] No change to any `lib/api.ts` function signature or TanStack Query key
  without updating the "frozen contract" list in `frontend-audit.md §5` — if a
  visual direction seems to need one, that's a flag to revisit the direction, per
  the `product-design` skill's own non-negotiable rule.
- [ ] A second `axe-core` smoke pass at the halfway point, diffed against Phase
  1's baseline pass — new violation types (not just count) get a look before
  continuing.
- [ ] `settings.tsx`'s Plaid/Schwab connection rows: manually re-verify the actual
  connect flow at least once after restyling (§3.3) — this is the one place a
  broken flow after a redesign is a trust-destroying event, not a cosmetic bug.

### Phase 5 — Cleanup

- [ ] Dead pre-redesign components/tokens removed; no orphaned styles left behind
  duplicating the new `Panel`/`StatTile`/`IconButton`/`HeroPanel` primitives
  (`frontend-audit.md §4`'s duplication findings resolved, not just added to).
- [ ] Full `make check` (ruff + backend pytest + frontend typecheck + `export:web`
  + the now-wired frontend `test` script) green.
- [ ] `make learning-check` still green — final proof the redesign never touched
  the nine learning files.
- [ ] Final complete screenshot set (§5) captured and archived as the new
  reference baseline, replacing the pre-redesign one for future changes.
- [ ] Final full `axe-core` pass across all 15 screens with the two Playwright E2E
  smoke scripts (§4) run once by hand: Google sign-in → home, and one sync button
  press → timestamp advances.
