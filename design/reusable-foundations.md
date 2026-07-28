# Posted reusable foundations — keep vs. replace

What already exists in `apps/client/src/` that a visual redesign should build on top of,
versus what's ad hoc/inconsistent and should be replaced by a real design-system layer. Cross-
references `frontend-audit.md` and `component-inventory.md` for detail; this file is the
"keep or replace" verdict.

## 1. `theme/tokens.ts` — keep the structure, repaint the palette

**Keep as-is (structural namespaces, referenced widely for layout math, not just paint):**
- `spacing` (`xxs`…`xxl`, 4-48px) — a clean geometric scale, consistently used.
- `radius` (`sm`/`md`/`lg`/`pill`) — small, coherent set; no evidence of ad hoc radius values
  outside a few specific spots (e.g. `AssetBadge`'s `radius.sm` in `HoldingsList.tsx`).
- `type` (`micro`…`display`, 10-38px) — used sparingly today (mostly `login.tsx` and
  `login/callback.tsx`); most screens hardcode font sizes directly in their own
  `StyleSheet.create` instead of referencing `type.*` (e.g. `index.tsx`'s `portfolioValue:
  { fontSize: 31 }` is a one-off value not in the `type` scale at all). **Worth doing during
  redesign**: audit whether the redesign's new type scale actually gets used from `tokens.ts`
  consistently, since today's screens mostly bypass it.
- `breakpoints` (`mobileNav: 920`, `assistantDock: 1600`) — correctly used by `AppShell.tsx`
  and `AssistantDrawer.tsx`, the two places that need a single source of truth for the
  sidebar/bottom-nav and assistant-dock cutovers. **Not used anywhere else** — every screen
  invents its own local breakpoint number instead (see §3). Recommend the redesign either (a)
  extends this namespace with a couple of named content breakpoints
  (e.g. `contentTwoColumn`, `contentWideRail`) that screens opt into, or (b) explicitly
  decides per-screen breakpoints are fine but picks values deliberately instead of the
  current scatter of 680/700/720/760/900/920/980/1080/1680 with no documented reasoning for
  why each screen's cutoff differs from its neighbors.
- `cardShadow` — a single soft-elevation recipe, spread into panel styles everywhere. Good
  candidate to keep as the one "elevated surface" shadow recipe, once panels are unified into
  a shared `Panel` component (see `frontend-audit.md` §4.1) so it's applied from one place
  instead of copy-pasted into 9+ `StyleSheet.create` blocks.

**Replace / actively redesign:**
- `colors` — this is the intended swap point for the whole visual direction (see
  `frontend-audit.md` §5). Concretely: `ink`/`inkMuted`/`inkFaint`/`line`/`lineStrong`/
  `canvas`/`surface*` form a reasonable neutral scale; `positive`/`negative`/`warning` (+
  their `*Soft` backgrounds) are the semantic state colors and are used correctly and
  consistently for gain/loss/pending throughout (a good pattern to keep even while changing
  the actual hex values). `teal`/`tealDark`/`tealSoft`/`blue`/`blueSoft` are the current single
  accent + one secondary accent — consistent with the skill's "one accent" guidance, so the
  redesign's new accent(s) should replace these keys' values rather than introduce a third or
  fourth ad hoc accent color. `purple`/`pink`/`orange`/`indigo`/`brown` exist **only** to feed
  `symbolColor.ts`'s deterministic per-ticker badge palette (`lib/symbolColor.ts` line 3-11)
  — not used anywhere else. Worth deciding explicitly whether the redesign keeps a
  multi-hue "identicon" treatment for ticker badges or replaces it with something monochrome
  (the skill's "restrained, monochrome-plus-one-accent" starting point argues against 5 extra
  decorative hues existing only for this).
- No dark-mode variants exist today (`AppShell`'s `safeArea`/`root` always use `colors.navy`/
  `colors.canvas` regardless of system theme). Not necessarily in scope for this redesign
  (native app, not a web artifact), but worth flagging since it's a real gap versus the
  `prefers-color-scheme` expectations called out generally in this environment's design
  guidance for web surfaces.

## 2. Chart interaction hooks (`lib/chartScrub.ts`, `chartZoom.ts`, `chartInteraction.ts`,
`chartMomentum.ts`) — keep entirely as-is

This is the strongest piece of "logic properly separated from presentation" in the codebase
and should be treated as a foundation, not touched:
- `useChartScrub` (`chartScrub.ts`) — headless pan/pointer-driven index selection, mode-aware
  (`'point'` vs `'bar'`), with a `resetKey` to clear selection when the underlying series
  changes shape (e.g. `StockPriceChart` resets on `${resolution}:${zoom.start}:${zoom.end}`,
  `index.tsx` composition line 249). Exposes `accessibilityValue`/`onAccessibilityAction`
  directly, so every chart built on it gets adjustable-slider semantics for free
  (`accessibilityRole="adjustable"` at each call site).
- `chartInteraction.ts`'s `barIndexForX`/`pointIndexForX`/`availableResolutions` are pure
  index/geometry math, independently testable (`chartInteraction.test.ts` exists).
- `chartMomentum.ts`'s `momentumColor` is a small, self-contained trend-coloring utility used
  only by `PortfolioChart`'s crosshair dot today — a reasonable pattern to reuse if new charts
  want a similar "local trend" visual cue.
- `useChartZoom` — pan/zoom range state consumed only by `StockPriceChart` today, but
  written generically enough (`zoom.start`/`zoom.end`/`zoom.zoomAtRatio`/`zoom.reset`) to
  reuse for any future zoomable series chart.

**Verdict**: three charts (`PortfolioChart`, `StockPriceChart`, `insiders.tsx`'s inline
`SentimentChart`) each build their own SVG/View visual layer on top of these shared hooks.
That's the right split — keep the hooks, let each chart's paint layer be redesigned
independently and even divergently per the skill's "signature element per screen" mandate.
The one exception: `insiders.tsx`'s `SentimentChart` is defined inline in the route file
rather than colocated as its own component the way `StockPriceChart/` is — if this screen's
chart grows in complexity during redesign, consider extracting it to match the
`StockPriceChart/` colocation pattern (component + hook/types together) rather than growing
further inside `insiders.tsx`.

## 3. `lib/format.ts` — keep entirely as-is

`money`, `number`, `percent`, `signedMoney`, `daysUntil`, `relativeTime` are small, pure,
consistently-used formatting functions with no state. Every screen goes through these rather
than hand-rolling `Intl.NumberFormat` calls (with a couple of screen-local exceptions that
build their own compact-number formatters for domain-specific needs —
`insiders.tsx`'s `signedCompact`, `stock/[symbol].tsx`'s `compactNumber`/`yieldOrDash` — those
are reasonable one-offs given they're MSPR/market-cap/dividend-yield specific formats, not
general-purpose). No changes needed here for a visual redesign; these are pure data-shaping,
not presentation.

## 4. `lib/symbolColor.ts` — keep the mechanism, revisit the palette

The hash-based deterministic ticker-badge coloring (`hashString` → palette index → alpha-
blended background) is a fine, cheap "no per-symbol design work needed" mechanism and should
be kept mechanically. What should be revisited is *which* colors feed it — see §1 above; this
is the only consumer of `colors.purple/pink/orange/indigo/brown`.

## 5. `components/ui.tsx` — keep the primitives, tighten the API surface

`SectionHeader`, `ActionButton`, `ErrorState`, `LoadingState`, `LevelPill` are all
well-adopted, prop-driven, and free of default values tied to one domain (`LevelPill`'s
level→color mapping is genuinely generic across urgent/important/notable/informational).
Keep all of these as the base of the new primitives layer.

`DemoBanner` and `LoadingState` both ship **default prop values that are investing-specific
copy** (`DemoBanner`'s default message references "Schwab" specifically; `LoadingState`'s
default label is "Loading portfolio") even though both components are used across money,
investing, and stock-research contexts that always override the default. This is a smell:
the components are generic, but their *defaults* leak one domain's assumptions. Recommend
either making these props required (forcing every call site to be explicit, which they
already are in practice) or picking genuinely generic defaults ("Loading…", "Sample data —
connect a live account to replace this.").

**Missing from `ui.tsx` today, needed to eliminate the duplication cataloged in
`frontend-audit.md` §4 / `component-inventory.md`:**
- `Panel`/`Card` — the exact `{borderWidth:1, borderColor:line, backgroundColor:surface,
  borderRadius:radius.lg, overflow:'hidden', ...cardShadow}` recipe copy-pasted 9+ times,
  with two screens (`news.tsx`, `event/[id].tsx`) accidentally diverging from it. This is the
  single highest-value primitive to add — it would make `SectionHeader`'s "always lives
  inside a panel" convention explicit and enforced rather than incidental.
- `StatTile`/`MetricCard` — 6+ independent reimplementations of label/value/caption stat
  blocks at slightly different sizes.
- `IconButton` — 5 near-identical 38×38/40×40 square icon buttons; also the natural place to
  fix the sub-44×44 touch-target issue the skill doc explicitly flags, in one spot instead of
  five.
- `HeroPanel` — 4 independent dark navy stat-hero implementations
  (`money.tsx`/`invest.tsx`/`insiders.tsx`/`stock/[symbol].tsx`).
- `ConnectionRow` — the settings.tsx banking/investing connection row pattern (icon, name+
  meta, demo-badge-or-sync/unlink-actions), currently duplicated wholesale between two panels
  in one file.
- `TextLinkAction` — the "label + arrow" chip pattern (`money.tsx`'s `TextAction`,
  `index.tsx`'s inlined equivalent, `insiders.tsx`'s `stockLink`,
  `stock/[symbol].tsx`'s `insiderAnalysisLink`).

## 6. `AppShell.tsx`'s responsive/layout logic — keep the mechanism, consolidate the numbers

The desktop-sidebar vs. mobile-bottom-nav switch (`desktop = width >= breakpoints.mobileNav`,
line 123) and the assistant's dock-vs-float-vs-float-above-tab-bar three-way branch
(`AssistantDrawer.tsx` lines 21-25) are both good, deliberate pieces of responsive
architecture worth keeping exactly as they are — they're the only two places in the codebase
that reference `theme/tokens.ts`'s `breakpoints` at all. The auth-gate + redirect logic (see
`frontend-audit.md` §3.2) is correct and should not be touched beyond restyling the loading
spinner itself. The account-menu (`menuOpen` state, backdrop-dismiss pattern, lines 268-312)
is a reasonable, self-contained dropdown implementation worth keeping.

**Worth revisiting, not necessarily "replacing"**: the sidebar footer's `marketStatus` block
(lines 216-223) hardcodes the caption "Demo environment" regardless of actual connection
state — it's decorative copy that doesn't reflect whether the user actually has a live
connection. If the redesign wants a real "demo vs. live" signal in the shell chrome (a
reasonable idea given how much of the rest of the app cares about this distinction), it should
be wired to real connection data, not left as static copy.

## 7. `PlaidLinkButton`/`PlaidLinkButton.native`/`PlaidInvestmentLinkButton` — keep the
integration boundary, don't try to unify the SDK calls

The Plaid Link integration (web SDK vs. native SDK vs. money-vs-investing endpoint pairing)
is inherently platform- and product-scoped; don't try to collapse the three files into one
generic "LinkButton" that branches internally on platform *and* product — that would make an
already-fiddly OAuth-adjacent integration harder to reason about. Do extract the **shared
visual shell** (button + help/error/success text block, `container`/`button`/`help`/`error`/
`success` styles) into one presentational component that all three files render, taking
`busy`/`error`/`success`/`disabled`/`label` as props — that removes the ~90% styling
duplication without touching the SDK-specific `connect()` logic in any of the three files.

## 8. `StockPriceChart/` colocation pattern — keep as the template, don't generalize its internals

As called out in the skill doc and `component-inventory.md`: this directory's shape
(component + `IndicatorToolbar`/`OscillatorPanel`/`PricePanel`/`RangeBrush`/`ParamPopover`
sub-components + `formatting.ts` with its own test file) is the right structure for any future
component that grows real internal complexity. Do not try to extract a generic "chart
component" that both this and `PortfolioChart`/`insiders.tsx`'s `SentimentChart` inherit
from — the three visualizations are different enough (multi-indicator OHLC vs. simple line
vs. bar chart) that a shared base would either be a leaky abstraction or would fight the
skill's per-screen signature-element requirement. Keep them separate; keep sharing only the
headless interaction hooks (§2).

## 9. Assistant plumbing (`lib/assistantSection.ts`, `assistantContext` prop chain) — keep
the mechanism, be deliberate about the coupling it creates

`lib/assistantSection.ts`'s tiny `useSyncExternalStore`-based store is a clean, minimal way
to let any screen declare "I'm a money/investing/general screen" without prop drilling or
context re-renders. Keep it. The `assistantContext` string prop chain
(`AppShell` → `AssistantDrawer` → `AssistantChat` → `api.sendAssistantMessage`) is also a
sound mechanism — but as documented in `frontend-audit.md` §3.4 and
`component-inventory.md`'s `AssistantChat` entry, the *wording* of these strings is
functionally load-bearing (both for the LLM's answers and for `AssistantChat`'s
`suggestedPrompts` substring-matching on rendered context text). A visual redesign should
treat these strings as content to review deliberately (do the words still say what's true
about the redesigned screen?) rather than incidental JSX to leave untouched or casually
reword.
