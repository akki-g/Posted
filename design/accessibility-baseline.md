# Posted accessibility baseline — WCAG 2.1 AA (RN/react-native-web translation)

Scope: `AppShell.tsx`, `app/settings.tsx`, `app/index.tsx`, `app/money.tsx`, `app/invest.tsx`,
`AssistantDrawer.tsx`, `AssistantChat.tsx`, `components/StockPriceChart/` and its supporting
libs (`lib/chartInteraction.ts`, `chartScrub.ts`, `chartZoom.ts`), plus the components those
screens compose directly (`HoldingsList.tsx`, `MarketSearch.tsx`, `ui.tsx`, `PortfolioChart.tsx`).
Read-only audit, current state of the working tree on `frontend-redesign` (including the
uncommitted edits to `index.tsx`/`invest.tsx`/`money.tsx`). No code was changed to produce this
document.

## How to read this document

Posted has no DOM — every check below had to be translated from the checklist's HTML terms
(`<button>`, `aria-label`, `role="status"`) to React Native's accessibility API and then verified
against how `react-native-web` (RNW) actually renders that API to the browser, since that's the
one target with a real accessibility tree today (iOS/Android RN apps have their own native a11y
tree, not audited here beyond noting where behavior diverges). Three RNW behaviors are load‑bearing
for almost every finding below and are worth stating once, with the exact source consulted
(`apps/client/node_modules/react-native-web/dist/...`):

1. **Every `Pressable` is keyboard-focusable by default.** `Pressable/index.js` sets
   `tabIndex = disabled ? -1 : 0` unless you pass `tabIndex` explicitly — so on web, a `Pressable`
   with no `accessibilityRole` is still a tab stop. But **only `Enter` activates it** by default;
   `usePressEvents/PressResponder.js`'s `isValidKeyPress` only treats `Space` as an activation key
   when the element's tag is `button` or its `role` attribute is `button` — i.e., **Space only
   works if `accessibilityRole="button"` is set.** A plain `View` (not `Pressable`) gets no default
   `tabIndex` at all and is invisible to keyboard/Tab entirely.
2. **`accessibilityRole` strings not in RNW's small explicit map pass straight through as the raw
   ARIA `role`** (`propsToAriaRole.js`): `accessibilityRole="menu"` really does become `role="menu"`
   in the DOM, `"tab"` becomes `role="tab"`, etc. So most RN-to-ARIA gaps in this app are
   fixable — they're missing props, not a platform ceiling. The one genuine platform ceiling: RN's
   typed `AccessibilityRole` (see `react-native/.../ViewAccessibility.d.ts`) has **no `"dialog"`
   value**, so a true `role="dialog"` on web requires passing the raw `role`/`aria-modal` props
   RNW's `View` still forwards (`forwardedProps/index.js` lists `role` and `aria-modal` as
   passthrough), guarded by `Platform.OS === 'web'` or just always (native ignores unknown props).
3. **`accessibilityActions` / `onAccessibilityAction` and the object form of `accessibilityValue`
   are not implemented by react-native-web at all** — grepping the entire RNW `dist/` tree, these
   names appear nowhere in the forwarded-props lists (`forwardedProps/index.js`) or in `View`'s
   prop handling; only the flat `accessibilityValueMin/Max/Now/Text` props are forwarded, and only
   as raw pass-through (nothing translates the object form into them). This single fact is the
   root cause of the most severe finding in this document (§1, chart scrub) — code written
   correctly for native VoiceOver/TalkBack does nothing on the web target Posted actually ships to
   as its primary desktop experience.

**Severity legend**
- **Critical** — blocks an entire workflow for keyboard-only or screen-reader users; no alternative path exists anywhere in the UI.
- **High** — a real WCAG 2.1 AA failure that any keyboard/AT user hits in a normal path, not an edge case.
- **Medium** — a real AA gap, but narrower in blast radius, inconsistent rather than universal, or has a partial workaround already in the UI.
- **Low** — best-practice / near-miss / a standard the project has *chosen* to hold itself to that's stricter than literal WCAG 2.1 AA (the 44×44 touch-target floor is this: WCAG 2.1 AA has no numeric target-size criterion at all — 2.5.5 Target Size is AAA, and the 24×24 minimum of 2.5.8 is a **2.2** AA addition. Posted's own `product-design/SKILL.md` commits to 44×44 explicitly, so it's graded against that as the project's real floor.)

---

## 1. Keyboard navigation

### 1.1 [Critical] Chart scrub ("drag to inspect") has zero keyboard or screen-reader path on web
- **Files**: `apps/client/src/components/StockPriceChart/PricePanel.tsx:217-231`,
  `apps/client/src/components/StockPriceChart/OscillatorPanel.tsx:162-176`,
  `apps/client/src/components/PortfolioChart.tsx:163-177` (same bug, on the in-scope `index.tsx`
  portfolio-overview chart), root cause in `apps/client/src/lib/chartScrub.ts:71-77`.
- **What**: The interactive "tracking layer" is a plain `View` (not `Pressable`) with
  `{...scrub.panHandlers}`, `onPointerDown`/`onPointerMove` (mouse/touch only), plus
  `accessibilityRole="adjustable"`, `accessibilityValue={scrub.accessibilityValue}`,
  `onAccessibilityAction={scrub.onAccessibilityAction}`, and `accessibilityActions={[...]}`. This
  is the textbook-correct native RN pattern (VoiceOver/TalkBack would announce it as an adjustable
  slider and swipe up/down would call `onAccessibilityAction`). But per the RNW behaviors above:
  the `accessibilityActions`/`onAccessibilityAction`/`accessibilityValue` props are silently
  dropped on web, and because it's a `View` with no `tabIndex` prop, it isn't even in the tab
  order. Net effect on web: the crosshair/"selected bar" that drives OHLC readouts, indicator
  values, and the assistant's chart context can **only be moved with a mouse or touch drag.**
  There is no arrow-key, no Tab-reachable control, nothing a screen-reader user or keyboard-only
  user can do to inspect any bar other than the default last one.
