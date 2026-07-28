# Posted — Primary user, workflows, and IA critique

Research artifact only. Grounded in the actual screens (`apps/client/src/app/*.tsx`),
`AppShell.tsx`, `AssistantDrawer`/`AssistantChat`, `useConnectionSync.ts`,
`DebriefPanel.tsx`, and the backend feature list in `README.md`. No code changed.

---

## 1. Primary user — concretely

The `product-design` skill's prior is basically right, and reading the code
sharpens it rather than overturning it:

**One person, checking their own money, alone, on their phone, most days.**
Specifically: someone who has linked a real Schwab (or Plaid-covered)
brokerage and a real bank/credit-card via Plaid — not a demo — and opens
Posted the way they'd open a banking app: standing in line, first thing in
the morning, or right after a payday/statement notification. They are
financially literate (the UI assumes they know MSPR, cost basis, derivative
securities, 10b5-1 filings, recurring-vs-subscription nuance) but they are
**not a trader in the moment of opening the app** — they're not placing
orders (the app is read-only/no-trading, reinforced by the assistant's own
disclaimer: "Informational only · Posted never places trades"). They're
doing a status check, not a task.

Two behavioral details from the code sharpen this further:

- `index.tsx` (the richest screen — chart, debrief, feed, holdings) is
  **web-only**; native iOS/Android hard-redirects to `/money`. So the
  person's *native mobile* daily habit is anchored on cash position first,
  investing second — the code's own routing default treats "money" as the
  primary mobile identity, "portfolio" as a desktop/secondary one. This is
  worth taking seriously rather than reflexively "fixing": for a single
  individual checking from a phone, "did anything weird happen to my cash"
  is plausibly the more frequent question than "what's my portfolio doing,"
  which is more of a sit-down-at-a-desk activity. The IA should treat this
  intentionally rather than as an artifact.
- Settings includes a **verified SMS link to the assistant** (`smsLinkStatus`,
  `requestSmsLink`/`verifySmsLink` in `settings.tsx`, plus the Telnyx bridge
  documented in `README.md`). This means the actual person sometimes isn't
  even opening the app — they're **texting** "What changed in my portfolio
  today?" from wherever they are. That's a strong signal about who this
  person is: someone who wants an answer, not necessarily a screen.

There is no team, no shared household view, no permissions model, no
"invite a collaborator" surface anywhere in the code. Confirmed: not a
collaboration tool. Every workflow below is single-person, single-session.

---

## 2. Workflows, ranked by frequency × stakes

