# Posted — Three Redesign Directions

This is a proposal document, not an implementation. Nothing in `apps/client` has
been touched. It lays out three materially different directions for Posted's
core screens — different information architecture, navigation model, layout
composition, content hierarchy, interaction model, density, typography,
spatial behavior, and motion language, not three palettes on one skeleton. No
winner is picked here; that's a separate decision.

Everything is grounded in what Posted's backend already computes and what a
single financially-engaged owner actually does with it daily — not in what a
generic fintech dashboard template looks like.

## Baseline: what's actually there today

Before proposing deltas, here's an honest read of the current app, since
"different" only means something relative to this:

| Screen | Current IA role | Current structure |
|---|---|---|
| `index.tsx` (Portfolio overview) | Desktop-only default route (`apps/client/src/app/index.tsx:29`, redirects to `/money` on native) | Time-of-day eyebrow greeting → 4-up metric strip (`index.tsx:109-162`) → 2-col chart+accounts (`164-205`) → 2-col holdings+impact feed (`207-234`) → right sidebar `DebriefPanel` |
| `money.tsx` (Money overview) | Native/mobile home | Desktop: 4-up metric strip (`money.tsx:107-129`) → 2-col activity+accounts → 2-col transactions+recurring. Mobile: dark hero card (`193-209`) → 2-up spend/income → 3-up quick actions (`228-244`) → stacked panels |
| `invest.tsx` | Secondary investing entry on mobile bottom nav | `MarketSearch` → insider-activity banner → dark hero (total value) → 2-up today/return → holdings panel → accounts panel |
| `settings.tsx` | Connections & prefs | Flat stack of bordered panels: account, banking connections, investing connections, SMS link, alert delivery, data/security |
| `AppShell.tsx` | Shell | Desktop: 224px navy sidebar with two nav **groups**, `MONEY` and `INVESTING` (`AppShell.tsx:181-184`) → topbar with an "Ask Posted" toggle button that opens a drawer (`AssistantDrawer.tsx`), which docks as a fixed column only ≥1600px (`breakpoints.assistantDock`, `tokens.ts:63`). Mobile: bottom tab bar, 4 items. |
| `theme/tokens.ts` | Design tokens | Cool-neutral canvas (`#EDF0F4`) + white surfaces, one teal accent (`#087E8B`), navy for chrome/hero cards, radius scale `4/7/12/999`, soft `cardShadow`, no font-family token (system default everywhere) |

This is already closer to "Precision & Density" / "Sophistication & Trust"
than to a consumer budgeting app — hairline rules, tabular nums, all-caps
9–10px micro-labels, teal used only for interactive/brand accents. It is
**not**, however, structurally different from a generic SaaS dashboard: a
metric-card row, a two-column panel grid, a sidebar split into feature
groups, and a chat drawer bolted onto the top bar is the same skeleton
Linear/Vercel/Stripe-style admin templates use. That skeleton, not the color
palette, is what the three directions below actually change.

## What stays fixed regardless of direction

Per the redesign's non-negotiable engineering floor, none of the three
directions below touch:

- Query keys, mutation contracts, sync behavior, or any `lib/api.ts` /
  backend call shape.
- The real breakpoint logic (`useWindowDimensions`, the `920`/`1600`
  thresholds, genuinely different mobile layouts for Money/Portfolio — not a
  reflowed single column).
- The accessibility floor: `accessibilityRole`/`accessibilityLabel` on every
  control, ≥44×44 touch targets (explicitly correcting today's 38×38 icon
  buttons in `AppShell`/`index.tsx`/`invest.tsx`), visible focus on web,
  loading/empty states that explain next action, `prefers-reduced-motion`
  respected.
- The 150ms-micro / 200ms-panel motion floor as a baseline — each direction
  is explicit below about the few places it deliberately exceeds that floor,
  and why that's a state-communication choice, not decoration.

---

## Direction A — "The Statement" (conservative production direction)

### Core concept

Posted already computes something no generic dashboard has: a
provider-backed, timestamped financial record (Schwab positions, Plaid
transactions, a `last_synced_at` per connection). Direction A takes that
literally and treats every screen as a **printed financial statement**
brought current — a brokerage confirm or a bank statement, not a "dashboard."
Metrics aren't cards floating in a grid; they're a statement header. Lists
aren't card grids; they're ledger lines with a right-aligned numeric column,
the way a real statement lines up dollars against a hairline rule. Nothing
about this requires new gesture systems or IA changes — it's the safest
direction here — but it stops the screen from reading as an admin-panel
template by refusing the metric-card + bordered-panel-grid pattern entirely.

### Visual references (translated for RN)

- **Rejected explicitly:** MagicUI's `border-beam` / `shine-border`
  (`magicuidesign-magicui/apps/www/registry/magicui/border-beam.tsx`-style
  animated gradient card edges) — this is exactly the decorative-glow
  anti-pattern the redesign forbids; a statement doesn't need light chasing
  its border to feel trustworthy. Rejected. MagicUI's `dock` (hover
  magnification) is also rejected — it's a hover-only affordance with no
  honest touch equivalent, and a bottom tab bar that "bounces" reads as
  playful, not as a ledger. Rejected. Bento-style card grids for
  metrics/holdings (the current `styles.metrics` 4-up + `styles.panel`
  grid) — rejected as the thing being replaced.