- **Why it matters**: this is the signature interaction of the flagship chart component
  (`product-design/SKILL.md` explicitly calls `StockPriceChart/` "the existing pattern to match"
  for future screens) and it's on the primary portfolio-overview screen too, not a rare page.
- **Fix**: give `useChartScrub` a `moveBy(delta: number)` function used by *both* the native
  `onAccessibilityAction` handler and a new `onKeyDown` on the tracking layer (`ArrowLeft`/
  `ArrowRight` → `moveBy(-1)`/`moveBy(1)`, `Home`/`End` → first/last index). Add `tabIndex={0}` to
  the tracking layer (or swap it for `Pressable`, which sets this by default) and switch
  `accessibilityValue` to the flat, RNW-forwarded props (`accessibilityValueMin`,
  `accessibilityValueMax`, `accessibilityValueNow`, `accessibilityValueText`) so a value actually
  reaches the DOM as `aria-valuemin/max/now`. Add a visible focus ring (see §7 pattern) so sighted
  keyboard users can find it.

### 1.2 [High] Range brush has no keyboard or accessibility-action path on *any* platform
- **File**: `apps/client/src/components/StockPriceChart/RangeBrush.tsx:119-154`
- **What**: `accessibilityRole="adjustable"` and `accessibilityLabel="Chart zoom range"` are set,
  but unlike `PricePanel`/`OscillatorPanel` there is **no `accessibilityValue`, no
  `accessibilityActions`, no `onAccessibilityAction` at all** — so even native VoiceOver/TalkBack
  has nothing to act on. The only interaction is `PanResponder` + `onPointerDown/Move/Up`
  (drag the `move`/`left`/`right` handle regions, hit-tested within `HANDLE_HIT_PX = 14`px of the
  handle). No `tabIndex`.
- **Why it matters**: setting a precise zoom range is completely unreachable without a mouse or
  touch, on every platform, with no fallback.
- **Mitigating factor**: the coarse zoom in/out/reset buttons next to it
  (`StockPriceChart/index.tsx:444-467`) *are* keyboard accessible (`Pressable` +
  `accessibilityRole="button"` + `accessibilityLabel`), so zooming isn't 100% blocked — only
  precise range-setting via the brush is.
- **Fix**: same pattern as §1.1 — wire real `accessibilityActions`/`onAccessibilityAction` for
  native, plus a keyboard handler for web (arrow keys move the whole window; Shift+arrow resizes
  one edge), plus `tabIndex`.

### 1.3 [Medium] Discoverability: the only visible instructions describe pointer-only interaction
- **Files**: `StockPriceChart/index.tsx:374` (`"SCROLL TO ZOOM · DRAG TO INSPECT"`),
  `PortfolioChart.tsx:81` (`"MOVE OR DRAG TO INSPECT"`)
- **What**: these captions are accurate today — there genuinely is no keyboard alternative — but
  even after §1.1/§1.2 are fixed, the visible hint text should mention the keyboard path (e.g.
  "Drag or use arrow keys to inspect") so sighted keyboard users know it exists.
- **Fix**: update copy once a keyboard path ships.

### 1.4 [Medium] `HoldingsList` cash rows are inert but still capture a Tab stop
- **File**: `apps/client/src/components/HoldingsList.tsx:46-58` (mobile row),
  `HoldingsList.tsx:91-103` (desktop table row)
- **What**: for `holding.asset_type === 'cash'`, both `accessibilityRole` and `onPress` are set to
  `undefined`, but `disabled` is never passed. Per §-methodology point 1, `Pressable` defaults to
  `tabIndex=0` unless explicitly `disabled` — so tabbing through a holdings list lands on a silent,
  unlabeled, do-nothing stop at the cash row every time one is present.
- **Fix**: `disabled={holding.asset_type === 'cash'}` on both Pressables, or render a plain `View`
  for the cash row instead of `Pressable` when there's no `onPress`.

### 1.5 [Medium] `MarketSearch` typeahead results have no keyboard navigation and race their own close timer
- **File**: `apps/client/src/components/MarketSearch.tsx:90-119` (input), `120-163` (results),
  used from `invest.tsx:75`
- **What**: the results dropdown is a list of `Pressable` rows with `accessibilityRole="link"` —
  each is individually reachable via Tab, and `Enter` on the input submits the exact/first match
  (`onSubmitEditing`, line 99-102), but there is **no `ArrowDown`/`ArrowUp` navigation** between
  results (no combobox/listbox pattern — no `role="combobox"` on the input, no `role="listbox"`/
  `role="option"` on the results, no `aria-activedescendant`). Worse, `onBlur` hides the list after
  a 180ms timeout (line 96) with no distinction between "blurred because the user clicked a
  result" and "blurred because the user tabbed forward into the list" — a keyboard user tabbing
  from the input toward the first result row can have the list disappear out from under them.
- **Fix**: implement the standard combobox pattern (`role="combobox"` + `aria-expanded`/
  `aria-controls` on the input, `role="listbox"`/`"option"` on results, arrow-key handling that
  moves a highlighted index and `Enter` accepts it), and don't hide on blur when focus is moving
  to a child result — check `event.relatedTarget` (web) instead of a fixed timeout.

### 1.6 [Low] Icon-only buttons that skip `accessibilityRole="button"` lose Space-key activation
This is one root cause repeated across every in-scope screen; see §3 for the full list of exact
sites (same instances, catalogued there to avoid duplication). Net keyboard effect everywhere it
appears: `Enter` works (any focusable element does), `Space` does not (RNW only wires Space to
button-role/tag elements per methodology point 1).

