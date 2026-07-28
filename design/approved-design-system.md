# Posted — Approved design direction

Status: **approved**, synthesized from `design/frontend-audit.md`,
`design/competitor-similarity-audit.md`, `design/product-workflows.md`,
`design/redesign-directions.md`, `design/design-system-proposal.md`,
`design/accessibility-baseline.md`, and `design/testing-strategy.md`. This
document is the single source of truth going forward; where it disagrees with
one of those source documents, this document wins and the reason is stated.

## Design thesis

Posted is one person's real net worth, not a multi-tenant SaaS product with
separate "money" and "investing" features. The redesign's core move is
structural, not decorative: collapse the two-vertical IA (Money / Investing as
co-equal nav destinations) into **one net-worth view, filtered by lens**, and
make the plumbing that's actually unique to Posted — multi-provider sync
freshness, a causal read on what moved the numbers — the primary visible
structure instead of a caption buried three rows down. This is Direction B,
"The Position Spine," from `design/redesign-directions.md`, chosen over the
conservative statement direction (safe but doesn't fix the debrief/orphaned-
route/decorative-sync-dot problems the audits found) and the experimental
narrative-stream direction (most original, but leans on generated-text entity
reliability that's too risky to bet a real financial app's trust on).

## Product identity

One financially-engaged individual, checking their own real Plaid/Schwab-
linked money, alone, most often on a phone, doing a status check rather than
a task (`design/product-workflows.md` §1). Not a trader in the moment of
opening the app; not a team; no collaboration surface exists or should be
designed for. The two highest-frequency workflows are "did anything unusual
happen" and "what's my net cash," both glance-speed; the deepest workflow
(insider/news judgment) is the one place exploration is the right mode — see
`product-workflows.md` §3 for the full per-workflow optimization table, which
this design system treats as settled.

## Information architecture

- **One net-worth spine replaces `index.tsx` + `money.tsx` + `invest.tsx` as
  separate primary destinations.** Default view is "Everything"; inline lens
  chips (`Everything / Cash / Investments`) filter Movement/Sync/Attention/
  Ledger bands in place — no navigation, no route change. `money`/`invest`
  survive only as redirect routes (to `/` with the lens preselected) for deep
  links and back-compat, per `redesign-directions.md`'s Direction B spec.
- **This is also the fix for the debrief being stranded on web-only.** The
  spine is a single-column, full-width-band layout by construction — it works
  identically on a 390px phone and a 1440px desktop (content within a band
  reflows; band order and presence do not). The morning debrief becomes the
  spine's default content, cross-platform, closing the single highest-impact
  gap `product-workflows.md` found (finding c).
- **Feed / News / Holdings / Insider activity collapse from four co-equal
  sidebar items into one "Portfolio detail" destination** with in-page
  tabs/segmented control, landing on whichever lens the entry point implies
  (tapping a holding → Holdings tab; tapping an impact event → Feed tab).
- **Sidebar becomes: the spine (default) + lens chips + a compact "Explore"
  rail** for the less-frequent destinations (Portfolio detail, Transactions,
  Subscriptions, Settings). The day-to-day loop never requires opening
  Explore.
- **`/assistant` gets a real entry point instead of being deleted.** Add an
  "expand" affordance in `AssistantDrawer` (next to its close button) that
  navigates to `/assistant` carrying the current section/context — the route
  already works, it just has zero navigation path today
  (`product-workflows.md` finding d). On ≥1600px (`assistantDock`) the
  assistant stays docked as today; the expand target matters specifically for
  narrower widths where docking isn't available.
- **Settings keeps add/remove-connection responsibility; connection *health*
  moves to the Sync band**, which is where the person will actually notice
  something's wrong (per `product-workflows.md` §6a). Settings' connection
  rows become the Sync band's "see full detail" destination, not a
  parallel implementation.

## Navigation model