- **Kept and reinterpreted:** origin-ui's `table.tsx`
  (`shadcn-originui/registry/default/ui/table.tsx`) — not the DOM `<table>`,
  but its *idea*: consistent column alignment, a header row that stays
  legible under scroll, numeric columns right-aligned and monospaced. In RN
  this becomes a `FlatList`/`View` row component with fixed-width numeric
  columns and `fontVariant: ['tabular-nums']`, not a literal HTML table.
  motion-primitives' `SlidingNumber`
  (`ibelick-motion-primitives/components/core/sliding-number.tsx`) supplies
  the *mechanism*, not the code, for the one motion moment this direction
  allows itself: a per-digit odometer column (each digit is a fixed-width
  overflow-hidden view; the digit rolls through 0–9 on a spring) — reimplemented
  with `react-native-reanimated`'s `useAnimatedStyle` + `withSpring`
  (stiffness ≈ 280, damping ≈ 18, matching the reference's own constants),
  triggered only when a sync completes and a real value changes.

### Layout principles

Full-bleed, flush ledger — no card shadows, no per-panel elevation
(`cardShadow` retired for this direction). One continuous ruled surface per
screen, sections separated by a labeled hairline rule (a small-caps section
label sitting directly on the rule, like a statement section header),
not by whitespace or boxes. A single "statement header" band at the top of
every screen carries the identity + as-of timestamp that the current design
scatters (greeting eyebrow, "last synced" caption, sync button) into one
place — that band is the one thing that's always present, everything below
it is ledger lines.

### Typography

Two faces, one superfamily, for a concrete reason (columns must align):
**IBM Plex Sans** for labels, prose, and captions; **IBM Plex Mono** for
every number, everywhere — dollar figures, percents, dates, account
counts. Statements are typeset in fixed-width numerals for exactly this
reason (so a column of dollar amounts lines up visually); this reinterprets
that convention instead of decorating with a display face. Both ship via
`expo-font` + `@expo-google-fonts/ibm-plex-sans` and
`@expo-google-fonts/ibm-plex-mono`, loaded once in the root layout — works
identically on iOS/Android/web. Scale stays close to today's (10/12/14/20/28)
but the primary portfolio/cash figure grows to 34–36px in Plex Mono, letting
the monospace numerals themselves be the "hero," not a bigger generic sans.

### Geometry

Radius collapses to functionally zero: a new `radius.flat = 0` (or 2px,
enough to stop web anti-aliasing artifacts) replaces `radius.lg` for every
panel. `radius.pill` is dropped for status — the `LevelPill`/demo badge
pattern becomes bracketed monospace text (`[URGENT]`, `[DEMO]`,
`[STALE 6H]`) rather than a colored rounded chip, which is both more
"statement," and sidesteps the "pill-shaped controls everywhere"
anti-pattern outright rather than trying to use pills tastefully. Hairlines
(`colors.line`/`lineStrong`) do all the separation work that `cardShadow`
does today. Density goes up slightly over today's row heights (72–84px rows
tighten to 56–64px) since the instrument here is a professional trader/owner
scanning a record, not a consumer touching cards.

### Navigation model

Kept conservative on purpose: same desktop sidebar / mobile bottom-tab split
as today, same `MONEY`/`INVESTING` grouping (this direction doesn't propose
an IA change — see Direction B for that). What changes is the sidebar's own
visual register: the navy icon-pill nav items become a plain text index —
small-caps labels in a single column, a 2px vertical rule (not a filled
pill background) marking the active item, closer to a table of contents in
a printed report than to app chrome. The "Ask Posted" control moves from a
teal pill button in the topbar to a bracketed text link (`[ Ask Posted ]`)
that opens the same drawer — same behavior, statement-consistent skin.

### Interaction patterns

Rows expand in place (tap a holding row → inline detail slides open below
it, `LayoutAnimation`, 180ms height+opacity) rather than navigating to a new
screen for a quick check — but "All holdings" / "All transactions" still
navigate to the dedicated list screens for the full record, unchanged from
today. Private mode (`Eye`/`EyeOff`) gets a real `accessibilityState:
{ selected }` it's missing today, and masked digits render as monospace
bullets (`••••••`) that keep the same column width as real numerals, so
masking a statement doesn't reflow the ledger.

### Motion language

- Digit-column settle on real value change only (sync completes, a number
  changes): spring, stiffness 280 / damping 18 / mass 0.3 — same constants
  as the `SlidingNumber` reference — roughly 300–400ms to rest. This is a
  state-change signal (the record updated), not a mount animation; numbers
  never animate on first paint.
- Row expand/collapse: 180ms height+opacity, within the 200ms panel floor.
- Page-to-page: no transition. A statement doesn't animate when you turn to
  a new page in the same book — instant swap, consistent with "the design
  should disappear."
- Everything respects `prefers-reduced-motion` by skipping straight to the
  end state.

### Strengths

Cheapest to build of the three (mostly typography, spacing, and shadow/radius
token changes — no new gesture systems, no IA/routing change, no new backend
shape needed). Meets the accessibility floor almost automatically because
everything is row-based. Genuinely differentiates from a stock admin
dashboard while staying obviously "safe to ship" — a reviewer who wants zero
risk can pick this without arguing about interaction novelty.