1. **"Did anything unusual happen since I last looked?"** (cash + portfolio,
   combined) — the highest-frequency check, and the one the code has
   *already* tried to build a dedicated answer for: `DebriefPanel` ("TODAY'S
   DEBRIEF") + `unread_event_count` ("ATTENTION NEEDED") on the dashboard.
   This is the single most-repeated motion in the whole app.
2. **Net cash position check** (`money.tsx` — "NET CASH POSITION" hero metric,
   `MobileMoneyOverview`'s navy hero card). Very high frequency, low
   cognitive load — a glance, not a read.
3. **Catching an unusual/unexpected charge** (`transactions.tsx` search +
   filters, `subscriptions.tsx` recurring-charge review). Lower frequency
   than #2 but high stakes when it happens — this is the "surprise charge"
   moment the recurring-detection feature exists specifically to prevent.
4. **Portfolio value + day change + "what moved it"** (`index.tsx` hero
   metrics, `PortfolioChart`, `invest.tsx` on mobile). Daily-ish, medium
   stakes — mostly reassurance, occasionally investigation.
5. **Deciding whether an insider transaction or news event is signal or
   noise** (`insiders.tsx`, `news.tsx`, `feed.tsx` detail panel with AI
   insight + "why this score" reasons + caveats). Lower frequency, but this
   is the deepest, most exploration-oriented workflow in the app — the one
   place multi-source synthesis (transactions + MSPR + price + portfolio
   weight + news + AI) is deliberately built for a "should I care" judgment.
6. **Asking the assistant a question about what's on screen right now**
   (`AssistantDrawer`/`AssistantChat`, `assistantContext`/`assistantSection`).
   Frequency varies a lot by user, but it's the one workflow that cuts
   across every other screen — it's not really workflow #6, it's a modifier
   available to all of 1–5.
7. **Connecting/managing a new institution** (`settings.tsx` Plaid/Schwab
   panels). Rare (happens once per institution, plus occasional
   re-auth/token-expiry), but must be flawless when it happens — a broken
   OAuth or Link flow is a trust-destroying event, not a UX inconvenience.

---

## 3. What each workflow should optimize for

| Workflow | Optimize for | Why |
|---|---|---|
| 1. Daily debrief / "anything unusual" | **Speed + trust**, in that order | It's a glance. If the summary is wrong, stale, or contradicts the numbers below it, trust in the whole app breaks — so speed cannot come at the cost of the numbers being *provably* current. |
| 2. Net cash position | **Speed** | Pure glanceability. One number, one direction (up/down), done in under a second. Nothing here should require reading. |
| 3. Catching an unusual charge | **Clarity** | The task isn't "see a number," it's "understand whether this specific line item is a problem." Needs merchant, category, cadence context — search/filter, not just a feed. |
| 4. Portfolio value + day change | **Speed for the headline, clarity for the "why"** | The metric card is speed; the moment they tap into the chart or holdings, they've switched into a clarity task ("why is today red"). The UI should make that mode-switch explicit, not force both at once. |
| 5. Insider/news "does this matter" | **Exploration + trust** | This is the one place where showing your work (evidence, caveats, confidence, "AI vs deterministic") matters more than speed — `insiders.tsx` already gets this right with `interpretation.factors` / `interpretation.caveats` and an explicit "AI analysis unavailable" fallback rather than a blank space. |
| 6. Ask-the-assistant | **Trust + speed of access, not exploration** | Because the assistant reasons over *real financial data*, an uncertain-sounding or ungrounded answer is worse than no answer. Speed here means "don't make me leave the page to ask," not "answer fast at the cost of being wrong." |
| 7. Connect/manage an institution | **Trust**, full stop | No speed or clarity value can compensate for a connection flow that leaves the person unsure whether their bank is actually linked, syncing, or broken. This is the one workflow where "boring and unambiguous" beats "fast." |

The through-line: this app has **no workflow that should optimize for
exploration as a default mode** except #5. Everything else is a status
check first. That's a useful filter for reviewing any new screen idea: if
it invites open-ended browsing (infinite feeds, "discover" surfaces,
recommendation carousels), it's fighting the actual user, not serving them.

---

## 4. Product-specific interaction opportunities being left on the table

**a. The assistant is contextual under the hood but generic in its chrome.**
`assistantContext`/`assistantSection` genuinely thread per-screen state into
the model (e.g. `index.tsx` passes the exact inspected chart point's date
and value; `insiders.tsx` passes the exact inspected MSPR bar). That is a
real, product-specific capability — a Bloomberg-terminal-style "point at a
thing, ask about the thing" interaction. But the *presentation* is a
bog-standard chat drawer: a title bar, a section-pill row (General/Money/
Investing), a scrolling bubble list, a composer. Nothing in the drawer
itself reflects that it's grounded in the exact number under the user's
cursor. Concrete gap: when `portfolioInspection`/`sentimentInspection` is
set, the drawer's own header only shows a static `contextLabel` (e.g.
"Portfolio overview · Live chart context") — it never surfaces the actual
inspected value ("Aug 14 · $128,402") the way the suggested-prompts logic
already privately knows about it. The context is real; only the chat UI
fails to make it visible. A product-specific version would show the pinned
fact ("You're asking about Aug 14, $128,402") as a small persistent chip
inside the drawer, not just in prompt engineering the user can't see.

**b. Sync freshness is computed but not designed.** `useConnectionSync`
already encodes a genuinely Posted-specific idea: auto-sync once per
page-open if a connection's `last_synced_at` is older than 5 minutes,
otherwise trust cache; manual pull-to-refresh/Sync-now always forces a real
sync regardless of staleness. That's a real state machine — *fresh /
auto-syncing / stale-but-not-yet-refreshed / manually-forced / demo
(never syncs)* — and it currently renders as exactly one thing everywhere:
a small green dot (`liveDot`, hardcoded to `colors.positive`, never
conditional) plus "Last synced {relativeTime}" text. The dot is green even
when data is 4 minutes 59 seconds stale and about to trigger an auto-sync,
and green even in demo mode where "synced" is meaningless. There is no
`stale` token in `theme/tokens.ts` at all (checked: `positive`/`negative`
exist, no stale/live/demo semantic color). For an app whose entire premise
is "trust this number, it's your real bank account," sync state deserves
its own token and its own always-visible affordance — not a spinner that
appears for the ~1 second a manual sync takes and a static dot the rest of
the time.

**c. The morning debrief — the app's best answer to the #1 workflow — is
the least reachable surface in the app.** `DebriefPanel` (AI summary +
top holdings + weekly spending + upcoming charges, i.e. exactly workflow #1
above) only renders inside `PortfolioDashboard` in `index.tsx`, which is
explicitly `Platform.OS !== 'web'` redirected away from on native
iOS/Android (`<Redirect href="/money" />`). So the single most
synthesized, highest-value "what should I know right now" view — the one
genuinely differentiated piece of UI in the whole app — is invisible on the
platform (phone) this person most plausibly opens the app from. This isn't
a "nice enhancement to consider," it's the flagship feature shipping to the
wrong surface.

**d. The full-page `/assistant` screen is orphaned.** Grep across
`app/` and `components/` for `'/assistant'` turns up exactly two hits, both
in `AppShell.tsx`, and both are the *guard* that hides the "Ask Posted"
button while already on that route — nothing anywhere (`mobileNav`,
`moneyNav`, `portfolioNav`, any `router.push`) ever navigates a user to it.
It has its own layout, its own eyebrow ("AI · BUDGETING & INVESTING"), and
reuses `AssistantChat` in full (non-compact) mode — clearly intended as a
"expand the drawer to a full workspace" destination — but that expand
action doesn't exist. Either wire an expand affordance from the drawer into
this screen, or delete the dead route; right now it's neither ambient nor
reachable.

**e. Insider/news screens already do the "product-specific" thing right —
worth protecting, not just critiquing elsewhere.** `insiders.tsx`
deliberately separates a deterministic, always-available
`interpretation` (headline/summary/factors/caveats) from an optional
`ai_insight`, and shows a specific "AI analysis is not configured" vs.
"...temporarily unavailable" distinction rather than collapsing both into
a blank state. That's a real trust-preserving pattern (never let the
AI-shaped part of the screen look broken or absent without an explanation)
that the redesign should generalize to the assistant drawer and the
debrief panel, both of which currently show a flatter "no AI summary
available right now" without distinguishing "not configured" from
"errored" from "still generating."