Default: the spine, lens chips inline at its top, Explore icon top-right for
the encyclopedic destinations, assistant docked (≥1600px) or reachable via a
persistent entry point that expands to `/assistant` (<1600px). Mobile bottom
nav is redesigned around this shape rather than kept as today's four-items-
by-omission set (`product-workflows.md` finding d) — exact tab set is a
migration-plan decision (Phase B), not fixed here, but Settings must be
reachable in ≤2 taps given connection health is a trust-critical workflow.

## Typography

**Amendment to `design-system-proposal.md` §3.3**, stated explicitly: that
proposal recommended system-font-only everywhere, reasoning that Posted's
"who" (checks daily, values legibility) beats expressive type. That's the
right call for a direction with no other differentiation mechanism, but
Direction B's signature *is* a typographic distinction — "measured fact" vs.
"assistant-narrated context" need to read as different registers without
relying on color alone (color is reserved for state per §Color below). Adopt
Direction B's pairing instead: **Space Mono** for every measured figure
(dollars, percents, tick timestamps), **Manrope** for labels/prose/narrated
notes. Two families only — no third display face, no per-screen typeface
variation. Both via `@expo-google-fonts/space-mono` and
`@expo-google-fonts/manrope`, loaded once in the root layout. This is a
functional choice (the pairing does real signaling work in the Movement
band), not decoration, so it doesn't violate `app.md`'s "save expression for
marketing" rule — it's the one exception the rule itself allows for when
type *is* the mechanism, not an accessory.

Scale: adopt `design-system-proposal.md` §3.1's ten-step scale unchanged
(sized from what's already shipping, not invented) — `label`/`labelWide`/
`caption`/`body`/`bodyLarge`/`statValue`/`statValueLarge`/`panelTitle`/
`pageTitle`/`pageTitleMobile`/`display`/`displayDesktop`. Keep
`fontVariant: ['tabular-nums']` on every numeral (already correct where used;
enforce via the `StatTile`/spine-row primitives owning it, not per-screen
discipline).

## Visual hierarchy & component geometry

Adopt `design-system-proposal.md` §§1-2, 4-6 in full: the two-layer token
architecture (primitives → semantic roles), the elevation ladder
(`raised`/`floating`/`overlay`, unchanged `cardShadow` as `raised`), radius
scale (`sm:4 / md:8 / lg:12 / xl:16 / pill:999`), sizing tokens (`touchMin:44`
solving the 38×38 touch-target violation via `hitSlop`, not by inflating
visual chrome), and the six new primitives (`Panel`, `StatTile`, `IconButton`,
`ConnectionRow`, `FilterChip`, focus ring) that consolidate the nine-file
Panel duplicate, the seven-file StatTile duplicate, and the rest of §9's
anti-duplication table.

**One addition specific to Direction B**: the spine's bands (Position,
Movement, Sync, Attention, Ledger) are **not** `Panel` instances. Per
`redesign-directions.md`, bands are full-width, no card boundary, separated by
full-bleed hairlines, with a `radius.instrument` (2–4px) reserved only for the
sync-tick marks themselves — this is deliberately a second, flatter geometry
than `Panel`'s rounded-card treatment, used specifically for the spine's
primary bands. `Panel` remains correct and unchanged for everything else
(Settings rows, Portfolio-detail tabs' content, the Explore destinations,
holding/transaction detail expansions) — this is not a second competing
design language, it's one flush band type reserved for exactly one screen
shape, exactly as `design-system-proposal.md` §5.1 already scopes `Panel`
variants by role rather than by screen.

## Color roles

Adopt `design-system-proposal.md` §2 in full, including the new `stale`/
`live`/`demo` semantic roles this redesign specifically requires (per
`product-workflows.md` §5.3/§6c and §6e — the sync dot must stop being
hardcoded green, and demo-vs-live needs the same permanent ambient treatment
sync freshness gets, not a dismissible banner). The sync-tick colors on the
spine (teal fresh <15min, amber aging, red stale >4hr) reuse existing semantic
tokens exactly as specified — no new hues invented for this.

## Motion

