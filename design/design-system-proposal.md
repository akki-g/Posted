# Posted design system proposal — tokens & component architecture

Status: proposal, not yet implemented. No application code was changed to produce
this document. It resolves `frontend-audit.md` §4-5 and `competitor-similarity-audit.md`'s
token-usage findings into one concrete, adoptable system: exact values, exact names,
exact component boundaries. Where those two documents already established a fact
with file:line citations, this proposal treats it as settled and builds on it rather
than re-deriving it.

Grounding: `.agent/skills/product-design/SKILL.md` (Posted domain + platform reality),
`.agent/skills/frontend-design-principles/references/principles.md` (token mechanics),
`.agent/skills/frontend-design-principles/app.md` (application-design direction),
`.agent/skills/frontend-ui-engineering/SKILL.md` (component/state rules). Current
state: `apps/client/src/theme/tokens.ts`, `apps/client/src/components/ui.tsx`,
`apps/client/src/components/AppShell.tsx`, all 16 files under `apps/client/src/app/`.

---

## 0. What the audit actually shows

Confirmed by direct repo inspection (not assumed):

- **The `type` scale in `tokens.ts` (`micro`…`display`) is referenced nowhere in the
  app** except `login.tsx` (and even there, alongside raw literals). Every other
  screen hardcodes `fontSize`. Repo-wide, screens use **24 distinct raw font sizes**
  (7, 8, 9, 10, 11, 12, 13, 14, 15, 17, 18, 19, 20, 22, 23, 24, 25, 27, 30, 31, 34,
  36, 40, 56) — a scale exists on paper, reality is unconstrained.
- **The `spacing` scale is referenced almost nowhere** outside `login.tsx`. Observed
  raw `gap` values alone: 1, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 16, 22 — more than
  half don't belong to `xxs4/xs8/sm12/md16/lg24/xl32/xxl48`.
- **The bordered/shadowed "panel" container is byte-for-byte duplicated in 9 files**
  (`index.tsx`, `money.tsx`, `invest.tsx`, `holdings.tsx`, `feed.tsx`,
  `subscriptions.tsx`, `transactions.tsx`, `insiders.tsx`, `settings.tsx`):
  `{ borderWidth:1, borderColor: colors.line, backgroundColor: colors.surface,
  borderRadius: radius.lg, overflow:'hidden', ...cardShadow }`, verified via direct
  read of each file's `panel` style block.
- **The metric-tile pattern (label/value/caption, tabular-nums) is independently
  reimplemented in 7 files** (`index.tsx`, `money.tsx`, `invest.tsx`, `holdings.tsx`,
  `insiders.tsx`, `subscriptions.tsx`, `transactions.tsx`) with drifting font sizes
  (22/23/24/30) and `marginTop` (13–18) for what is visually the same component.
- **`colors.purple/pink/orange/indigo/brown` are not dead** — `lib/symbolColor.ts`
  and `lib/indicators/registry.ts` both consume them, but each hand-assembles its
  own categorical array, and both **improperly mix semantic state colors into a
  decorative categorical set** (`symbolColor.ts` includes `colors.teal`;
  `indicators/registry.ts` includes `colors.blue` and `colors.warning`). Validated
  with this session's dataviz-palette checker (`scripts/validate_palette.js`):
  `colors.teal` fails the categorical chroma floor outright (reads gray in a
  categorical role); the 5 unclaimed colors (purple/pink/orange/indigo/brown) pass
  every check standalone. See §3.6.
- **Every screen defines its own responsive cutoff, none agreeing with
  `breakpoints.mobileNav` (920)**: `index.tsx` 1080 & 1680, `money.tsx` 1080 & 700,
  `subscriptions.tsx` 900 & 700, `insiders.tsx` 980 & 720, `transactions.tsx` 680,
  `news.tsx` 920 (this one matches by coincidence), `stock/[symbol].tsx` 980/760/520.
  Between 900–1080px, different screens are already showing mismatched combinations
  of shell chrome and content layout.
- **An un-tokenized "on-navy" sub-palette has been hand-invented per file.** At
  least 7 near-duplicate blue-grays stand in for "muted text on a dark surface"
  (`#9DA9B9`, `#AAB4C1`, `#8FA0B7`, `#7F8DA1`, `#9EABBD`, `#B8C1CE`, `#8F9CAE`), and
  5 near-duplicate dark blues stand in for "hairline on a dark surface" (`#263247`,
  `#2A3548`, `#2D394C`, `#303D50`, `#526176`) — verified across `AppShell.tsx`,
  `money.tsx`, `invest.tsx`, `insiders.tsx`, `news.tsx`, `subscriptions.tsx`.
  `insiders.tsx` additionally hand-built a **third, entirely separate** positive/
  negative/neutral trio tuned for dark backgrounds (`#8CE1B1`/`#163B2B`/`#3B8960`
  and `#F1A0A9`/`#44252D`/`#A95660`) that has no name and is invisible to every
  other screen.
- **Three unrelated implementations of "is this demo or live data"** exist
  side by side: `ui.tsx`'s `DemoBanner`, `settings.tsx`'s inline `demoStatus` pill,
  and `AppShell`'s sidebar `marketStatus`/`statusDot` (whose green dot, `#32C98C`,
  doesn't match `colors.positive` and whose caption is a hardcoded string, not
  derived from real connection state).
- **`privateMode` masking (`'••••'` in place of a balance) is hand-rolled in 4
  places** (`index.tsx`, `invest.tsx`, `money.tsx` — twice — `DebriefPanel.tsx`)
  with **inconsistent mask width**: `'$••••••'`, `'$••••'`, `'••••'`, `'••'` all
  appear for conceptually the same "hide this number" action.
  Same finding for the filter-chip "active" state: `feed.tsx` colors it navy,
  `transactions.tsx` colors it `tealSoft` with a raw hex border — two treatments of
  one interaction.