**f. SMS is a second, ambient front-end to the same assistant — and the
in-app IA doesn't acknowledge it exists.** `settings.tsx` lets someone
verify a phone number and text Posted questions directly (backed by the
Telnyx bridge in `README.md`). This means "ask the assistant" is not solely
an in-app interaction — for this specific person, it may be the *most*
ambient one (no app-open required at all). The in-app assistant UI (drawer,
full page) has no acknowledgment of this — no "you can also just text this
to Posted" affordance, no shared conversation history surfaced between SMS
and in-app chat (worth confirming whether `assistant-messages` even
includes SMS-originated turns). If they're separate threads, that's a
trust gap: the person may not know their SMS question and their in-app
question aren't the same conversation.

---

## 5. Proposed IA changes

**Current state:** two desktop sidebar groups — MONEY (Money overview,
Transactions, Subscriptions) and INVESTING (Portfolio overview, Impact
feed, News, Holdings, Insider activity) — plus a 4-item mobile bottom nav
(Home→`/money`, Activity, Invest, Recurring) that silently drops Feed,
News, Holdings, Insider activity, the standalone Assistant screen, and
Settings from primary navigation entirely on the platform (native mobile)
this person most likely uses daily.

**Does the MONEY/INVESTING split match how this person actually thinks?**
Partially. Cash-vs-portfolio is a real mental division (different
providers, different cadences, different emotional register — spending is
"did I mess up," investing is "how am I doing"), so keep the two-domain
split at the top level. But the current split conflates **"the daily
status check" (should be fast, single-tab, always the landing view)** with
**"exploration tools" (feed/news/insiders — should be one-tap deeper, not
peers of the status check)**. Right now Impact feed/News/Holdings/Insider
activity sit as four *separate, co-equal* sidebar items under INVESTING,
which reads as "here are six things you might want," when really it's "one
dashboard, with three optional drill-down lenses on the same portfolio."