---

## 2. Focus management

### 2.1 [High] Account-menu dropdown: no focus-in, no trap, no Escape, no return-focus
- **File**: `apps/client/src/components/AppShell.tsx:259-312`
- **What**: `setMenuOpen(true)` (line 262) renders the dropdown (lines 268-312) with no
  accompanying focus movement anywhere in the component — no ref, no `useEffect` on `menuOpen`.
  Concretely:
  - Opening does not move focus into the menu (a screen-reader/keyboard user has no indication
    focus went anywhere; it stays on the avatar button while a new layer appears).
  - There's no `onKeyDown` for `Escape` anywhere in `AppShell.tsx` (confirmed: no `Escape`/
    `onKeyDown` string appears in the file) — the only way to close is clicking the backdrop
    (line 270) or picking an item.
  - Closing (via backdrop click or item selection) never returns focus to the avatar button that
    opened it, so a keyboard user's focus is simply lost/reset to document body.
  - The backdrop itself (`styles.menuBackdrop`, line 270) is a `Pressable` with **no
    `accessibilityLabel` and no role** — per methodology point 1 it still gets `tabIndex=0` by
    default, so it becomes an unlabeled, silent phantom Tab stop sitting between the avatar button
    and the menu items in the tab order.
- **Fix**: on `menuOpen` becoming `true`, focus the first menu item (ref + `.focus()` on web, or
  `AccessibilityInfo.setAccessibilityFocus` on native); add an `onKeyDown` at the menu's root that
  closes on `Escape`; on close (any path), return focus to the avatar `Pressable` (ref it); give
  the backdrop `tabIndex={-1}` (or `accessibilityElementsHidden`/`importantForAccessibility="no-hide-descendants"`
  for native) so it never becomes a stop.

### 2.2 [Critical] Assistant drawer: no focus-in, no trap, no Escape, no return-focus, no backdrop at all
- **Files**: `AppShell.tsx:361-368` (mount site), `AssistantDrawer.tsx:27-72` (component)
- **What**: `{assistantOpen ? <AssistantDrawer .../> : null}` is the entire wiring — same gaps as
  §2.1 (no focus-in, no Escape, no return-focus) *plus* it's worse in one respect: unlike the user
  menu, there is **no backdrop element at all** for the floating/compact variants
  (`panelFloating`/`panelFloatingCompact` in `AssistantDrawer.tsx:86-117` are absolutely positioned
  over the page with no dimming/click-catching sibling). That means:
  - Tabbing while the drawer is open is not contained — focus can move from the drawer into
    background page content that is visually covered by the panel (no `aria-hidden`/`inert` is
    applied to the rest of the app, no focus trap inside the drawer either), producing a confusing
    "invisible focus" state for keyboard users.
  - There's no click-outside-to-dismiss on floating/compact layouts at all (contrast with the user
    menu, which at least has that).
  - The container (`AssistantDrawer.tsx:28-29`) has `accessibilityLabel="Ask Posted contextual
    assistant"` but no dialog semantics — per methodology point 2, RN has no typed `"dialog"`
    role, but RNW still forwards a raw `role`/`aria-modal` prop, so `role="dialog"` +
    `aria-modal="true"` is achievable on web with a small `Platform.select`/prop-spread; it's
    simply not attempted today.
- **Why Critical rather than High**: this is the app's core cross-screen affordance (per
  `product-design/SKILL.md`'s domain snapshot, asking the assistant "without leaving the page" is
  a first-class workflow) and it is opened from every screen in the app via the topbar toggle —
  the blast radius is the whole product, not one screen.
- **Fix**: same as §2.1 (focus-in on open, trap via a focus-scope or `inert`/`aria-hidden` on
  sibling content while open, `Escape` closes, focus returns to the "Ask Posted" toggle button in
  `AppShell.tsx:232-258` on close), plus add a backdrop for the floating/compact variants and
  `role="dialog"`/`aria-modal="true"` on web.

### 2.3 [Medium] No focus moved to new content anywhere it appears
- Neither the account menu, the assistant drawer, `ParamPopover.tsx` (opened inline from
  `IndicatorToolbar.tsx`/`OscillatorPanel.tsx`), nor any conditionally-rendered error/success
  banner in `settings.tsx` (e.g. `connectionSuccess`/`connectionError` text, lines 385-400) moves
  focus or otherwise announces itself when it appears. `ParamPopover` in particular renders inline
  next to a settings-gear icon button with no relationship (`aria-owns`/`aria-controls`) back to
  the button that opened it.