### Risks

The zero-shadow / zero-radius / monochrome-plus-mono-numerals combination can
tip into looking unfinished or "just a spreadsheet" if the type scale and
rule weight aren't held with confidence — the statement-header band and the
bracketed status tags are load-bearing for signaling "considered," not
"default browser table." Because it's the least visually loud of the three,
it's also the easiest to under-execute and end up boring; the self-review
squint test (does the primary figure still read as unmistakably primary)
matters more here than in the other two.

### Example treatment — Portfolio overview (desktop)

```
POSTED · STATEMENT                                    AS OF TODAY · 9:41 AM
Good morning, Akshat                        [ Hide balances ]   [ Sync now ]
────────────────────────────────────────────────────────────────────────────
TOTAL PORTFOLIO VALUE                                          $142,830.44
across 3 Schwab accounts
  TODAY                                          +$412.18        +0.29%
  TOTAL RETURN                                 +$18,442.02       +14.8% all time
  ATTENTION                                             2  unread material updates
────────────────────────────────────────────────────────────────────────────
PORTFOLIO PERFORMANCE · 30D                    │ ACCOUNTS
                                                │ Schwab Individual   $88,204.11
   [ledger-line chart — one hairline stroke,    │                        +$210.40
    no fill, no card border, gridlines at       │ Schwab Roth IRA     $54,626.33
    the same hairline weight as everything      │                        +$201.78
    else on the page]                           │ ──────────────────────────────
                                                 │ Last synced 4m ago         ●
────────────────────────────────────────────────────────────────────────────
LARGEST HOLDINGS                                │ IMPACT FEED
AAPL    184 sh   $32,904.00        +2.1%        │ [URGENT]  AAPL earnings beat
MSFT     64 sh   $27,140.16        +0.4%        │ [NOTABLE] Fed holds rates
GOOGL    40 sh   $19,880.00        -0.6%        │ [NOTABLE] MSFT cloud guidance
                                     All →       │                       Feed →
────────────────────────────────────────────────────────────────────────────
```

The sidebar `DebriefPanel` is not a separate boxed column here — it's the
last band of the same statement, same rule weight, same type scale, just
below the fold or, ≥1680px, still to the right but flush (no border, no
shadow) so it reads as an appendix to the statement, not a different widget.

### Example treatment — Money overview (desktop)

```
POSTED · STATEMENT                                    AS OF TODAY · 9:41 AM
Cash flow and everyday finances               [ Hide balances ]  [ Manage → ]
────────────────────────────────────────────────────────────────────────────
NET CASH POSITION                                                 $8,240.11
$9,540.11 cash less $1,300.00 card balances
  SPENT THIS WEEK                                    $612.40
  vs $2,400.00 income received
  CARD BALANCES                                    $1,300.00   across 2 cards
  RECURRING MONTHLY                                  $340.00   $4,080/yr
────────────────────────────────────────────────────────────────────────────
WEEKLY ACTIVITY                                 │ CONNECTED ACCOUNTS
Mo ▂  Tu ▄  We ▇  Th ▃  Fr ▅  Sa ▁  Su ▂         │ Chase Checking      $6,204.30
   groceries    $210   ████████░░░░              │ Chase Sapphire     -$1,300.00
   dining       $140   █████░░░░░░░              │ ─────────────────────────────
   transport     $88   ███░░░░░░░░░              │ Updated 12m ago            ●
────────────────────────────────────────────────────────────────────────────
RECENT TRANSACTIONS                             │ RECURRING CHARGES
Whole Foods            -$84.20    Tue           │ Spotify        $11.99   in 3d
Shell #4021             -$41.02   Tue           │ Rent        $1,200.00   in 9d
Amazon                   -$29.99  Mon           │
                              All transactions → │                   Review →
────────────────────────────────────────────────────────────────────────────
```

On mobile, the dark navy hero card (`money.tsx:193-209`) is replaced by the
same statement-header band used on desktop — no separate "hero" treatment,
because a statement doesn't get a different cover page on your phone.

### Extending to Investing / Settings / the shell

`invest.tsx`'s dark hero card and `settings.tsx`'s bordered-panel stack both
fold into the same flush-ledger treatment — Settings in particular reads
*better* this way, since "connections" are already inherently a record
(provider, account count, last synced), not feature cards. `AppShell`'s
sidebar keeps its two groups but loses the navy pill-nav chrome for the
text-index treatment described above.

---

## Direction B — "The Position Spine" (product-native direction)

### Core concept

The current IA splits the app into two verticals — `MONEY` and `INVESTING`
— because that's how a multi-tenant fintech SaaS would organize *features*.
But Posted is one person's net worth: cash and portfolio aren't two
products, they're two currents feeding one number, and the thing that
actually differentiates Posted from any other finance app is what happens
underneath both of them — a Schwab OAuth connection, a Plaid checking
connection, a Plaid Investments connection, and (per
`project_signalwire_signing_key.md`-adjacent territory) an SMS link, each
syncing on its own schedule, each capable of going stale independently. This
direction makes that plumbing the primary structure instead of hiding it
behind a caption. The overview becomes a single vertical **spine** of
full-width instrument bands — Position, Movement, Sync, Attention, Ledger —
each grounded in a real domain concept (net cash position, day change,
sync freshness, unread impact events + upcoming recurring charges treated as
one "needs a decision" list) instead of an arbitrary card grid.