Proposed changes:

1. **Make the debrief-bearing dashboard the actual landing view on every
   platform**, not a web-only bonus. If a native/mobile-width layout can't
   fit the full desktop grid, ship a mobile-native version of
   `DebriefPanel` (it's already three simple stacked lists plus a summary
   string — this is not a heavy port) inside `MobileMoneyOverview` or a new
   mobile-`index` equivalent, rather than routing mobile away from it
   entirely. This is the single highest-leverage IA change available:
   it fixes finding (c) above and directly serves workflow #1, the most
   frequent one.
2. **Collapse Feed / News / Holdings / Insider activity from four sidebar
   peers into one "Portfolio detail" destination with in-page tabs or a
   segmented control**, landing on whichever lens the person came from
   (e.g. tapping a holding from the dashboard opens straight to the
   Holdings tab; tapping an impact-score event opens straight to Feed).
   This matches how the person actually moves through the app already —
   `insiders.tsx` links out to `/stock/[symbol]` and to news items by event
   id, `index.tsx` links to `/holdings` and `/feed` — it's already a web of
   cross-references pretending to be four independent top-level sections.
   Making that explicit (a persistent sub-nav instead of four sidebar
   rows) reduces the sidebar from "5 investing items" to "1 investing item
   with an internal shape that matches the actual exploration workflow
   (#5)."
3. **Give sync freshness a permanent, visible home instead of a spinner +
   caption.** Concretely: add a `stale`/`syncing`/`synced`/`demo` semantic
   token set to `theme/tokens.ts` (parallel to `positive`/`negative`), and
   surface connection state as a small persistent indicator near whichever
   metric it governs (net cash position, portfolio value) — not buried in
   a footer row shared across a whole account list. This turns an
   invisible internal state machine (`useConnectionSync`'s stale-check)
   into IA the person can actually read at a glance, which matters because
   workflow #1/#2 are "trust the number instantly" tasks.
4. **Repair or remove the mobile navigation gap.** At minimum, Settings
   needs a mobile-bottom-nav-reachable path that isn't buried in the avatar
   menu (connection health is arguably the most consequential thing to
   reach quickly when something looks wrong — see 6c below). Feed/News
   need *some* mobile entry point beyond the desktop sidebar; if item 2
   above collapses them into the portfolio-detail destination, this
   resolves itself as a side effect.
5. **Decide the fate of `/assistant` explicitly.** Either add a
   "expand to full assistant" affordance from the drawer (natural home:
   next to the `X` close button) that pushes to `/assistant` carrying the
   current section/context, or delete the route. An unreachable screen
   with real functionality behind it is worse than either committing to it
   or removing it.
6. **Make the SMS assistant link visible from inside the assistant UI**,
   not just from Settings → Text Messaging. Even a one-line "Also reachable
   by text at [number]" in the drawer's empty state would acknowledge that
   this person's actual relationship with the assistant may start outside
   the app.

---

## 6. Inherited-template choices worth challenging

**a. Settings-as-flat-list-of-rows is a SaaS-onboarding-checklist pattern,
not a "manage my real bank connections" pattern.** `settings.tsx` currently
reads exactly like a generic "Integrations" page: provider mark, name,
metadata line, READY/SETUP badge, Sync/Unlink buttons, repeated per
provider (Plaid, Schwab, Plaid Investments), plus unrelated toggles (push
notifications, morning briefing) and an SMS-linking flow, all inside
identically-styled bordered panels. Nothing about this layout is derived
from "money" or "investing" as domains — swap the labels for any
Yodlee/Teller-based competitor's settings page and it's indistinguishable.
Two specific challenges:
   - **Connection health arguably belongs next to where the connection's
     data is consumed, not in a separate admin page.** A stale/broken Plaid
     connection should surface as a visible, actionable state *on the
     Money overview screen itself* (where the person will notice something
     is wrong — a spending number that hasn't moved in days) rather than
     requiring them to already suspect a problem and go find Settings to
     confirm it. Settings should remain the place to *add/remove*
     connections; *health* of an existing connection is a money-screen or
     invest-screen concern, closer to workflow #2/#4.
   - **The push-notification/morning-briefing toggles and the SMS-linking
     flow are unrelated concerns crammed into "Settings" by convention**
     ("every app has a settings page with toggles"), not because this
     person thinks of "how Posted reaches me" as one category with
     "which banks are connected." Consider whether alert delivery
     preferences belong nearer the debrief/notification surface they
     configure, rather than filed under the same page as OAuth
     connection management.

**b. Four co-equal top-level investing destinations (Feed/News/Holdings/
Insiders) is dashboard-template thinking** ("give every data type its own
nav item") **rather than task-derived thinking.** As covered in §5.2, the
actual person's task is "understand my portfolio," approached from
different angles depending on mood/moment — not "I have five independent
reasons to open the app today, one of which is 'check insider filings.'"
Nobody opens Posted specifically to browse Insider Activity cold; they
arrive there from a holding, a news event, or curiosity sparked by the
portfolio dashboard. The nav structure should reflect that entry pattern.

**c. The green "last synced" dot is decorative-status theater, a
holdover from generic dashboard "everything is fine" indicators** (compare:
Vercel's green "Ready" dot, any SaaS status page's green circle) **rather
than a real reflection of the state `useConnectionSync` already computes.**
It's hardcoded to `colors.positive` in both `index.tsx` and `money.tsx`
regardless of actual staleness, sync-in-progress, or demo-mode. A
trading-terminal-register register (the direction the product-design
skill's starting-point calls for) would make this dot mean something —
tie it to the real state machine — rather than exist purely for the
reassurance-shaped visual vocabulary of "green dot = healthy" that every
consumer dashboard uses whether or not it's true.

**d. Mobile bottom nav's 4-item shape (Home/Activity/Invest/Recurring)
reads as "pick four things to fit in a tab bar" (a generic mobile-app
convention) rather than "these are the four things this specific person
needs one tap away."** It's a reasonable set, but it was seemingly derived
by omission (whatever's left after Feed/News/Insiders/Assistant/Settings
got cut for space) rather than by design — none of the cut items got a
deliberate "where does this live on mobile instead" answer, they just
don't have one (see finding (d) in §4 and the orphaned-route problem).
The redesign should decide the mobile IA on its own terms — including
possibly a 5th tab, a long-press action, or the portfolio-detail
consolidation in §5.2 — rather than accept the current four as a given.

**e. `DemoBanner` treats "you're looking at fake data" as a dismissible-
feeling inline notice (matching generic empty-state/demo-mode banners
across SaaS products) when, for a *financial* app specifically, demo-vs-live
is arguably as important a piece of state as gain/loss color — arguably
deserving the same permanent, ambient treatment proposed for sync
freshness in §5.3, not a banner that scrolls out of view.** Confusing a
demo dollar figure for a real one, even briefly, is a much higher-stakes
mistake here than in a typical SaaS trial-mode banner.

---

## Summary for the redesign

The IA's biggest problem isn't the two-group MONEY/INVESTING split (that's
sound) — it's that the app's best, most product-specific answer to its
most frequent workflow (`DebriefPanel`, workflow #1) is stranded on the
platform this person uses least, while four peer-weighted investing nav
items exist mostly to host cross-linked drill-downs of one underlying
portfolio story. Sync freshness and demo-mode are both real, computed
states (`useConnectionSync`, `demo_mode` flags) rendered as generic
decoration (a static green dot, a scrollable banner) instead of ambient,
Posted-specific truth indicators — exactly the kind of signature-element
opportunity the redesign brief calls for and the current build hasn't
claimed yet.