- **Fix**: for inline popovers like `ParamPopover`, add `accessibilityLabelledBy`/`aria-controls`
  linking the trigger button to the popover, and move focus into the first field when it opens
  (it's a small form, so this is cheap); for banners, see §7's live-region recommendation.

---

## 3. Semantics / screen-reader coverage

Spot-checking the icon-only controls and interactive rows named in the brief, plus every
`Pressable` touched during this audit, for `accessibilityRole`/`accessibilityLabel`/
`accessibilityState` consistency.

### 3.1 [High] Privacy "eye" toggle has a label but no role, in three places
- **Files**: `app/index.tsx:65-74` (`privacyButton`), `app/invest.tsx:51-60` (`iconButton`),
  `app/money.tsx:60-69` (`privacyButton`)
- **What**: all three set `accessibilityLabel={privateMode ? 'Show balances' : 'Hide balances'}`
  (good — a real, state-dependent name) but **none set `accessibilityRole="button"`**. Per
  methodology point 1: Space does nothing, and RNW never renders these as `<button>` — a screen
  reader gets a labeled generic element, not a control identified as a button.
- **Fix**: add `accessibilityRole="button"` to all three (trivial, no visual change).

### 3.2 [Critical] Both notification `Switch` controls have no accessible name at all
- **File**: `apps/client/src/app/settings.tsx:529-534` (push notifications),
  `settings.tsx:542-547` (morning briefing)
- **What**: verified directly in `react-native-web`'s `Switch/index.js:127-138` — the underlying
  DOM node is a real `<input type="checkbox" role="switch">` with
  `'aria-label': ariaLabel || accessibilityLabel`. Neither `Switch` here passes `accessibilityLabel`
  (or `aria-label`), so on web this literally renders `aria-label={undefined}` — a screen reader
  announces **"switch, not checked"** with zero indication of what it controls. This is the single
  cleanest, most concrete Name/Role/Value (4.1.2) failure found in the audit: the underlying
  control is a real native `<input>` (excellent — fully keyboard-operable, Space toggles it, it's
  correctly in the tab order) that is simply missing one prop.
- **Fix**: `accessibilityLabel="Push notifications"` / `accessibilityLabel="Morning briefing"` on
  the two `Switch` elements (`SettingRow`'s `control` prop, lines 528-536 / 541-549).

### 3.3 [Medium] Connection sync/unlink buttons: `accessibilityLabel` present, role inconsistent with sibling buttons in the same file
- **File**: `apps/client/src/app/settings.tsx:233-254` (bank sync/unlink),
  `settings.tsx:312-335` (brokerage sync/unlink)
- **What**: these four `Pressable`s all correctly set a descriptive, per-connection
  `accessibilityLabel` (e.g. `` `Unlink ${connection.display_name}` ``) but none set
  `accessibilityRole="button"` — while the "SIGN IN" button 30 lines above (line 197) and the SMS
  "UNLINK" button 190 lines below (line 438) *do* set it. Same file, same visual language
  (bordered pill button), inconsistent semantics.
- **Fix**: add `accessibilityRole="button"` to all four for consistency with the rest of the file.

### 3.4 [Medium] Several settings.tsx action buttons have no role *or* label at all
- **Files**: `settings.tsx:369-381` ("Connect or reconnect Schwab"), `settings.tsx:462-473`
  ("Send code"), `settings.tsx:488-499` ("Verify"), `settings.tsx:505-512` ("Resend code")
- **What**: none of these four set `accessibilityRole` or `accessibilityLabel`; they rely entirely
  on the visible `<Text>` child for an accessible name (which does work as a fallback name source,
  so these aren't silent like §3.2 — but they're still missing explicit button semantics, so Space
  doesn't activate them and no "button" role is announced).
- **Fix**: add `accessibilityRole="button"` to each (labels aren't strictly required since the
  visible text is descriptive, but adding them costs nothing and future-proofs against the text
  being replaced by an icon).

### 3.5 [Medium] `ui.tsx`'s shared `ErrorState` retry button has no role or label
- **File**: `apps/client/src/components/ui.tsx:86-90`
- **What**: `<Pressable onPress={retry} style={styles.retryButton}>` with an icon + "Retry" text,
  no `accessibilityRole`/`accessibilityLabel`. `ErrorState` is reused on essentially every screen
  in the app (confirmed via `design/frontend-audit.md`'s route map) — this is a single-line fix
  with the widest blast radius of any semantics finding in this audit.
- **Fix**: `accessibilityRole="button"` on `ui.tsx:86`.

### 3.6 [Low] Account-menu dropdown items have no role at all
- **File**: `AppShell.tsx:282-309` ("Settings", "Sign out", "Sign in with Google")
- **What**: three `Pressable`s with only visible `<Text>` children, no `accessibilityRole`. Given
  §2.1's larger menu-semantics gap, the concrete fix is `accessibilityRole="menuitem"` on each item
  and `accessibilityRole="menu"` on the menu container (`styles.userMenu`, line 271) — both values
  pass straight through to real ARIA roles per methodology point 2, so this is a real fix, not a
  platform-limited one.

### 3.7 [Low] Account-menu toggle doesn't expose expanded/collapsed state; the assistant toggle right next to it does
- **File**: `AppShell.tsx:259-265` (avatar button) vs. `AppShell.tsx:232-244` (assistant button)
- **What**: the assistant toggle sets `accessibilityState={{ expanded: assistantOpen }}` (line
  235) — correct, and a good pattern already in the codebase. The avatar button three lines below
  it, toggling a structurally identical dropdown, does not set `accessibilityState`. A screen
  reader user gets "expanded"/"collapsed" for one toggle and nothing for the other.
- **Fix**: `accessibilityState={{ expanded: menuOpen }}` on `AppShell.tsx:259-265`.

### 3.8 [Informational — good patterns to preserve] What's already correct
Worth calling out explicitly so the redesign doesn't regress them:
- `AssistantChat.tsx` is the most consistent file in the audit: every `Pressable` (clear, section
  pills, suggested-prompt chips, source links, send button) sets `accessibilityRole` and, where
  icon-only, `accessibilityLabel`; toggle-like controls set `accessibilityState={{ selected }}`
  (lines 159, 199, 279).
- `IndicatorToolbar.tsx` and `ParamPopover.tsx` (chart chrome) are equally disciplined —
  every button has role/label/state.
- `money.tsx`'s `MobileQuickAction` (line 287) sets `accessibilityRole="button"` correctly.
- `HoldingsList.tsx` and `MarketSearch.tsx` correctly use `accessibilityRole="link"` for
  navigation-triggering rows (as opposed to `"button"`), matching the checklist's button-vs-link
  distinction.
- Gain/loss values are **not** color-only: `lib/format.ts`'s `signedMoney`/`percent` (lines 15-23)
  prepend an explicit `+`/`-` sign, so every green/red metric in `index.tsx`/`invest.tsx`/
  `money.tsx` already satisfies 1.4.1 (Use of Color) via redundant text. Preserve this in the
  redesign — see §8.
- `Switch`'s underlying implementation (once §3.2 is fixed) is a real native `<input
  type="checkbox">` on web — fully keyboard/AT-operable "for free."

---

## 4. Contrast

Ratios computed directly from `apps/client/src/theme/tokens.ts` hex values using the WCAG
relative-luminance formula (sRGB → linear → 0.2126R+0.7152G+0.0722B, contrast =
(L1+0.05)/(L2+0.05)). AA thresholds: **4.5:1** normal text, **3:1** large text (≥18px regular /
≥14px bold) and non-text UI components.

| Pair (fg on bg) | Ratio | Normal-text AA | Large-text/UI AA |
|---|---|---|---|
| `ink` #121A26 on `surface` #FFFFFF | 17.48:1 | Pass | Pass |
| `inkMuted` #5B6675 on `surface` #FFFFFF | 5.83:1 | Pass | Pass |
| **`inkFaint` #7D8794 on `surface` #FFFFFF** | **3.64:1** | **Fail** | Pass |
| **`inkFaint` #7D8794 on `canvas` #EDF0F4** | **3.19:1** | **Fail** | Pass |
| **`inkFaint` #7D8794 on `surfaceMuted` #E9EDF1** | **3.10:1** | **Fail** | Pass |
| **`inkFaint` #7D8794 on `tealSoft` #DDF2F2** | **3.13:1** | **Fail** | Pass |
| `inkMuted` #5B6675 on `canvas`/`surfaceMuted` | 5.10 / 4.95:1 | Pass | Pass |
| `teal` #087E8B on `surface` #FFFFFF | 4.81:1 | Pass | Pass |
| `tealDark` #075E68 on `surface`/`tealSoft` | 7.47 / 6.43:1 | Pass | Pass |
| `positive` #14804A on `surface` #FFFFFF | 4.98:1 | Pass (thin margin) | Pass |
| **`positive` #14804A on `positiveSoft` #DFF3E8** | **4.30:1** | **Fail** | Pass |
| `negative` #C73E4D on `surface` #FFFFFF | 4.97:1 | Pass (thin margin) | Pass |
| **`negative` #C73E4D on `negativeSoft` #FBE5E7** | **4.13:1** | **Fail** | Pass |
| `warning` #9A5B00 on `surface`/`warningSoft` | 5.43 / 4.83:1 | Pass | Pass |
| `blue` #2764D8 on `surface` #FFFFFF | 5.38:1 | Pass | Pass |
| white on `navy` #101827 / `navyRaised` #182235 | 17.77 / 15.92:1 | Pass | Pass |
| **`navLabel` #6F7C8F on `navy` #101827** (sidebar group labels) | **4.19:1** | **Fail** | Pass |
| `navText` #AAB4C1 / inactive icon #9DA9B9 on `navy` | 8.47 / 7.45:1 | Pass | Pass |
| `line` #D6DCE2 on `surface` (input/divider border) | 1.38:1 | — | **Fail (needs 3:1 as a UI-component boundary)** |

### 4.1 [High] `inkFaint` fails normal-text contrast against every surface it's paired with, and is used for real (non-decorative) text at 7-10px in 23 files
- **Representative in-scope sites** (89 total usages across the app; grep confirms 23 files):
  - `app/settings.tsx:703` — the compliance-relevant disclaimer ("Posted categorizes financial
    activity... Verify important amounts with your financial institution.") at 10px, `inkFaint` on
    white. 3.64:1.
  - `AssistantDrawer.tsx:165-174` — "Informational only · Posted never places trades" disclaimer,
    8px, `inkFaint` on `canvas`. 3.19:1.
  - `AssistantChat.tsx:354` (`emptyText`) — 12px, `inkFaint` on `surface`/`canvas`. 3.64:1.
  - `app/index.tsx:278`, `invest.tsx:253-258`, `money.tsx:399` — every `metricLabel` ("TOTAL
    PORTFOLIO VALUE", "TODAY", "NET CASH POSITION", etc.), 9px, `inkFaint` on white.
  - `StockPriceChart/index.tsx:505,506,510,538-539` and `PricePanel.tsx` axis labels — readout
    labels, date-axis labels, 7-9px, `inkFaint` on white/`surfaceMuted`.
  - `IndicatorToolbar.tsx:187` (`categoryLabel`, "TREND"/"MOMENTUM"/etc. section labels), 8px.
- **Why it matters**: these aren't decorative captions — several are legally-flavored disclaimers,
  and the rest are the primary metric labels users scan first on the money/portfolio/invest
  screens (per `product-design/SKILL.md`'s own framing: "nothing should compete with net cash /
  portfolio value" — but the labels naming those very metrics fail contrast).
- **Fix**: either darken `inkFaint` itself (something ≥ `#5F6975`-ish on white would clear 4.5:1
  while still reading lighter than `inkMuted`), or — better, since the token is used at both
  decorative and textual sites — audit each of the 89 usages and swap textual ones to `inkMuted`
  (5.83:1, already passes everywhere it's been tested above) while reserving `inkFaint` strictly
  for large text (≥18px) or purely decorative marks (dividers, dots) that 1.4.3 doesn't apply to.

### 4.2 [Medium] Sidebar group labels ("MONEY"/"INVESTING") fail against the navy sidebar
- **File**: `AppShell.tsx:387-394` (`navLabel`, `#6F7C8F` on `#101827`, 10px, letter-spacing 1.6)
- **Fix**: darken toward `navText`'s `#AAB4C1` (8.47:1) or introduce a dedicated navy-safe
  "faint-on-dark" token rather than reusing a color tuned for light surfaces.

### 4.3 [Medium] "Ready" status badges fail contrast; their "Setup" sibling does not
- **File**: `settings.tsx:694-697` (`readinessBadgeReady`/`readinessTextReady`: `positive` on
  `positiveSoft`, 4.30:1, at 8px) vs. the default state (`inkMuted` on `surfaceMuted`, 4.95:1, passes).
- **Fix**: darken the "Ready" text color a step (e.g. reuse `tealDark`-style darkening logic
  already applied elsewhere) or lighten `positiveSoft`'s background further.
- **Related**: `negative` on `negativeSoft` (4.13:1) is the same pattern in the palette; flag for
  wherever it's used as text-on-tint (not found inside the in-scope files, but present in
  `tokens.ts` and likely to be reused by the redesign — see §8).

### 4.4 [Low] Input/divider borders fail the 3:1 non-text-contrast requirement where they're the only boundary cue
- **Files**: `settings.tsx:660-668` (`textInput`, border `colors.line` on white, no background
  fill difference), `ParamPopover.tsx:74-85` (same pattern)
- **What**: `line` (#D6DCE2) on white is 1.38:1 — far under the 3:1 WCAG 1.4.11 threshold for
  identifying a UI component's boundary. Since these text inputs have no background-color
  difference from their surrounding panel (transparent/white-on-white with only a border), the
  border is the *only* affordance marking "this is a field," and it's nearly invisible at low
  contrast/vision-impairment settings.
- **Fix**: use `lineStrong` (#B7C0CA) instead of `line` for input borders specifically (still needs
  checking, but it's meaningfully darker), or add a subtle background fill (`surfaceMuted`) so the
  boundary isn't border-dependent alone.

### 4.5 [Low] Positive/negative value text passes AA with almost no margin
- **Files**: every `positiveValue`/`negativeValue`/`positiveCaption`/`negativeCaption` style in
  `index.tsx`, `invest.tsx`, `money.tsx`, `HoldingsList.tsx`
- **What**: `positive` (4.98:1) and `negative` (4.97:1) on white both clear 4.5:1 by less than
  0.5. This isn't a failure today, but it's fragile — see §8's redesign-risk note.

---

## 5. Reduced-motion behavior

### 5.1 [Informational / forward-looking, not a current bug] No animation exists, and no `prefers-reduced-motion` handling exists to catch what comes next
- **Verified**: `package.json` has no `react-native-reanimated`, no motion/animation library of any
  kind; a repo-wide grep for `Animated\.`, `useNativeDriver`, `LayoutAnimation`,
  `prefers-reduced-motion`, and `AccessibilityInfo` returns **zero matches** in `apps/client/src`.
  The only motion-adjacent things in the app today are instant (non-animated) style swaps on press
  (`pressed && styles.xPressed`, opacity/background changes with no transition duration) and the
  root `_layout.tsx` Stack's `animation: 'fade'` (per `design/frontend-audit.md`), which is a
  platform-default screen transition, not app-authored motion.
- **Why this is still worth flagging in a baseline document**: `product-design/SKILL.md` explicitly
  scopes future motion ("150ms micro-interactions... respect `prefers-reduced-motion` on web") and
  names `react-native-reanimated` as the likely addition. There is currently **no
  `useReducedMotion()` hook, no media-query listener, and no `AccessibilityInfo.isReduceMotionEnabled()`
  call anywhere in the codebase** — meaning if a design-system architect adds hover/press
  transitions or panel-open animations without first adding this plumbing, day one of motion in
  this app ships with zero respect for reduced-motion preferences, which is a straightforward
  1.4.2/2.3.3-adjacent regression (technically 2.3.3 is AAA, but "don't ship new motion no user can
  turn off" is squarely in the spirit of what this audit is meant to prevent).
- **Fix (pre-emptive, before any animation library lands)**: add one small shared hook
  (`useReducedMotion()`), backed by `AccessibilityInfo.isReduceMotionEnabled()` +
  `AccessibilityInfo.addEventListener('reduceMotionChanged', ...)` on native and
  `window.matchMedia('(prefers-reduced-motion: reduce)')` on web, and require every new
  transition/animation added during the redesign to branch on it (durations → 0, or transforms →
  opacity-only) from the first PR that introduces motion, not retrofitted later.

---

## 6. Touch target sizes

WCAG 2.1 AA itself has no numeric target-size criterion (see severity legend) — grading against
Posted's own explicit 44×44 floor (`product-design/SKILL.md`). Every `width: 38`/`height: 38` match
plus every other interactive control found materially under 44 during this audit, file-by-file:

| File:line | Control | Size | Interactive? |
|---|---|---|---|
| `app/index.tsx:255-264` | Privacy eye toggle (`privacyButton`) | 38×38 | Yes |
| `app/invest.tsx:184-192` | Privacy eye toggle (`iconButton`) | 38×38 | Yes |
| `app/invest.tsx:204-210` | Insider-link leading icon | 38×38 | No (decorative, row is the target) |
| `app/money.tsx:361` | Privacy eye toggle (`privacyButton`) | 38×38 | Yes |
| `app/settings.tsx:609-615` | Provider mark icon | 38×38 | No (decorative) |
| `components/AppShell.tsx:431-443` | "Ask Posted" toggle (`assistantButton`) | height 38 (width auto) | Yes |
| `components/AppShell.tsx:448-455` | Account-menu avatar | 34×34 | Yes |
| `components/AssistantDrawer.tsx:155-164` | Drawer close button | 32×32 | Yes |
| `components/AssistantDrawer.tsx:127-134` | Header sparkle icon | 32×32 | No (decorative) |
| `components/AssistantChat.tsx:320-332` | Clear-conversation button | minWidth 38 × height 34 | Yes |
| `components/AssistantChat.tsx:308-316` | Section pills (General/Money/Investing) | height 30 | Yes |
| `components/AssistantChat.tsx:410-417` | Send button | 42×42 | Yes |
| `components/AssistantChat.tsx:399-409` | Composer text input | height 42 | Yes (text field) |
| `app/settings.tsx:626-645` | Sync/Unlink pill buttons (×2 lists) | height 28 | Yes |
| `StockPriceChart/index.tsx:519-529` | Zoom in/out/reset buttons | 26×26 | Yes |
| `StockPriceChart/OscillatorPanel.tsx:200-208` | Settings/remove icon buttons | 22×22 | Yes |
| `StockPriceChart/IndicatorToolbar.tsx:230` | Chip settings/remove icons | 18×18 | Yes |
| `StockPriceChart/IndicatorToolbar.tsx:189-213` | Add-indicator / interval buttons | height 28 | Yes |
| `StockPriceChart/IndicatorToolbar.tsx:232-243` | Signal filter chips | height 26 | Yes |
| `StockPriceChart/ParamPopover.tsx:74-95` | Numeric inputs / Cancel-Apply buttons | height 28 | Yes |
| `StockPriceChart/RangeBrush.tsx:11` | Brush handle hit zone | ~28px (`HANDLE_HIT_PX*2`) | Yes (drag only, see §1.2) |
| `HoldingsList.tsx:152,165-171` | Row action-column arrow / asset badge | 34×34 | Badge no, arrow column yes (whole row is the real target, 62px tall — passes) |

**Pattern**: the chart toolbar (`IndicatorToolbar`/`OscillatorPanel`/`ParamPopover`) is
*consistently* the densest, smallest-target part of the app (18-28px across the board) — this is a
specialist, mouse-oriented power-user surface today, and is the single area most likely to need a
deliberate exception-and-rationale decision (bigger targets vs. accepting a documented,
intentional AAA/44px deviation for a data-dense tool) rather than a blanket fix.

**Fix, general**: raise all "Yes" rows to at least 44×44 (hit-slop via `hitSlop` prop is an
acceptable RN-native way to keep the *visual* chip small while growing the *touch* target, without
changing chart-density aesthetics).

---

## 7. Forms, dialogs, menus, tooltips, overlays

### 7.1 SMS phone/code form (`settings.tsx:448-513`)
- **[Good]** Both `TextInput`s carry `accessibilityLabel` ("Phone number", "Verification code",
  line 453/478) — a real accessible name exists even without a visible `<label>`-equivalent.
- **[Low]** Neither input's visible instructional text ("Enter the 6-digit code below", line 425)
  is programmatically associated with the field it describes (no `accessibilityLabelledBy`/
  `aria-describedby` equivalent) — satisfies 3.3.2 via the `accessibilityLabel` alone, but a
  screen-reader user doesn't get the extra instruction read as part of the field's description.
- **[Low]** Placeholder text (`"+15551234567"`, `"123456"`) is the only visible-to-sighted-users
  format hint and disappears the moment the user types — classic placeholder-as-instruction
  anti-pattern, though not a hard AA failure since `accessibilityLabel` covers the accessible-name
  requirement.
- **[Medium]** No error is announced live: `requestSmsLink.isError`/`verifySmsLink.isError` render
  plain `<Text>` (lines 514-519) with no `accessibilityLiveRegion`/`role="alert"` equivalent — a
  screen-reader user who submits an invalid code gets no spoken feedback unless they manually
  re-scan the screen. **Fix**: `accessibilityLiveRegion="assertive"` (native) and the RNW-mapped
  web equivalent on the error `Text`'s wrapping `View` (RNW forwards `accessibilityLiveRegion` per
  `forwardedProps/index.js:95` — this one *does* work on web, unlike the chart's
  `accessibilityActions`).

### 7.2 Destructive unlink confirmation: `Alert.alert` vs `window.confirm` split (`settings.tsx:113-141`)
- **What it is**: `confirmDestructive` branches on `Platform.OS === 'web'` to use
  `window.confirm()` (since `Alert.alert` is a documented no-op on `react-native-web`) and
  `Alert.alert(...)` on native.
- **[Informational — not a violation]**: both paths are, today, *more* accessible than a typical
  custom modal would be: the browser's native `confirm()` dialog and each OS's native `Alert` are
  both keyboard-operable, focus-managed, and `Escape`-dismissible by the platform itself, for
  free. This is arguably the most accessibility-robust dialog pattern in the entire app precisely
  because it *isn't* custom-built.
- **[Medium — the real risk]**: `window.confirm()` is a blocking, unstyleable, synchronous browser
  primitive — a very likely target for replacement with a custom styled modal during the redesign
  (it's visually completely off-brand). See §8: that swap is exactly the kind of change that
  silently downgrades accessibility unless the replacement explicitly re-implements focus trap +
  Escape + return-focus (§2's gaps, not yet solved anywhere else in this app, would need to be
  solved correctly for the *first* time here).

### 7.3 Account-menu dropdown (`AppShell.tsx:259-312`)
Covered in depth in §2.1/§3.6. Summary: functions as a menu visually and behaviorally (click
outside to close) but has none of `role="menu"`/`"menuitem"`, focus-in, `Escape`, or return-focus.

### 7.4 Assistant drawer as overlay (`AssistantDrawer.tsx`, mounted from `AppShell.tsx:361-368`)
Covered in depth in §2.2. Summary: no dialog semantics, no focus trap, no backdrop for the
floating/mobile variant, no `Escape`, no return-focus. The single biggest overlay-accessibility gap
in the app given how central this feature is.

### 7.5 Inline popovers: `ParamPopover` (indicator settings) and chart-toolbar chips
- **File**: `StockPriceChart/ParamPopover.tsx`, opened from `IndicatorToolbar.tsx:104-113` /
  `OscillatorPanel.tsx:92-100`
- **What**: a small inline form (not a true overlay — renders in normal flow, pushing content down)
  with correctly-labeled inputs and buttons (§3.8's "good patterns" list), but no relationship
  (`aria-controls`/`aria-expanded` on the trigger, `aria-labelledby` on the popover) tying it back
  to the gear icon that opened it, and no focus movement into its first field on open.
- **Fix**: low-cost — add `accessibilityState={{ expanded: isOpen }}` to the trigger buttons (they
  already track `isOpen`/`isSettingsOpen` in state, so this is just adding the prop) and focus the
  first `TextInput` when the popover mounts.

---

## 8. Where the redesign itself is likely to introduce regressions

Concrete, pattern-matched predictions based on what's actually fragile in the current
implementation — not generic warnings.

1. **New motion ships without the reduced-motion hook that doesn't exist yet (§5).** The moment a
   design-system architect adds `react-native-reanimated` for card hover/press or panel-open
   transitions, it will ship with zero `prefers-reduced-motion` handling unless that plumbing is
   built *before* the first animated component, because nothing in the current stack provides it
   to inherit. This is the highest-confidence prediction in this document — it isn't a maybe, it's
   a certainty unless explicitly budgeted as its own task.

2. **A denser holdings/transactions table quietly drops the touch targets and roles that already
   exist.** `HoldingsList.tsx`'s current desktop row is 62px tall (comfortably ≥44) precisely
   *because* it's a low-density row with badge + two lines of text; a "denser table for scanning
   many holdings" (an explicit design-principles goal — `product-design/SKILL.md`'s "a table
   commands scanning/comparison") directly trades off against row height. If row height drops
   toward the 28-38px range already used elsewhere in the app (§6's table), rows will cross under
   44px while *also* being the densest, most repeated interactive element on the busiest screen.
   Any redesign of this table should treat row height as a touch-target-size decision, not a
   spacing decision, and re-verify `accessibilityRole="link"` and the §1.4 `disabled` fix survive
   the rewrite (a full visual rewrite of this component is exactly the kind of change likely to
   drop props that don't show up in a visual diff).

3. **New card/row hover states on web, if built only on `:hover`, will be invisible to keyboard
   focus.** Nothing in the current app relies on hover-only affordances (there's no hover-revealed
   content today), but "new card hover states" is named explicitly as a redesign risk to watch.
   `Pressable`'s RNW hover state (`useHover`) and its focus state (`focused` in the interaction
   callback) are separate booleans — a component that styles only `hovered` and ignores `focused`
   in its style callback will look identical whether or not it has keyboard focus, silently
   reintroducing a focus-visible failure structurally identical to §7.2's `outlineStyle: 'none'`
   finding (`AssistantChat.tsx:408`, `MarketSearch.tsx:220`, plus three more `searchInput` sites in
   `feed.tsx`, `transactions.tsx`, `holdings.tsx` — all removing the native focus outline with no
   compensating focus style, a pattern already present four times over and worth fixing as a batch
   rather than letting new components copy it a fifth time).

4. **`inkFaint`'s contrast debt (§4.1) is architecturally likely to persist or worsen.** It's used
   89 times across 23 files today specifically *because* it reads as "the quiet caption color" —
   exactly the role a redesign's new "faint"/"tertiary" text token will be asked to play. If the
   new token is derived by eye ("a bit lighter than muted") rather than validated against a
   contrast checker the way this document did, the same failure will reappear under a new name.
   Recommend the design-system architect treat 4.5:1-on-`surface` as a hard constraint when picking
   the new faint-text token, not a nice-to-have.

5. **Gain/loss color redundancy (the `+`/`-` sign in `signedMoney`/`percent`) is easy to lose in a
   visual refresh that redesigns how deltas are displayed** (e.g., switching to arrow glyphs, or
   compact `▲2.3%`-style chips) if the new component doesn't deliberately re-implement a
   non-color signal. This is currently one of the app's accessibility strengths (§3.8) and is
   exactly the kind of thing a purely-visual refactor can regress without anyone noticing, since
   the change would still "look correct" to a sighted reviewer using color alone. The thin
   contrast margin on `positive`/`negative` (§4.5, ~4.97-4.98:1) also means a redesign that shifts
   these toward a trendier, slightly different green/red (a very likely "3 materially different
   directions" outcome per the art-direction brief) has almost no room to move before failing AA
   outright — recommend re-validating contrast for any new accent pair before adopting it, not
   after.

6. **The chart's accessibility groundwork (§1.1/§1.2) looks finished but isn't — a redesign that
   trusts the existing `accessibilityActions`/`onAccessibilityAction` code as "already handled"
   will carry the bug forward.** Because the native-RN code is genuinely well-formed (correct
   props, sensible increment/decrement semantics), a design-system architect skimming
   `chartScrub.ts`/`PricePanel.tsx` could reasonably conclude chart accessibility is already
   solved and focus redesign effort elsewhere. It is not solved on web, which is Posted's primary
   desktop surface. If the redesign adds a *new* signature chart interaction (per
   `product-design/SKILL.md`'s per-screen "signature element" requirement), budget explicit
   keyboard-equivalent design for it from the start rather than assuming the existing pattern is a
   safe template to copy.

7. **A custom-styled replacement for `window.confirm()` (§7.2) is the single most likely
   accessibility downgrade in this list.** It's the one dialog in the entire app that currently
   works well specifically *because* it's unstyled and native; every custom-built dialog audited
   in this document (account menu, assistant drawer) fails focus management. A redesign that
   swaps `window.confirm` for an on-brand modal must treat §2's focus-trap/Escape/return-focus
   requirements as launch-blocking for that specific component, not as a follow-up.