This is the direction with the most IA change: **Money and Investing stop
being separate top-level destinations** and become filtered lenses
(`Everything / Cash / Investments`) over one net-worth spine.

### Visual references (translated for RN)

- **Signature mechanism — the sync spine:** inspired by a trading terminal's
  "last trade" tape and an ECG strip, not by any of the reference repos
  directly — this is the one component that has no generic-SaaS equivalent,
  because no generic SaaS product syncs from four independently-stale
  providers. Rendered as a horizontal strip of tick marks, one per
  connection (Schwab, Plaid checking, Plaid investments, SMS link), each
  positioned/colored by recency rather than described in a caption.
- **Kept and reinterpreted:** MUI Base UI's `Meter` primitive
  (`mui-base-ui/packages/react/src/meter`) — Base UI models "a scalar value
  within a known range, exposed with an ARIA `meter` role" as a first-class
  unstyled primitive. That's exactly what a freshness tick *is*
  (time-since-sync within a known staleness range) — the RN reinterpretation
  is a `Pressable` with `accessibilityRole="adjustable"` and
  `accessibilityValue={{ min, max, now }}`, not a literal DOM meter. Base
  UI's `Tabs` (`packages/react/src/tabs`) supplies the *keyboard/roving-focus
  model* — not the component — for the `Everything/Cash/Investments` lens
  selector: one `accessibilityRole="tablist"` container, each lens
  `accessibilityRole="tab"` with `accessibilityState.selected`, arrow-key
  roving focus on web. Base UI's `Toolbar` informs grouping the header's
  privacy toggle + sync action as one labeled control group instead of two
  loose icon buttons.
- **Rejected explicitly:** MagicUI's `animated-circular-progress-bar` used
  as literal decoration (a generic "% complete" ring) — rejected; if a ring
  ever represents sync freshness it must be one of the *tick marks* on the
  spine, not a separate decorative gauge bolted onto a card. A
  bento/kanban-style "modules as cards you drag around" layout — rejected;
  the spine's band order is fixed and meaningful (position → what changed →
  can I trust these numbers → what needs a decision), not user-rearrangeable
  widgets, because the order itself encodes priority.

### Layout principles

