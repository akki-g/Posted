---
name: product-design
description: Posted-specific redesign workflow. Synthesizes frontend-design, frontend-ui-engineering, and frontend-design-principles into one process, resolved against Posted's actual domain, platform (Expo/React Native), and the redesign's originality requirements. Use for every screen touched during the redesign.
---

# Product design — Posted

This is the one skill to follow for the redesign. The three source skills
(`frontend-design`, `frontend-ui-engineering`, `frontend-design-principles`)
are folded in here, conflicts resolved. Consult them directly only for the
deep-dive detail they point to (concrete CSS values, the full a11y checklist).

## Domain snapshot — answer once, apply everywhere

Don't re-derive these per screen; they're fixed for this product. (If a
subagent's own audit suggests one of these is wrong, flag it rather than
silently redirecting.)

- **Who:** one financially-engaged individual managing their own money —
  not a team, not an org, not a multi-tenant SaaS customer. They connected
  their own real bank (Plaid) and brokerage (Schwab / Plaid Investments) and
  check this daily. They're comfortable with financial vocabulary (cost
  basis, MSPR, recurring streams) — this is not a beginner-friendly consumer
  app that needs hand-holding.
- **What they must accomplish:** know their net cash position and whether
  anything unusual happened since yesterday; track portfolio value and what
  moved it; catch recurring charges before they surprise them; ask a
  context-aware assistant a question about what's on screen right now
  without leaving the page; connect/manage bank and brokerage links without
  friction.
- **Starting-point feel (subject to the art-direction subagent's own
  answer — this is a prior, not a mandate):** closer to a trading-terminal /
  instrument-panel register than a consumer budgeting app. Numbers-first,
  restrained, monochrome-plus-one-accent. `frontend-design-principles/app.md`'s
  "Precision & Density" / "Data & Analysis" directions are the natural
  starting family, not "Warmth & Approachability." The art-direction subagent
  must still produce 3 materially different directions per the master
  prompt — this is where they start exploring from, not where they must land.

## Platform reality — read before recommending any library or component

Posted is **Expo / React Native**, targeting web + iOS + Android from one
codebase (`react-native-web` on web). This changes which reference material
applies directly vs. needs translation:

- **shadcn/ui, MUI Base UI, Origin UI, awesome-shadcn-ui** are React DOM +
  Radix/Tailwind. They do not run on iOS/Android. Use them only as visual/
  interaction *references* to reimplement with RN primitives (`View`,
  `Pressable`, `Text`) — never as a dependency to install.
  `birobirobiro/awesome-shadcn-ui` is a links list, not a library — treat it
  as a reading list only.