Adopt `design-system-proposal.md` §7's baseline (150ms micro / 200ms panel,
`Animated` core API, no `reanimated` yet, full `prefers-reduced-motion`
compliance) **plus** Direction B's two Posted-specific exceptions, both
justified as state-communication, not decoration:

- The actively-syncing tick's breathing-opacity loop (1.6s ease-in-out,
  stops the instant sync resolves) — the one ambient/looping animation
  allowed anywhere, because it's the literal visual meaning of "syncing now."
- The digit-column settle (spring, stiffness 280/damping 18/mass 0.3, ~300–
  400ms) fired only when a sync completes and a real value changes — never on
  first paint/mount.

Login keeps its one-time bolder hero entrance exception, unchanged from the
general floor's carve-out.

## Responsive principles

Adopt `design-system-proposal.md` §6 in full: the consolidated `compact:720 /
mobileNav:920 / wide:1280 / assistantDock:1600` breakpoint set, the shared
`useBreakpoint()` hook (no screen may declare its own numeric cutoff again —
closes the 7-screen breakpoint-drift finding), and the explicit requirement
that `invest.tsx`'s content (folded into the Investments lens) get a genuine
mobile-specific layout pass, since it's the one primary screen flagged as
having none today.

## Accessibility requirements (non-negotiable, verified against real findings)

Beyond the general WCAG 2.1 AA floor already stated in
`.agent/skills/product-design/SKILL.md`, these five are **confirmed real bugs**
from `design/accessibility-baseline.md` and must be fixed as part of the
screens that touch them, not deferred:

1. Chart drag-to-inspect (`StockPriceChart`, `PortfolioChart`) has no
   keyboard path on web — add one when these charts are touched.
2. `AssistantDrawer` has no focus trap, no Escape-to-close, no return-focus on
   close — fix when the drawer is redesigned (Phase B, shell work).
3. Both notification `Switch` controls in `settings.tsx` need
   `accessibilityLabel` — trivial, fix immediately, doesn't need to wait for
   a visual redesign of that screen.
4. `inkFaint` fails 4.5:1 contrast in 89 sites — the semantic-role adoption
   above should route caption/tertiary text through a corrected value; do
   not carry the failing value forward into `color.textTertiary`.
5. Icon-only buttons need `accessibilityRole="button"` consistently (some
   have labels but not the role) — enforced structurally once `IconButton`
   (§5.3 of the design-system proposal) is the only way to build one.

## Component-library policy

Adopt `design-system-proposal.md` §8 verbatim: RN core/Expo primitives and
`expo-router` as-is; `lucide-react-native` and `react-native-svg` as the sole
icon/chart foundations; every new Posted-specific primitive built from `View`/
`Pressable`/`Text` in `components/ui.tsx`; shadcn/ui, Base UI, Origin UI,
react-bits, Magic UI, Motion/motion-primitives used only as read-only pattern
references, never installed, never imported.

## Explicit anti-patterns (standing, every screen)

Everything already listed in `.agent/skills/product-design/SKILL.md`'s
non-negotiable section, plus these two confirmed-in-this-codebase additions:

- **No more independently-invented "hero panel" implementations.** Four exist
  today (`money.tsx`, `invest.tsx`, `insiders.tsx`, `stock/[symbol].tsx`) —
  the redesign gets exactly one (`Panel variant="inverted"`), and the spine's
  bands don't use a hero panel at all (see geometry section above).
- **No color-only status signaling.** The green sync dot and any future
  state indicator must pair color with a glyph/text, matching the pattern
  `LevelPill` already gets right.

## What stays exactly as-is (do not touch for visual reasons)

Per `frontend-audit.md` §5's frozen-contract list: `lib/api.ts`/`marketApi.ts`
call signatures and every existing query key, `useConnectionSync`'s hook
signature and each screen's `invalidateKeys`, the chart interaction hooks
(`chartScrub`/`chartZoom`/`chartInteraction`/`chartMomentum`) and their
callback contracts feeding the assistant, and the three bespoke chart
components themselves (genuinely different visualizations, not a
duplication problem — forcing one shared chart component would fight the
signature-element requirement).