Single column, full-width bands (no two/three-column card grid at all on
desktop or mobile — this is one of the two places density comes from
*ordering*, not from packing more columns side by side). Each band has a
narrow left legend rail (a fixed-width label column, like a spec sheet or
an instrument panel's gauge labels) and content filling the rest of the
width — so "NET POSITION" sits to the left of the number the same way on
a 1440px desktop and a 390px phone; only the content area's internal layout
(stacked vs. side-by-side sub-values) changes at the breakpoint, not the
band structure itself.

### Typography

**Space Mono** for every measured figure (dollars, percents, tick timestamps)
— deliberately more "terminal readout" than Direction A's statement-print
Plex Mono, because this direction's whole metaphor is an instrument panel,
not a printed record. **Manrope** for the narrated causal notes this
direction introduces (see Movement band below) and for all labels/prose —
a humanist grotesk chosen specifically to contrast with the mechanical
monospace, so "measured fact" vs. "assistant-narrated context" are
typographically distinct at a glance without needing a color or icon to say
so. Both via `@expo-google-fonts/space-mono` and `@expo-google-fonts/manrope`.

### Geometry

Rectilinear, low-radius (2–4px, a new `radius.instrument` token) bands
separated by full-bleed hairlines — no card boundaries at all for the bands
themselves. The sync-spine ticks are the one place a small circular/diamond
mark is meaningful geometry (a data mark, not decoration): 8px marks,
color communicating freshness — teal (fresh, <15 min), amber
(`colors.warning`, aging, 15 min–4 hr), red (`colors.negative`, stale, >4 hr)
— reusing existing semantic tokens rather than inventing new ones.

### Navigation model

Sidebar collapses from two feature-groups into: the spine itself (the
default view, always "Everything"), three inline lens chips at the top of
the spine (`Everything / Cash / Investments` — filters the Movement,
Attention, and Ledger bands in place, no navigation, no route change),
and a secondary **Explore** rail (a slide-out reached from one compact icon)
that holds the encyclopedic destinations used less often — Transactions,
Subscriptions, Holdings, Insiders, Impact Feed, News, Settings. The
day-to-day loop (position, what changed, can I trust it, what needs a
decision) never requires opening Explore.

### Interaction patterns

- **Sync spine ticks are tappable.** Tapping a tick expands an inline
  detail directly below the spine: what that connection's last sync
  actually changed ("+3 new transactions," "2 holdings repriced,
  AAPL +2.1%," "no change"). This is the thing that most concretely answers
  "can I trust the number above" — which today is a single muted caption
  (`index.tsx:198-203`) three levels down the page.
- **Movement band carries a causal note, not just a delta.** Instead of a
  bare `+$412.18 (+0.29%)`, the line reads `+$412.18 today — mostly AAPL
  after yesterday's earnings beat, partly offset by a $38 Spotify renewal`,
  generated from the same `important_events`/`recent_transactions` data the
  backend already returns, just surfaced at the top instead of buried in a
  feed three bands down.
- **Attention band merges impact events and upcoming recurring charges**
  into one ranked "needs a decision" list — from the owner's point of view,
  an unread material portfolio event and a subscription renewing in 3 days
  are the same kind of thing (something that will move their money that
  they haven't acknowledged), so they're one list, not two panels in two
  different verticals.
- **The assistant is docked, not toggled**, on any width where there's room
  (reusing the existing `breakpoints.assistantDock` threshold, but the
  *default* interaction is that it's part of the spine's right margin, not
  a button that opens a drawer), and its suggested quick-questions change
  per band in view (reusing the `assistantSection`/`assistantContext`
  plumbing that already exists in `AppShell.tsx`/`assistantSection.ts` —
  today that context is used only to seed the chat; here it also drives
  which quick-prompt chips are visible, e.g. "why is my cash down" appears
  only while the Position/Movement bands are in view).

### Motion language

- Sync-in-progress tick: a slow breathing opacity loop (1.6s, ease-in-out,
  0.55↔1.0) on the *actively syncing* connection's tick only — stops the
  instant that sync resolves. This exceeds the "no ambient animation"
  instinct deliberately: it is the literal visual meaning of "syncing right
  now," not decoration, and nothing else on the page loops.
  - Value change settle: same digit-column spring as Direction A (stiffness
  280 / damping 18 / mass 0.3), 300–450ms, fired whenever a sync completes
  and a Position/Movement number actually changes.
- Band-to-detail expand (tapping a tick or an Attention item): 200ms
  height+opacity, at the panel-transition floor.
- Lens switch (`Everything → Cash`): 150ms crossfade on the bands that
  filter out/in — at the micro-interaction floor, communicating "this data
  set changed," not a decorative wipe.

### Strengths

The most defensible direction against "another finance company could ship
this unchanged" — the sync spine and the causal Movement line are both
literally impossible without Posted's specific multi-provider sync
architecture. Makes the assistant load-bearing instead of an accessory.
Directly serves three of the four domain workflows named in the brief
(sync-freshness, net cash position, portfolio moves) as the primary
structure rather than as buried details.

### Risks

This is the only direction with a real **IA/routing change** (merging Money
and Investing into lensed views of one screen) — meaningfully more
engineering lift than Direction A, and it changes muscle memory for
someone who's used the two-vertical nav since the app's start. A long
single-column spine risks becoming a lot of vertical scrolling before
reaching the Ledger band on a smaller phone if bands aren't collapsible;
mitigate by making Sync and Attention collapse to a one-line summary by
default with a tap to expand, so "just check my number" still resolves in
one glance at the top of the spine. The causal Movement note requires
generating a short natural-language sentence from transaction/event data
reliably enough to trust at a glance — a real product risk, not just a
visual one, if the sentence is ever wrong or misleading; needs a confidence
threshold below which it falls back to the plain delta.

### Example treatment — Portfolio overview → folded into "Position" (lens: Investments)

```
Ask Posted ▸ context: Investments lens                          [≡ Explore]
─────────────────────────────────────────────────────────────────────────
  Everything   [ Cash ]   ( Investments )              [ Hide ]  [ Sync ]
─────────────────────────────────────────────────────────────────────────
POSITION        $142,830.44 invested · $8,240.11 cash → $151,070.55 total
                [██████████████████████░░░░]  95% invested / 5% cash
─────────────────────────────────────────────────────────────────────────
MOVEMENT        +$412.18 today (+0.29%) — mostly AAPL after yesterday's
                earnings beat, partly offset by a $38 Spotify renewal
                +$18,442.02 all time (+14.8%)
─────────────────────────────────────────────────────────────────────────
SYNC            Schwab ●fresh 4m   Plaid-Chk ●fresh 12m   Plaid-Inv ●fresh 4m
                ⌄ tap a mark: "Schwab · +2 holdings repriced, no new txns"
─────────────────────────────────────────────────────────────────────────
ATTENTION (3)   ! AAPL earnings beat estimates — unread            2h ago
                ! Fed holds rates steady — unread                  6h ago
                ~ Spotify renews in 3 days — $11.99
─────────────────────────────────────────────────────────────────────────
LEDGER          AAPL   184 sh   $32,904.00   +2.1%
                MSFT    64 sh   $27,140.16   +0.4%
                GOOGL   40 sh   $19,880.00   -0.6%
                                                            All holdings →
─────────────────────────────────────────────────────────────────────────
```

### Example treatment — Money overview → folded into "Position" (lens: Cash)

```
Ask Posted ▸ context: Cash lens                                 [≡ Explore]
─────────────────────────────────────────────────────────────────────────
  Everything   ( Cash )   [ Investments ]               [ Hide ]  [ Sync ]
─────────────────────────────────────────────────────────────────────────
POSITION        $8,240.11 net cash — $9,540.11 cash less $1,300.00 cards
─────────────────────────────────────────────────────────────────────────
MOVEMENT        $612.40 spent this week vs $2,400.00 income — groceries
                and dining are 58% of the week's spending
─────────────────────────────────────────────────────────────────────────
SYNC            Chase-Checking ●fresh 12m   Chase-Sapphire ●fresh 12m
                ⌄ tap a mark: "Chase Checking · +6 new transactions"
─────────────────────────────────────────────────────────────────────────
ATTENTION (2)   ~ Spotify renews in 3 days — $11.99
                ~ Rent due in 9 days — $1,200.00
─────────────────────────────────────────────────────────────────────────
LEDGER          Whole Foods           -$84.20     Tue
                Shell #4021           -$41.02     Tue
                Amazon                -$29.99     Mon
                                                       All transactions →
─────────────────────────────────────────────────────────────────────────
```

Note both lenses are the *same screen* — only Position/Movement/Sync/
Ledger content swaps; the band order and the Attention band (which is
domain-agnostic on purpose) do not.

### Extending to Investing / Settings / the shell

`invest.tsx` and `money.tsx` as standalone routes go away as primary
destinations (redirect to `/` with the matching lens preselected, kept as
routes only for deep links/back-compat). `settings.tsx`'s connection
panels map directly onto the Sync band's expanded detail — "manage this
connection" becomes the same inline expansion the sync tick already offers,
with Settings as the exhaustive version. `AppShell`'s two nav groups become
the lens chips + the Explore rail described above.

---

## Direction C — "The Entry Stream" (experimental direction)

### Core concept

The real interaction-model risk: stop treating "overview" as a dashboard at
all. Posted's backend already generates a `morning_debrief` — a narrative
summary — but today it's demoted to italic-fallback text inside a sidebar
card (`DebriefPanel.tsx:33-40`). This direction promotes that narrative to
the entire top-level architecture: the overview is a **reverse-chronological
stream of dated entries** — today's entry, then yesterday's, then the day
before — each a short piece of generated prose with the real numbers set
inline and typographically distinct, not pulled out into separate metric
cards. "Your portfolio is up **+$412** today, mostly from **AAPL** (+2.1%)
after yesterday's earnings beat. Cash sits at **$8,240** after this
morning's **$1,200** rent payment posted." Any bolded noun or number in the
sentence is tappable and blooms open in place — this is an inline-expansion
interaction model, not drill-down navigation to a new screen. Navigation and
the assistant merge into one control: a single persistent input at the top
("Ask or jump to…") that is simultaneously a command-palette-style jump-to
and the existing context-aware assistant's entry point.

### Visual references (translated for RN)

- **Kept and reinterpreted:** origin-ui's `command.tsx`
  (`shadcn-originui/registry/default/ui/command.tsx`, a cmdk-style
  fuzzy-filter combobox) and MUI Base UI's `Combobox`/`Autocomplete`
  primitives — not as a ⌘K modal (touch has no keyboard-shortcut affordance
  to summon one), but as the *filtering/keyboard-navigation model*: a single
  always-visible `TextInput` at the top of the stream whose typed text
  simultaneously fuzzy-matches navigation destinations (shown as a filtered
  list below, `accessibilityRole="option"` rows) and, if not a nav match, is
  forwarded to the assistant as a question — reusing the exact
  `assistantContext`/`screenContext` plumbing `AssistantDrawer.tsx` already
  has, just moved from a toggled drawer to the permanent top control.
- **Kept and reinterpreted:** the *digit-column* mechanism from
  motion-primitives' `SlidingNumber` again, here for the inline numbers
  within prose (so `$8,240` settles the same way a statement number would
  when today's entry is still live/updating), and motion-primitives'
  `text-effect` variants (`app/docs/text-effect`) — not for glitch/typewriter
  gimmicks, but restrained to a single crossfade of the input's placeholder
  hint cycling through example prompts every 4s ("Ask or jump to… try 'why
  is my cash down'").
- **Rejected explicitly:** react-bits' `GlitchText` / `LetterGlitch`
  (`DavidHDev-react-bits/src/ts-default/TextAnimations/GlitchText`,
  `Backgrounds/LetterGlitch`) — tempting for a "terminal" feel but wrong
  register entirely for a financial record; a ledger diary doesn't glitch.
  Rejected outright, named here explicitly as a rejected default. MagicUI's
  `marquee` used as a literal auto-scrolling ticker — rejected as a primary
  pattern (auto-scrolling content the user can't pause is an accessibility
  anti-pattern and reads as a marketing ticker, not a financial record);
  if a tape-style scan ever appears it must be user-driven (swipe/scroll),
  never autoplaying. A centered-hero "Good morning" greeting card with
  stat chips underneath (i.e., today's `index.tsx` greeting eyebrow pattern
  scaled up) — rejected, since that's the generic "hero + cards" template
  this whole redesign is meant to avoid.

### Layout principles

No card grid anywhere in the primary stream. A single line-length-
constrained prose column (~640px max width on desktop, full width with
generous margins on mobile) with hairline **date rules** between entries —
like a diary's dated headers, not a card boundary. Above the stream, a
single pinned line (not a hero card) holding just the net worth figure and
today's signed delta — this is the explicit mitigation for the "numbers
first" domain hypothesis: even though the primary surface is narrative, the
one number the owner checks reflexively is always visible without scrolling
or reading a sentence.

### Typography

**Newsreader** (a Google Font built specifically for long-form reading) for
all entry prose — the only one of the three directions using a genuine
serif, chosen because this is the only direction where reading, not
scanning, is the primary act. **Fragment Mono** for every number embedded in
that prose, so figures interrupt the serif the way a ticker interrupts
print — a deliberate, restrained pairing (one characterful face used
consistently, not decoratively) rather than the generic AI-design-default
warm-serif-plus-terracotta combination; no terracotta or cream-paper
backdrop here, palette stays Posted's existing cool neutrals. Pinned
net-worth line uses the same Fragment Mono as the inline numbers, at 28px,
so it visually agrees with the numbers below it rather than introducing a
fourth type role.

### Geometry

Zero radius, zero borders for the prose column itself — text blocks, not
boxes. The **only** rounded geometry in this direction is the inline
tappable data chip (a number or a named entity within a sentence gets a
subtle 8px rounded-rect background on tap-affordance, `radius: 8`,
distinctly smaller than the existing `radius.pill: 999`) — used
specifically and only to mark "this is interactive," which is a meaningful,
sparing use of roundedness rather than the "pill-shaped controls
everywhere" anti-pattern.

### Navigation model

The sidebar and bottom tab bar are gone from the primary flow. Navigation
*is* the omnibox: typing "holdings," "settings," or "subscriptions" jumps
there; asking "why is my cash down" gets answered without leaving the
stream (an inline assistant reply appended as the next "entry" in the same
stream, visually distinguished only by a small assistant glyph in its date
rule — the assistant's answers literally become part of the diary rather
than living in a separate drawer). A minimal fixed icon row (3 icons:
Explore, Notifications, Settings) remains for pure discoverability/backup
on both desktop and mobile, since an omnibox-only nav with zero visible
destinations is real enough of a risk to hedge explicitly.

### Interaction patterns

- **Inline bloom**, not drill-down: tapping `AAPL` inside a sentence expands
  a small holding card *directly below that word*, in place, with the
  sentence's surrounding lines making room (reanimated layout transition,
  spring mass ≈0.4/damping ≈20) rather than navigating away from the entry
  you were reading.
- **Reverse chronology as the browsing model**: scrolling up moves
  backward through past debrief entries (each already generated by the
  backend daily) — checking your finances becomes "catching up on the
  ledger's own log," not "always looking at now." Older entries recede to
  ~0.9 opacity as a light depth cue, capped and skipped under reduced
  motion.
- **Omnibox does double duty**: no nav match → forwarded verbatim to the
  assistant with the current entry's context attached, exactly the same
  `screenContext` string pattern `AppShell.tsx` builds today, just sourced
  from "which entry is in view" instead of "which route."

### Motion language

- Inline bloom expand: 260–320ms spring (mass 0.4, damping 20) — intentionally
  a little slower than the 200ms panel floor because it's this direction's
  one deliberately "signature" motion moment (an entity opening inside
  running prose is unusual enough to need a beat to read as an expansion,
  not a jump-cut); still well short of anything "bouncy."
- Inline number settle (digit-column spring, same 280/18/0.3 constants):
  fires only while today's entry is the live one and a sync updates a
  number already on screen.
- Placeholder-hint crossfade in the omnibox: 4s interval, 200ms crossfade,
  pauses entirely under reduced motion (no cycling text at all — shows one
  static hint).
- Date-rule opacity recession going back in time: no animation on scroll
  itself, just a static opacity function of distance from "today" — nothing
  moves continuously.

### Strengths

The most memorable and hardest-to-copy of the three — no generic dashboard
template has an inline-expanding, reverse-chronological, omnibox-navigated
financial diary. Makes the existing (currently underused) `morning_debrief`
generation the star instead of a sidebar afterthought. Genuinely merges
"navigate" and "ask the assistant" into one honest control instead of two
separate affordances competing for the same header real estate.

### Risks

This is the one direction that puts real tension on the domain hypothesis
itself: prose-first optimizes for narrative comprehension, not the
twice-a-day reflexive glance the brief names as a core workflow — the
pinned net-worth line is the explicit mitigation, but it's a deliberate
trade-off being stated, not hidden. Larger engineering lift than either
other direction: needs reliable entity-tagging inside generated prose
(mapping "AAPL" or "$1,200 rent payment" back to a real holding/transaction
record to expand, not just decorative bold text), a new omnibox component
doing double duty as nav-search and assistant-entry, and materially more
accessibility care (inline tappable spans inside a paragraph need correct
focus order and roles — closer to accessible rich-text editing than to a
list of distinct rows). Highest chance of reading as gimmicky if the bloom
motion or the entity-tapping ever fires on the wrong word or feels
unreliable — trust in a finance app is the one thing that can't wobble.

### Example treatment — Portfolio overview (as today's entry)

```
┌ Ask or jump to… (try "why is my cash down")                              ┐
└────────────────────────────────────────────────────────────────────────┘
  $151,070.55 total   +$412.18 today                          [Explore ▸]

  ── TODAY · JUL 27 ──────────────────────────────────────────────────────

  Your portfolio is up ⟪+$412.18⟫ today (+0.29%), mostly from ⟪AAPL⟫
  (+2.1%) after yesterday's earnings beat, partly offset by ⟪MSFT⟫'s flat
  session. Total return since you opened your Schwab accounts stands at
  ⟪+$18,442.02⟫ (+14.8%). Two portfolio updates are still unread: the
  ⟪AAPL⟫ earnings beat and the Fed holding rates steady.

  All three sync sources are fresh as of the last few minutes.

  ── YESTERDAY · JUL 26 ──────────────────────────────────────────────────

  Portfolio closed roughly flat, -$38.40 (-0.03%)…                 (recedes,
                                                                    ~90% opacity)
```

`⟪AAPL⟫`/`⟪+$412.18⟫` denote the inline tappable chips (Fragment Mono, 8px
rounded background); tapping `⟪AAPL⟫` blooms open a compact holding card
(shares, cost basis, day change, mini chart) directly beneath that line
without leaving the entry.

### Example treatment — Money overview (as today's entry, Cash context)

```
┌ Ask or jump to…                                                          ┐
└────────────────────────────────────────────────────────────────────────┘
  $8,240.11 net cash   $612.40 spent this week                [Explore ▸]

  ── TODAY · JUL 27 ──────────────────────────────────────────────────────

  Net cash sits at ⟪$8,240.11⟫ — ⟪$9,540.11⟫ in checking against
  ⟪$1,300.00⟫ on cards. This week you've spent ⟪$612.40⟫ against
  ⟪$2,400.00⟫ received, with groceries and dining making up more than half
  of it. ⟪Spotify⟫ renews in 3 days for ⟪$11.99⟫, and rent (⟪$1,200.00⟫)
  is due in 9.

  Chase Checking and Chase Sapphire both synced 12 minutes ago.

  ── YESTERDAY · JUL 26 ──────────────────────────────────────────────────
  …
```

Tapping `⟪Spotify⟫` blooms the recurring-charge detail (amount history,
next expected date, cancel/review link) in place; tapping `⟪$612.40⟫`
blooms the weekly spending-by-category breakdown that today lives in
`CategoryBars`.

### Extending to Investing / Settings / the shell

`invest.tsx`/`money.tsx` as separate routes disappear entirely as primary
surfaces — there is one stream, and "Investments" or "Cash" become
omnibox jump targets or filters on the stream ("Ask or jump to… investing
only"), not routes. `settings.tsx` and the exhaustive list screens
(Transactions, Subscriptions, Holdings) survive unchanged in structure and
become the destinations the omnibox jumps to and the Explore icon opens —
this direction doesn't ask them to become narrative too, only the daily
overview.

---

## Side-by-side comparison

| | A — The Statement | B — The Position Spine | C — The Entry Stream |
|---|---|---|---|
| **Information architecture** | Unchanged (Money / Investing stay separate) | Money + Investing merge into one net-worth spine with Cash/Investments lenses | Money + Investing merge into one narrative stream; sub-pages become jump targets |
| **Navigation model** | Same sidebar/tab bar, statement-style skin | Lens chips + collapsed Explore rail | Omnibox (nav + assistant merged) + 3-icon backup rail |
| **Primary layout unit** | Ledger lines under a statement header band | Full-width instrument bands (fixed legend rail + content) | Reverse-chronological dated prose entries |
| **Density** | High (tight rows, hairline-separated) | Medium (spine bands, collapsible) | Low in the stream, but a pinned numeric line stays high-density |
| **Typography** | Plex Sans + Plex Mono (statement pairing) | Manrope + Space Mono (instrument pairing) | Newsreader + Fragment Mono (editorial pairing) |
| **Geometry** | ~0 radius, zero shadow, bracketed text tags | 2–4px radius, hairline bands, meaningful tick marks | 0 radius prose, 8px chips only on tappable inline entities |
| **Signature element** | Statement header band + digit-column settle | The sync spine (tappable, freshness-colored tick marks) | Inline bloom on tapped entities within generated prose |
| **Motion signature** | Digit-column spring on real value change only; no page transitions | Breathing sync tick while actively syncing; causal-note crossfade | Inline bloom spring (260–320ms); reverse-chrono opacity recession |
| **Engineering lift** | Low — tokens, typography, component skins | Medium/high — real IA + routing change, new sync-detail data surfacing | High — entity-tagged narrative generation, new omnibox, richer a11y work |
| **Primary risk** | Can read as under-designed/boring if executed timidly | Longer build; causal-note generation must be reliable or fall back | Prose-first may fight the twice-daily reflexive-glance workflow |

## On choosing between these

This document intentionally stops short of recommending one. The honest
axis to weigh them on is how much appetite exists for IA/routing change
(A: none, B: moderate — merges two verticals, C: most — replaces both with
a stream) versus how much the redesign should lean into what's *only*
true about Posted (A leans least on that, using the domain mainly as
typographic/motion justification; B and C both make a Posted-specific
mechanism — the sync spine, the entity-tagged debrief — the actual
structure). Any of the three clears the redesign's non-negotiable bar (no
bento grid, no centered hero, no purple/blue glow, no interchangeable card
grid); which one is worth the corresponding engineering lift is a product
call, not a design one.