- **Motion (motiondivision/motion, née Framer Motion) and motion-primitives**
  are web-only. For cross-platform motion, the existing stack has no
  animation library yet — `react-native-reanimated` (via Expo) is the
  cross-platform equivalent worth considering if the design direction needs
  real spring/gesture-driven motion; CSS transitions are enough for anything
  web-only (e.g., hover states that don't exist on touch anyway).
- **react-bits, Magic UI** are web (React DOM + Tailwind/Framer Motion)
  component collections. Same rule: reference for the *idea* (a specific
  chart interaction, a specific empty-state treatment), rebuilt in RN.
- **Existing primitives to extend, not replace wholesale:**
  `apps/client/src/components/ui.tsx` (`ActionButton`, `DemoBanner`,
  `ErrorState`, `LoadingState`, `SectionHeader`), `theme/tokens.ts`,
  `AppShell.tsx`. The design-system architect decides what's promoted,
  renamed, or extended here — not a parallel component system.
- **Accessibility API is RN's, not the DOM's.** Where `frontend-ui-engineering`
  and its accessibility checklist say `<button>` / `<label htmlFor>` /
  `aria-label` / `role="status"`, the RN equivalents are: `Pressable` with
  `accessibilityRole="button"`, `accessibilityLabel`, `accessibilityState`
  (`{ disabled, selected, expanded }`), `accessibilityLiveRegion="polite"` /
  `"assertive"` on the container that changes, and focus management via
  refs + `AccessibilityInfo` (native) — `react-native-web` maps most of this
  to real DOM ARIA attributes, so the web target still gets genuine
  semantics. Touch targets: WCAG's 44×44px minimum applies on all three
  platforms; several current controls (e.g. the 38×38 icon buttons in
  `AppShell`/`index.tsx`/`invest.tsx`) are under that and should be corrected
  during redesign, not preserved as-is.

## Required before generating anything for a screen

Merged from `frontend-design-principles`' intent gate and `frontend-design`'s
subject-grounding — do this before writing component code, and again,
briefly, before showing the result:

1. **Name the specific workflow and moment.** Not "the money screen" — "the
   first thing a person checks when they open the app after not looking for
   two days."
2. **Domain vocabulary (5+ terms from Posted's actual world):** net cash
   position, recurring stream, cost basis, day change, MSPR sentiment,
   impact event, demo/live connection, sync — not generic
   dashboard/widget/card language.
3. **Color world:** derive from what these terms actually look like (ledger
   ink, a trading tape's red/green, a bank statement's hairline rule) —
   not "pick a nice palette." One accent, semantic color reserved for
   state (gain/loss, stale/synced, demo/live) — never decorative.
4. **Signature element for this screen:** one thing that follows from what
   *this* screen specifically does and wouldn't make sense elsewhere (e.g.
   a sync-freshness indicator tied to real provider state is Posted-specific;
   a generic "last updated" caption is not). The master prompt requires this
   per major screen — treat it as a gate, not a nice-to-have.
5. **Defaults to reject, named explicitly, 3 of them, for this screen** —
   see the non-negotiable list below for the standing set; add screen-specific
   ones (e.g. for a holdings table: "not a card grid of holdings — a table
   commands scanning/comparison, which is the actual task").

## Non-negotiable originality rules (apply to every screen)

Never default to: centered hero + feature cards, bento grids, everything in
a bordered rounded card, gradient text, purple/blue glow effects,
glassmorphism, pill-shaped controls everywhere, oversized marketing
headings, generic illustrations, floating decorative orbs, meaningless
decorative charts, three-column SaaS layout, or anything that reads as
Linear/Vercel/Notion/Stripe pastiche. A color swap is not a different
direction and not meaningful differentiation.

**A screen fails review when:** swapping the logo makes it look like a
generic SaaS product; the layout or interaction model is substantially
unchanged from a stock dashboard template; most of the interface is
interchangeable cards; it lacks an interaction specific to Posted's domain;
or another finance/SaaS company could ship the same screen unchanged.

## Self-review gates (run before showing anyone the result)

- **Swap test:** swap the typeface/layout for the obvious default — would
  anyone notice? Where it wouldn't matter is where the work defaulted.
- **Squint test:** blur focus — is hierarchy (what's primary vs. ambient)
  still legible? Nothing should compete with net cash / portfolio value / the
  one action that matters on that screen.
- **Signature test:** point at the specific component that is this screen's
  signature element. "The overall feel" doesn't count.
- **Token test:** read the token names aloud — do they belong to Posted's
  world (`ink`, `teal`, `positive`/`negative`, `stale`) or could they be any
  SaaS product's (`gray-700`, `surface-2`, `accent`)?
- **Logo-swap test:** the master prompt's own bar — remove branding, is this
  still identifiably Posted rather than any dashboard?

## Engineering and accessibility floor (non-negotiable, every screen)

- Component structure: colocate a component with its own hook/types when it
  has real internal complexity (see `StockPriceChart/` for the existing
  pattern to match); keep presentation separate from data-fetching
  (container/presentational split already used via TanStack Query + plain
  components — keep it).
- Every interactive control: keyboard-reachable on web, `accessibilityRole` +
  `accessibilityLabel` set, visible focus state, ≥44×44 touch target,
  disabled/loading/error states distinguishable by more than color.
  Loading states are skeletons or explicit `LoadingState`, not a blank frame.
  Empty states explain what to do next, not just "no data."
- Motion: 150ms for micro-interactions (press/hover), ~200ms for
  panel/tab transitions, respect `prefers-reduced-motion` on web. Motion
  communicates a state change — it is never decorative in the core app (the
  login screen is the one place a slightly bolder, hero-style moment is
  earned, since it's Posted's only real first-impression surface).
- Responsive: this app already has real breakpoint logic
  (`useWindowDimensions`, `desktop`/`mobile` splits, a bottom tab bar under
  the mobile breakpoint). Redesign must keep genuinely different mobile
  layouts (already true for Money/Portfolio) — not just reflow the desktop
  grid to one column.
- Never rewrite business logic (query keys, mutation contracts, the sync
  behavior just added, backend calls) to fit a visual idea. If a visual
  direction seems to require a data-shape change, that's a flag to revisit
  the direction, not a license to touch `lib/api.ts` or backend routes.

## Process

1. Brainstorm the screen's domain vocabulary, color world, signature element,
   and 3 rejected defaults (above).
2. Propose direction in prose + ASCII layout sketch; check it against the
   self-review gates before writing code.
3. Build, matching the approved design system's tokens/geometry/motion
   exactly — no one-off colors or spacing values.
4. Self-critique against the gates again; fix what a real critique would
   flag first.
5. Verify: typecheck, accessibility pass, responsive check at the project's
   real breakpoints, and confirm no business-logic drift from step 5 of the
   non-negotiable list.

Be invisible about process in user-facing text — do the brainstorming/
critique internally, surface the direction and the result, not a narration
of the steps.