- **No visible focus ring exists anywhere.** Every `TextInput` on web explicitly
  sets `outlineStyle: 'none'` (`holdings.tsx`, `feed.tsx`, `transactions.tsx`,
  `AssistantChat.tsx`, `MarketSearch.tsx`) and nothing replaces it — keyboard users
  lose all focus indication in search and chat inputs.
- **No motion library and no `Animated` usage exists anywhere** in the app today
  (confirmed: no `react-native-reanimated` dependency, zero uses of RN's `Animated`
  API). Every state change is an instant style swap. This is a from-scratch
  addition, not a fix to an inconsistent existing system.
- Two things are **already correct and should be explicitly preserved**: the
  uppercase, letter-spaced micro-label convention for metric labels ("NET CASH
  POSITION", "TOTAL RETURN"), and `fontVariant: ['tabular-nums']` on money values.
  Both read as ledger/terminal, not generic SaaS — see `app.md`'s "Data & Analysis"
  direction. The `LevelPill` component is also already correct in never using color
  alone (dot + uppercase text together) — the pattern below extends that rule, it
  doesn't introduce it.

---

## 1. Token architecture: two layers

Per `principles.md`'s "Surface & Token Architecture" — colors must trace back to a
small set of primitives, not be invented ad hoc. Posted's actual problem is not that
primitives are missing (`tokens.ts` already has a fairly disciplined primitive set:
canvas/surface/ink/line/navy/teal/positive/negative/warning) — it's that **there is
no semantic role layer above the primitives**, so screens reach for `colors.teal`
whether they mean "brand accent," "this is the live indicator," or "this is
selected," and reach for raw hex whenever the primitive layer doesn't cover a
dark-surface case.

The fix is **not** a rename of everything. It's:

1. Keep the primitive layer (`palette`), values validated below, with the missing
   dark-surface and status-on-dark primitives added (currently invented per-file).
2. Add a semantic role layer (`color`) that every component consumes. Roles map to
   primitives 1:1 or 2:1 (soft/strong pairs) — never invent a new hex at the
   component call site again.
3. Split the categorical/chart palette out of `color` entirely — it's not a UI
   state color, it's a data-identity color, and mixing it into the same object is
   what caused `symbolColor.ts`/`indicators/registry.ts` to decoratively reuse
   `teal`/`blue`/`warning`.

RN platform note: `principles.md`'s `oklch()`/`color-mix()` CSS guidance does not
run on iOS/Android — React Native's `StyleSheet` values must be static hex/rgba
computed ahead of time, no `color-mix()`, no CSS variables, no `light-dark()`. The
proposal below applies the *reasoning* (perceptually even elevation steps, one
soft/strong pair per role) but every value is precomputed, not computed at runtime.
Dark mode is out of scope for this proposal — Posted has one shipped surface
today (light canvas + dark inverted panels used as a structural accent, not a
theme) — but the primitive layer's structure (see §2.4) is what a future dark
theme would key off, so it's built to extend rather than be rebuilt.

---

## 2. Color

### 2.1 Primitives — validate, extend

Keep as-is (already sound, already used consistently everywhere they're used):

```ts
canvas:        '#EDF0F4'
surface:       '#FFFFFF'
surfaceMuted:  '#E9EDF1'
surfaceStrong: '#DDE3E8'
ink:           '#121A26'
inkMuted:      '#5B6675'
inkFaint:      '#7D8794'
hairline:      '#D6DCE2'   // renamed from `line` — see §2.2 naming note
hairlineStrong:'#B7C0CA'   // renamed from `lineStrong`
navy:          '#101827'
navyRaised:    '#182235'
teal:          '#087E8B'
tealDark:      '#075E68'
tealSoft:      '#DDF2F2'
positive:      '#14804A'
positiveSoft:  '#DFF3E8'
negative:      '#C73E4D'
negativeSoft:  '#FBE5E7'
warning:       '#9A5B00'
warningSoft:   '#FFF0D6'
blue:          '#2764D8'
blueSoft:      '#E6EEFD'
white:         '#FFFFFF'
transparent:   'transparent'
```

**Add** — these already exist in the shipped app as raw, uncoordinated hex; this
promotes them to named primitives instead of leaving them to be reinvented per
file. Values are computed from the actual in-use cluster (not invented):

```ts
// On-navy text — consolidates 7 near-duplicate grays found across AppShell.tsx,
// money.tsx, invest.tsx, insiders.tsx, news.tsx, subscriptions.tsx
inkOnDarkMuted:  '#A3AFC0'   // was #9DA9B9/#AAB4C1/#8FA0B7/#9EABBD/#B8C1CE/#8F9CAE
inkOnDarkFaint:  '#75839A'   // was #6F7C8F/#768397

// On-navy borders — consolidates 4 near-duplicate dark blue-grays
hairlineOnDark:       '#2B3749'  // was #263247/#2A3548/#2D394C/#303D50
hairlineOnDarkStrong: '#526176'  // already shipped once (insiders.tsx neutral-signal
                                 // pill border) — validated, adopted as-is

// Financial state, tuned for the navy surface — this is not a new invention,
// it's `insiders.tsx`'s already-shipped signal-pill trio, promoted from
// unnamed local hex to a shared primitive so every dark panel uses the same one
positiveOnDark:       '#8CE1B1'
positiveOnDarkSoft:   '#163B2B'
positiveOnDarkBorder: '#3B8960'
negativeOnDark:       '#F1A0A9'
negativeOnDarkSoft:   '#44252D'
negativeOnDarkBorder: '#A95660'

// A brighter, solid-fill green distinct from `positive` — a status DOT sitting on
// navy needs a different lightness step than positive TEXT on white for correct
// legibility; this is the already-shipped AppShell status-dot color, named.
liveDotOnDark: '#32C98C'

// Named borders that were previously raw literals repeated 5x / 1x respectively
accentSoftBorder:  '#A6D9D9'  // DemoBanner / assistant-active border, was raw hex
negativeBorder:    '#E8B9BE'  // ErrorState border, was raw hex
```

### 2.2 Naming change: `line` → `hairline`

Small, deliberate rename. `line` is a generic CSS-ism (could belong to any design
system); `hairline` is what the value actually is (a 1px rule, the bank-statement/
ledger hairline the product-design skill's own color-world example calls for) and
matches RN's own `StyleSheet.hairlineWidth` concept, which §5.3 recommends adopting
for the divider use case specifically. This is the only primitive rename in the
proposal — everything else is additive.

### 2.3 Semantic roles — what components actually consume

This is the layer that was missing. Every component in §4 reads from `color.*`,
never `palette.*` directly, so a re-skin only ever touches this table.

| Role | Value (→ primitive) | Replaces / fixes |
|---|---|---|
| `color.canvas` | `palette.canvas` | — |
| `color.surface` | `palette.surface` | — |
| `color.surfaceSunken` | `palette.surfaceMuted` | recessed fields, table stripes, pressed-panel background |
| `color.surfaceSelected` | `palette.surfaceStrong` | selected row/tab track |
| `color.surfaceInverted` | `palette.navy` | the hero/sidebar register — now a named *role* (data provenance: "this block is a synthesized summary," not decoration) |
| `color.surfaceInvertedRaised` | `palette.navyRaised` | active row on an inverted surface |
| `color.textPrimary` | `palette.ink` | — |
| `color.textSecondary` | `palette.inkMuted` | — |
| `color.textTertiary` | `palette.inkFaint` | — |
| `color.textOnInvertedPrimary` | `palette.white` | already consistent everywhere it's used — validated, not changed |
| `color.textOnInvertedSecondary` | `palette.inkOnDarkMuted` | replaces the 6-value hex cluster |
| `color.textOnInvertedTertiary` | `palette.inkOnDarkFaint` | replaces the 2-value hex cluster |
| `color.borderHairline` | `palette.hairline` | — |
| `color.borderHairlineStrong` | `palette.hairlineStrong` | focus-adjacent emphasis, selected-card border |
| `color.borderOnInverted` | `palette.hairlineOnDark` | replaces the 4-value hex cluster |
| `color.borderOnInvertedStrong` | `palette.hairlineOnDarkStrong` | — |
| `color.accent` | `palette.teal` | the **one** brand/interactive color — primary buttons, links, selected nav rail, checkbox/switch "on" |
| `color.accentPressed` | `palette.tealDark` | pressed/active state of anything using `accent` |
| `color.accentSoft` | `palette.tealSoft` | tinted fill behind an accent icon/badge/active chip |
| `color.accentSoftBorder` | `palette.accentSoftBorder` | border for an `accentSoft`-filled chip/banner |
| `color.positive` | `palette.positive` | financial gain, always paired with `+`/▲ glyph, never color-alone |
| `color.positiveSoft` | `palette.positiveSoft` | positive chip/badge fill |
| `color.positiveOnInverted` | `palette.positiveOnDark` (+ `Soft`/`Border`) | gain, on a navy panel |
| `color.negative` | `palette.negative` | financial loss, always paired with `-`/▼ glyph |
| `color.negativeSoft` | `palette.negativeSoft` | — |
| `color.negativeBorder` | `palette.negativeBorder` | `ErrorState` border, named |
| `color.negativeOnInverted` | `palette.negativeOnDark` (+ `Soft`/`Border`) | loss, on a navy panel |
| `color.attentionUrgent` | `= color.negative` | **reused intentionally** — the impact-feed's "urgent" tier IS a loss-coded red; no new hue |
| `color.attentionImportant` | `palette.warning` | — |
| `color.attentionNotable` | `palette.blue` | — |
| `color.attentionRoutine` | `palette.inkMuted` | — |
| `color.live` | `= color.positive` | sync-freshness role, reused hue (see §2.5) |
| `color.liveDot` | `palette.liveDotOnDark` | the solid status dot specifically (sidebar, connection row) |
| `color.stale` | `= color.attentionImportant` (warning) | data older than the sync SLA (see §2.5) — reused hue, amber not red: stale is a caution, not an error |
| `color.demo` | `= color.accent` | sample/demo data marker (see §2.6) — reused hue, teal, so "demo" reads as "informational," never alarming |
| `color.demoSoft` | `= color.accentSoft` | — |
| `color.focusRing` | `palette.teal` at 100% + 2px offset | see §5.4 — the missing focus-visible treatment |

**Reuse is deliberate, not laziness.** `attentionUrgent = negative`, `live = positive`,
`demo = accent` are the same hue on purpose — Posted has exactly five meaningfully
different *judgments* a color can carry (positive, negative, caution/stale,
informational/brand, neutral), and `stale`/`demo`/`urgent`/`live` are secondary
labels for those same five judgments, applied to a different subsystem (sync
freshness, data provenance, feed priority). Giving each subsystem its own hue would
recreate the exact "purple/pink/orange used because they were available" problem
this proposal is fixing in §2.6 — a color should mean one of five things anywhere
in the app, and a screen-specific label (`stale`, `demo`, `urgent`) just says which
subsystem is asking.

### 2.4 Elevation via surface, not shadow escalation

Per `principles.md`'s "Depth Strategies — choose ONE and commit": Posted already
committed to **single shadow** (`cardShadow`) for raised content, plus **surface
color shift** for the inverted (navy) register. Don't add a second depth language.
The elevation ladder is:

| Level | Surface | Shadow | Used for |
|---|---|---|---|
| 0 | `color.canvas` | none | app background |
| 1 | `color.surface` | `elevation.raised` (= today's `cardShadow`, unchanged) | panels, cards, metric tiles |
| 2 | `color.surface` | `elevation.floating` (new, below) | dropdown menus, popovers — promotes `AppShell`'s already-shipped one-off `userMenu` shadow to a named token instead of a local literal |
| 3 | `color.surface` | `elevation.overlay` (new, below) | the assistant drawer's floating panel — currently its own undocumented variant per `competitor-similarity-audit.md` |

```ts
elevation = {
  raised: {
    shadowColor: '#0B1420', shadowOpacity: 0.06, shadowRadius: 18,
    shadowOffset: { width: 0, height: 8 }, elevation: 2,
  }, // = current cardShadow, unchanged
  floating: {
    shadowColor: '#0B1420', shadowOpacity: 0.12, shadowRadius: 12,
    shadowOffset: { width: 0, height: 4 }, elevation: 6,
  }, // = AppShell userMenu's existing values, promoted
  overlay: {
    shadowColor: '#0B1420', shadowOpacity: 0.18, shadowRadius: 28,
    shadowOffset: { width: 0, height: 12 }, elevation: 10,
  }, // new — one step past floating, for the assistant drawer
}
```

`color.surfaceInverted` (navy) is not "level -1" — it's a parallel, non-elevated
register (a different kind of content, not a different stacking height), which is
why it keeps the same `elevation.raised` shadow when it appears as a hero panel
rather than getting its own shadow language.

### 2.5 Stale / live — new semantic pair, backed by real data Posted already has

`settings.tsx` already renders `synced {relativeTime(connection.last_synced_at)}`
as plain text with no visual treatment — the data existed, the semantic role
didn't. Proposal: a connection or panel is **live** if `last_synced_at` is within
the sync SLA for its source (recommend 15 min for Plaid money data, 1 hour for
Schwab/Plaid Investments — matches typical provider refresh cadence; exact SLA is
a product decision, not a design-token one), otherwise **stale**. This is a boolean
derived from data the API already returns, not a new field.

- `live`: no persistent visual noise — freshness is the unmarked default. Only
  the relative-time caption (`inkFaint`/`inkOnDarkFaint`) is shown.
- `stale`: the panel/connection row gets (a) the `stale` (warning/amber) color on
  the relative-time caption instead of `inkFaint`, and (b) a small dot or
  `RefreshCw`-style glyph next to it — never color alone. No border, no
  background change, no blocking banner: stale means "trust this a little less,"
  not "something is broken."

### 2.6 Demo — consolidates 3 existing implementations into 1

Per `frontend-audit.md` §4.7: `DemoBanner`, `settings.tsx`'s inline `demoStatus`
pill, and `AppShell`'s sidebar `statusDot` are three unrelated visual treatments of
one underlying fact. Proposal: one boolean role, `demo`, consumed by one component
(`ConnectionRow`, §4.5) and one banner (`DemoBanner`, kept). The type-layer
inconsistency already flagged (`ConnectionStatus.demo_mode` vs.
`MoneyConnectionStatus.is_demo`) is a data-layer fix outside this proposal's scope,
but the component must accept a single normalized `demo: boolean` prop regardless
of which field name the call site maps it from — this is a prop-contract decision,
not a backend change, so it doesn't violate the "never rewrite business logic"
rule.

### 2.7 Categorical / chart palette — separated from semantic color entirely

Not part of `color`. A new, standalone export, because a categorical color must
never collide with a state color (a chart line tinted "warning amber" must not be
misread as "something's wrong").

```ts
export const chartCategorical = [
  '#7357B8', // was colors.purple
  '#C74B8F', // was colors.pink
  '#C15A1F', // was colors.orange
  '#4F5FA8', // was colors.indigo
  '#B5651D', // was colors.brown
] as const;
```

Validated this session with the dataviz skill's `validate_palette.js`
(`node scripts/validate_palette.js "#7357B8,#C74B8F,#C15A1F,#4F5FA8,#B5651D"
--mode light`): **all 5 checks pass** — lightness band, chroma floor, CVD
adjacent-pair separation (worst ΔE 8.1 protan), normal-vision floor (worst ΔE
15.4), contrast vs. surface. In `--mode dark`, 4 of 5 pass; `#4F5FA8` (indigo)
warns at 2.93:1 contrast against a dark test surface — meaning on Posted's
`surfaceInverted` navy, any indigo-categorical mark (a 4th+ ticker/indicator in a
dark hero panel) **must** carry a direct label, not rely on hue alone. This is
already required by §6's "always label ≥2 series" rule, so no new rule, just a
concrete case where it's load-bearing.

**Two required fixes to how this palette is consumed**, both currently violated:

1. `lib/symbolColor.ts`'s `PALETTE` must drop `colors.teal` (validated: teal fails
   the categorical chroma floor standalone — `[FAIL] Chroma floor below floor
   (reads gray): #087E8B 0.092` — it visually reads as a muted gray next to the
   other five, not as "the accent color," when used as one entry among many).
2. `lib/indicators/registry.ts`'s `INDICATOR_PALETTE` must drop `colors.blue` and
   `colors.warning` — both are claimed semantic roles (`attentionNotable`,
   `attentionImportant`/`stale`) and must never appear as a decorative, hash-
   assigned categorical color.

Both files should import the same `chartCategorical` array instead of hand-
assembling their own — one canonical categorical palette, not two independently
drifting ones.

---

## 3. Typography

### 3.1 Verdict: the declared scale is unused and doesn't match reality — replace it, keep what's already working inside the reality

`type.micro/caption/body/bodyLarge/title/heading/display` (10/12/14/16/20/28/38)
is referenced nowhere except `login.tsx`, and even `login.tsx` mixes it with raw
literals (`fontSize: 40`, `fontSize: 56` for its own hero, `fontSize: 13` for
feature copy) — so it's failing even in its one adopter. Meanwhile two conventions
that were never tokenized are already correct everywhere they appear and should be
locked in rather than replaced: the uppercase, letter-spaced micro-label (metric
labels, level pills, nav-group headers) and `tabular-nums` on every money value.

Per `principles.md`'s typography guidance (display/body/small tiers,
600-weight/tight-tracking headlines, monospace-style tabular numerals for data),
the replacement scale below is sized directly from the values already shipping
across the app (not invented), collapsing the 24-value spread down to 10 named
steps:

```ts
export const type = {
  // Uppercase micro-labels — two tiers, a deliberate distinction: `label` marks
  // a piece of data (a metric, a badge, a chip); `labelWide` marks a structural
  // region (a nav group, a page eyebrow). Consolidates values that had drifted
  // to 9/10px and 0.7–1.6 tracking across 6+ files into exactly two.
  label:      { size: 9,  lineHeight: 12, weight: '800', tracking: 0.8 },
  labelWide:  { size: 10, lineHeight: 13, weight: '700', tracking: 1.4 },

  caption:    { size: 11, lineHeight: 15, weight: '500', tracking: 0 },
  body:       { size: 13, lineHeight: 18, weight: '500', tracking: 0 },
  bodyLarge:  { size: 15, lineHeight: 21, weight: '500', tracking: 0 },

  // Numeric display — always paired with fontVariant: ['tabular-nums']
  statValue:      { size: 22, lineHeight: 26, weight: '700', tracking: -0.2 },
  statValueLarge: { size: 30, lineHeight: 35, weight: '700', tracking: -0.4 },

  panelTitle:      { size: 15, lineHeight: 20, weight: '700', tracking: -0.1 }, // = SectionHeader today, validated unchanged
  pageTitle:       { size: 30, lineHeight: 36, weight: '600', tracking: -0.7 }, // = AppShell desktop title today, validated unchanged
  pageTitleMobile: { size: 25, lineHeight: 31, weight: '600', tracking: -0.5 }, // = AppShell mobile title today, tracking added

  // Login-only hero moment — the one screen the skill explicitly allows a
  // bolder register. Values match what login.tsx already ships (40 / 56,60).
  display:        { size: 40, lineHeight: 46, weight: '600', tracking: -0.8 },
  displayDesktop: { size: 56, lineHeight: 60, weight: '600', tracking: -1.2 },
} as const;
```

Each step is an object (`{ size, lineHeight, weight, tracking }`), not a bare
number like today — every current call site sets `fontSize` alone and lets weight/
line-height drift per screen (e.g. `statValue`'s job is done today at 22, 23, 24,
and 25px with `marginTop` 8–18 depending on file). An object forces the whole
typographic decision to move together.

### 3.2 Monospace / tabular numerals

Keep `fontVariant: ['tabular-nums']`, don't switch to a monospace font family. A
true monospace face (per `principles.md`'s "Numbers... belong in monospace")
would push Posted further from "trading terminal" and closer to "developer tool" —
tabular-nums on the system sans already gives columnar alignment without
introducing a second typeface, which also keeps the "one restrained typographic
voice" rule from `app.md` intact. Every `statValue`/`statValueLarge` usage and
every table/list numeric column must set `fontVariant: ['tabular-nums']` — today
only 6 of 9 screens with financial figures do (verified: `holdings.tsx`,
`index.tsx`, `insiders.tsx`, `money.tsx`, `news.tsx`, `subscriptions.tsx`,
`invest.tsx`, `transactions.tsx` mixed; `feed.tsx` inconsistently applies it).
Enforce via the `MetricTile`/`Stat` primitive (§4.2) owning this itself so no call
site can forget it.

### 3.3 Font family policy

System font stack only (`Platform.select` default), everywhere, including the
login hero. Per `app.md`: "save the interesting fonts for marketing" and Posted's
"who" (a financially-engaged individual who returns daily) means legibility and
zero load-time cost beat expression. No new font asset, no `expo-font` addition.

---

## 4. Spacing, sizing, radii, borders

### 4.1 Spacing — validate the scale, fix the enforcement gap

`xxs4/xs8/sm12/md16/lg24/xl32/xxl48` already matches `principles.md`'s own
recommended table almost exactly (4/8/12/16/24/32/48+) and is **not** the problem —
the problem is that it's applied almost nowhere. Keep the 7 steps unchanged. Add
exactly one explicit exception rather than a new step:

```ts
export const spacing = {
  xxs: 4, xs: 8, sm: 12, md: 16, lg: 24, xl: 32, xxl: 48,
  hairlineGap: StyleSheet.hairlineWidth, // NEW — see below
} as const;
```

`gap: 1` shows up deliberately in the metric-row grid (`index.tsx`, `money.tsx`,
`transactions.tsx`, `subscriptions.tsx`, `holdings.tsx` — the "1px hairline-gap
grid on a `hairline`-colored background" pattern `competitor-similarity-audit.md`
correctly identifies as a genuine positive: it reads as a bank-statement rule, not
a bento grid). That's not spacing drift, it's a *border simulated as a gap* — name
it as what it is (`spacing.hairlineGap`, backed by `StyleSheet.hairlineWidth` for
crisp rendering on retina displays rather than a flat `1`) and make it the internal
implementation of the `StatGrid` primitive (§4.3), not a value any screen sets by
hand. Every other stray value found (5, 6, 7, 9, 10, 11, 13, 14, 17, 18, 20, 22,
30…) has no such justification and should snap to the nearest of the 7 named
steps — there is no case in the audit where a value between two steps was doing
real work.

**Enforcement**, not a new value: once `Panel`/`StatTile`/`IconButton` (§4/§5) own
their own internal spacing, most stray literals disappear structurally, because
screens stop writing their own `padding`/`gap` for these shapes at all.

### 4.2 Sizing — new first-class token set (didn't exist before)

Control and icon sizing was never tokenized, which is exactly why touch targets
drifted: `ActionButton`/`assistantButton` at 38px height, `avatar` at 34px, icon
buttons at 38px (`index.tsx`, `money.tsx`) *and* 40px (`insiders.tsx`,
`stock/[symbol].tsx`) for the same control, `retryButton` at 36px — all below the
skill's mandated 44×44 floor.

```ts
export const size = {
  touchMin:  44,  // WCAG floor — every interactive control's HIT AREA, all 3 platforms
  controlSm: 32,  // visual chip/badge height where the tap target is padded via hitSlop
  controlMd: 44,  // standard button / icon-button / input height
  controlLg: 52,  // primary CTA height (login submit, "Connect Schwab")
  iconSm: 16,
  iconMd: 20,
  iconLg: 24,
  avatar: 36,     // visual diameter; hitSlop pads the tap target to touchMin
} as const;
```

**Resolving the density-vs-44px tension**: Posted's "Precision & Density" starting
point (per the product-design skill) argues for visually compact controls; WCAG
argues for 44px hit areas. RN resolves this natively — use a *visual* size from
`controlSm`/`iconMd`/`avatar` for how the control looks, and RN's `hitSlop` prop to
pad the invisible tap area out to `touchMin` without inflating the chrome. This is
already the correct pattern for a dense terminal UI and requires no visual design
compromise; it just wasn't used anywhere in the app yet (every current icon
button's tap area is exactly its visual box).

### 4.3 Radius — fix the one non-scale value, add the one missing step

```ts
export const radius = {
  sm: 4,     // unchanged — chips, small controls, ActionButton
  md: 8,     // was 7 — 7 isn't a multiple of anything and fails principles.md's
             // "explainable as N × base unit" rule; 8 is both a clean 2× of sm
             // and matches spacing's base unit
  lg: 12,    // unchanged — the standard Panel/Card radius (radius.lg today)
  xl: 16,    // NEW — hero/inverted panels specifically. subscriptions.tsx's
             // `mobileHero` already hardcodes 16 while insiders.tsx's `hero` and
             // money/invest's hero panels use radius.lg (12) for the visually
             // identical hero-panel role — verified inconsistency, this closes it
  pill: 999, // unchanged — reserved for true pills: avatar, status dot, LevelPill
             // dot. Not for buttons (ActionButton correctly already uses sm, not
             // pill — validate, keep) per app.md's anti-pattern list ("pill-shaped
             // controls everywhere")
} as const;
```

### 4.4 Borders

- `borderWidth: 1` for all panel/card/input outlines (unchanged, correct — RN's
  `hairlineWidth` is reserved for *dividers*, not outlines, since sub-pixel
  hairlines at a 12px radius corner anti-alias poorly).
- `StyleSheet.hairlineWidth` for row dividers and the metric-grid trick (§4.1)
  specifically.
- `color.borderHairline` default, `color.borderHairlineStrong` for emphasis
  (selected card, focus-adjacent state) — never a third border color at a call
  site.

---

## 5. Component variants & interaction states

### 5.1 `Panel` (new primitive — replaces the 9-file duplicate)

The single highest-value extraction in this proposal: the exact block quoted in
§0 is retyped verbatim in 9 files. One component, one place the shadow/radius/
border decision lives.

```
<Panel variant="default" | "inverted" tone="neutral" | "stale" | "demo">
```

States:
- **default** — `color.surface`, `color.borderHairline`, `radius.lg`,
  `elevation.raised`.
- **inverted** — `color.surfaceInverted`, no border (navy reads as a solid block,
  not an outlined card — matches the shipped hero panels), `radius.xl`,
  `elevation.raised`. Replaces `hero`/`mobileHero`/`quoteHero` (4 independent
  implementations per `frontend-audit.md` §4.4).
- **hoverable** (web only, when the whole panel is a `Pressable` navigating
  somewhere, e.g. a holdings row): `borderColor` steps to `color.borderHairlineStrong`.
  No second shadow layer — `principles.md`'s "choose one depth strategy" rule
  means hover must not introduce a shadow escalation on top of the committed
  single-shadow approach.
- **pressed**: `backgroundColor: color.surfaceSunken`, no shadow change.
- **disabled**: `opacity: 0.5`, `accessibilityState={{ disabled: true }}`,
  non-interactive.
- **stale** (`tone="stale"`): a 2px top rule in `color.stale`, no other structural
  change — see §2.5. Never applied to `inverted` panels simultaneously with
  `demo` (a data source is either sample or live; if live, it can be stale or
  fresh, but never both roles at once).
- **demo** (`tone="demo"`): a 2px top rule in `color.demo` + inline "DEMO" chip
  (reuses `LevelPill`'s pill shape). Replaces `DemoBanner`'s full-width variant
  when demo status is being shown *inside* a panel rather than as a page-level banner.

### 5.2 `StatTile` / `MetricTile` (new primitive — replaces the 7-file duplicate)

```
<StatTile
  label="NET CASH POSITION"
  value={...}
  caption="as of 2 minutes ago"
  tone="neutral" | "positive" | "negative"
  size="default" | "primary"
  masked={privateMode}
/>
```

- **tone**: `neutral` → `color.textPrimary`; `positive`/`negative` → paired with a
  `▲`/`▼` (or `TrendingUp`/`TrendingDown` from `lucide-react-native`, already the
  established icon set) glyph *and* the `+`/`-` sign already produced by the
  existing `signedMoney()` helper — never color alone, matching `LevelPill`'s
  already-correct pattern.
- **size**: `default` → `type.statValue` (22px); `primary` → `type.statValueLarge`
  (30px), exactly one per screen (the single most important number — net cash
  position, portfolio total).
- **masked** (private-mode state): replaces the numeral with a **fixed-width**
  mask, always `••••` (never `••`, `$••••••`, or any other length — 4 dots,
  currency prefix preserved only when the field is currency), so toggling private
  mode never reflows the layout. This is a single prop the component owns, not
  logic every screen reimplements — closes the 4-file duplicate `privateMode`
  ternary (`index.tsx`, `invest.tsx`, `money.tsx` ×2, `DebriefPanel.tsx`) with one
  canonical `formatMasked()` helper the component calls internally.

### 5.3 `IconButton` (new primitive — fixes the 38/40px touch-target violation)

Replaces `index.tsx`'s `privacyButton`, `money.tsx`'s `privacyButton`,
`invest.tsx`'s `iconButton`, `insiders.tsx`'s `headerIcon`, `stock/[symbol].tsx`'s
`headerIcon` — five independent style objects for one control, two different
sizes (38 vs 40) for no reason. Visual size `size.controlMd` (or `controlSm` with
`hitSlop` padding to `size.touchMin`), states: default / pressed
(`color.surfaceSunken` fill) / disabled (`opacity 0.5`) / active-toggled (for the
privacy eye icon: `color.accentSoft` fill while private mode is on).

### 5.4 Focus state — new, currently entirely absent

Every interactive control needs a visible focus-visible ring on web (currently
zero exist — every text input disables the outline and nothing replaces it).
Proposal: a shared `focusRing` style — `2px solid color.accent`, `2px` outline
offset — applied via `Pressable`'s/`TextInput`'s web-only `style` callback (RN Web
maps `outlineWidth/outlineColor/outlineStyle` to real CSS outline properties, so
this is a real fix, not a native-only gesture). Every primitive in this section
(`Panel` when `hoverable`, `IconButton`, `ActionButton`, filter chips, `TextInput`
usages in `MarketSearch`/`AssistantChat`/list search bars) must render it — this
is a correctness floor, not a variant to opt into.

### 5.5 `ConnectionRow` (new — consolidates settings.tsx's ~90% duplicate blocks)

Takes a normalized `demo: boolean`, `lastSyncedAt: string | null`, `status: 'live'
| 'stale' | 'demo' | 'error'` (derived per §2.5/§2.6, not stored). Replaces the
banking-connection panel and investing-connection panel in `settings.tsx` (lines
215-258 and 292-339 per `frontend-audit.md` — same row shape, same demo-badge-vs-
sync/unlink-button branch, differing only in which mutation it calls) and can
absorb `AppShell`'s sidebar `statusDot`/`marketStatus` so there is exactly one
place "is this connection live, stale, or demo" is decided and rendered.

### 5.6 Filter chip — unify the two existing divergent implementations

`feed.tsx`'s `filterActive` (navy fill) and `transactions.tsx`'s `filterActive`
(tealSoft fill + raw hex border) are the same interaction styled two ways. One
`FilterChip` primitive: inactive = `color.surface` + `color.borderHairline`;
active = `color.accentSoft` fill + `color.accentSoftBorder` border + `color.accent`
text (the `transactions.tsx` treatment, kept, since it reads as "selected filter"
rather than "structural navy block" — `navy` fill on a chip conflicts with `navy`
meaning "this is a summary/hero panel" elsewhere in the same design language).

---

## 6. Responsive behavior as first-class tokens

### 6.1 Verdict on current breakpoints

`breakpoints.mobileNav` (920) and `breakpoints.assistantDock` (1600) are both
correctly designed and correctly consumed (`AppShell.tsx`, `AssistantDrawer.tsx`)
— validate, keep both values unchanged. The actual problem is that **no other
screen references them**: 7+ screens each declare their own numeric cutoff
(900–1080 for "desktop," 680–720 for "compact"), producing dead zones where the
shell shows desktop chrome around a screen still rendering its mobile content
layout, or vice versa.

### 6.2 Proposed complete breakpoint set

```ts
export const breakpoints = {
  compact:      720,  // NEW — below this, stack to one column, hide secondary
                       // columns/metrics. Replaces the 680/700/720 spread found
                       // in transactions.tsx/money.tsx/subscriptions.tsx/insiders.tsx
  mobileNav:    920,  // unchanged — sidebar vs. bottom tab bar (AppShell)
  wide:         1280, // NEW — enables a 3rd column / extra density that isn't
                       // tied to the assistant docking decision
  assistantDock: 1600, // unchanged — assistant becomes a fixed right column
} as const;
```

`index.tsx`'s one-off `sideBySideSidebar` cutoff at 1680 is folded into
`assistantDock` (1600) rather than kept as a 5th number — the two decisions
("show a side-by-side layout" and "the assistant has room to dock") are the same
question (is there enough width for a third column), so they should be the same
breakpoint, not two numbers 80px apart that happen to both mean roughly "very
wide."

**Binding rule**: no screen may declare its own numeric width comparison. Every
screen consumes a shared hook instead of recomputing `useWindowDimensions().width
>= <ad hoc number>`:

```ts
// theme/useBreakpoint.ts — new, small, shared
function useBreakpoint() {
  const { width } = useWindowDimensions();
  return {
    width,
    compact: width < breakpoints.compact,
    desktop: width >= breakpoints.mobileNav,
    wide: width >= breakpoints.wide,
    assistantDocked: width >= breakpoints.assistantDock,
  };
}
```

This is a state-derivation rule, not just a constant — per
`frontend-ui-engineering`'s state-management guidance, cross-cutting UI state
read by many components belongs in one shared hook, not reimplemented per
consumer. This is exactly that case: 7 screens already reimplement the same
derivation with different numbers.

### 6.3 Preserve, don't flatten, genuinely different mobile layouts

The skill is explicit that Money/Portfolio's real mobile-specific layouts (not
just a reflowed desktop grid) must survive the redesign. `invest.tsx` is flagged
in `frontend-audit.md` §4.10 as the one primary screen with **no** responsive
split at all today — it reflows to one column rather than offering a genuinely
different mobile layout. This proposal's token layer doesn't fix that by itself
(it's a layout-design decision per screen), but flags it as the one screen that
needs a deliberate mobile-specific pass, not just a breakpoint-constant swap.

---

## 7. Motion

No motion system exists today (verified: no `react-native-reanimated` dependency,
zero `Animated` usage anywhere) — every current "transition" is an instant
`Pressable`-state style swap (e.g. `actionPressed: { backgroundColor:
colors.tealDark }`). This section is additive, not a fix to something
inconsistent.

```ts
export const motion = {
  duration: {
    instant: 0,     // reduced-motion fallback for everything below
    fast: 150,      // micro-interactions: press, hover-in/out, toggle flip
    base: 200,      // panel/tab transitions, assistant drawer open/close,
                     // menu open/close
  },
  easing: 'cubic-bezier(0.25, 1, 0.5, 1)', // per principles.md — smooth, no
                                             // spring/bounce anywhere; matches
                                             // app.md's "minimal spring physics...
                                             // bouncy feels unserious" for
                                             // application UI
} as const;
```

Rules:
- **150ms** for anything that responds to a single press/hover — button state,
  chip active/inactive, icon-button toggle.
- **200ms** for anything that changes what's on screen — the assistant drawer
  sliding open, a tab switching content, a menu appearing. This is also where
  `elevation.floating`/`elevation.overlay` (§2.4) should crossfade in, not pop.
- Every animated value must respect `prefers-reduced-motion` on web
  (`window.matchMedia('(prefers-reduced-motion: reduce)')`) and
  `AccessibilityInfo.isReduceMotionEnabled()` on native — when true, use
  `duration.instant` (skip straight to the end state), never disable the
  interaction itself.
- Motion is never decorative in the core app — every use above communicates a
  state change (open/closed, on/off, here/gone). `login.tsx` is the one
  exception the skill grants: a bolder, one-time hero entrance is acceptable
  there specifically because it's Posted's only first-impression surface, not
  because "the login page can have more animation" generally.
- Implementation: don't add `react-native-reanimated` yet. Every motion case
  above (opacity/translate fades, a drawer sliding in) is achievable with RN
  core's built-in `Animated` API at zero new dependency cost. Reconsider
  `reanimated` only if a specific redesigned screen needs gesture-driven or
  spring-physics interaction (e.g. a chart-scrub momentum fling) that `Animated`
  genuinely can't express well — don't adopt it preemptively.

---

## 8. Component-library policy

Explicit, per the product-design skill's platform-reality section — this is
Expo/React Native (`react-native-web` on web), not React DOM.

**From RN core / Expo, use directly:**
`View`, `Text`, `Pressable`, `ScrollView`, `TextInput`, `Switch` (already used in
`settings.tsx`), `ActivityIndicator`, `Image`, `Animated` (§7). `expo-router` for
navigation (already in place). `react-native-safe-area-context`'s `SafeAreaView`
(already in place, keep).

**Already-adopted, keep as the sole choice for their domain:**
- `lucide-react-native` — the established icon set app-wide. Consistent already
  (per `competitor-similarity-audit.md`: "not a giveaway on its own"); don't
  introduce a second icon library for any new component.
- `react-native-svg` — underlies the existing custom chart components
  (`PortfolioChart`, `StockPriceChart`, the insiders sentiment chart). No
  off-the-shelf charting library (Victory, react-native-chart-kit, etc.) — these
  charts are genuinely screen-specific visualizations per `frontend-audit.md` §5
  ("forcing a shared chart component would fight the skill's signature-element
  requirement") and should stay bespoke SVG, sharing only headless interaction
  hooks (`chartScrub`, `chartZoom`, etc.) already in `lib/`.

**Posted-specific primitives — extend `components/ui.tsx`, never a parallel file:**
`Panel` (§5.1), `StatTile` (§5.2), `IconButton` (§5.3), `ConnectionRow` (§5.5),
`FilterChip` (§5.6), plus the existing `SectionHeader`, `ActionButton`,
`DemoBanner`, `LoadingState`, `ErrorState`, `LevelPill` — all five validated as
already correct and kept unchanged. `TextLinkAction` (the arrow-chip pattern
currently inlined 3× in `index.tsx` and duplicated with variations in
`insiders.tsx`/`stock/[symbol].tsx`, despite `money.tsx` already having a correct
`TextAction` component to extend from) should also move here.

**Reference-only, never installed, never imported — reimplement the *idea* in RN
primitives:**
- `shadcn/ui`, `MUI Base UI`, `Origin UI`, `awesome-shadcn-ui` — React DOM +
  Radix/Tailwind, don't run on iOS/Android.
- `react-bits`, `Magic UI` — React DOM + Tailwind/Framer Motion component
  collections.
- `motiondivision/motion` (Framer Motion), `motion-primitives` — web-only motion
  libraries; RN's `Animated` (or `reanimated` if later justified, §7) is the
  cross-platform equivalent.
- No Tailwind/NativeWind anywhere in this codebase today (confirmed: not a
  dependency) — don't introduce one as a side effect of copying a shadcn
  reference; every component here is `StyleSheet.create`, matching the existing
  codebase convention.

**Confirmed: nothing in this proposal sources a component directly from a
React-DOM-only library.** Every new primitive in §5 is built from `View` /
`Pressable` / `Text` plus the token layer above.

---

## 9. The anti-duplication rule

Stated plainly, because the root cause across every finding in §0 is the same
pattern repeating: **a screen needs a visual shape that already exists on another
screen, and instead of importing it, re-authors it from raw `StyleSheet.create`
literals.** The fix is not "try to remember to reuse things" — it's removing the
ability to redefine these six shapes locally:

| Shape | Primitive that owns it | Currently duplicated in |
|---|---|---|
| Bordered/shadowed container | `Panel` (§5.1) | 9 files, byte-for-byte |
| Label/value/caption stat block | `StatTile` (§5.2) | 7 files, drifting sizes |
| Small square icon-only control | `IconButton` (§5.3) | 5 files, 2 different sizes |
| Dark hero summary block | `Panel variant="inverted"` (§5.1) | 4 files, independent radii/padding |
| Connection status + sync/unlink row | `ConnectionRow` (§5.5) | 2 near-identical blocks in `settings.tsx` alone |
| Filter/selection chip | `FilterChip` (§5.6) | 2 files, 2 different active-state treatments |

Going forward: **if a second screen needs a shape that already exists once, that
is the signal to extract it to `ui.tsx` before writing the second copy** — not
after a third or fourth copy accumulates, which is how the 9-file `Panel`
duplicate happened. `PortfolioChart`/`StockPriceChart`/the sentiment chart are the
explicit, reasoned exception (§8) — genuinely different visualizations of
different data, not the same shape twice.
