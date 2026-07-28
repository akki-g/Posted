# Skill acceptance record

Sources fetched read-only to a scratch directory (never executed — inspected as
markdown only), then selectively copied into `.agent/skills/`.

## anthropics/skills → `skills/frontend-design`

- **Status:** Accepted, verbatim (plus its `LICENSE.txt`).
- **Content:** Single `SKILL.md`. Aesthetic-direction guidance: ground design in
  the actual subject/domain, avoid the three current "AI-generated design"
  clusters (cream+serif+terracotta / near-black+acid accent / broadsheet
  hairline-rule layout), work in a brainstorm → plan → critique → build →
  critique loop, treat copy as design material.
- **Vetting:** No scripts, no shell commands, no instructions outside
  design guidance. No prompt-injection-shaped content. Nothing unrelated to
  frontend design.

## addyosmani/agent-skills → `skills/frontend-ui-engineering`

- **Status:** Accepted, with one reference file added (`accessibility-checklist.md`).
- **Content:** Production-UI engineering guidance — component architecture,
  state-management decision table, the "AI Default" anti-pattern table,
  WCAG 2.1 AA keyboard/ARIA/focus patterns, responsive breakpoints,
  loading/transition patterns.
- **Modification:** The repo is a large multi-skill monorepo (30+ unrelated
  skills: CI/CD, security-hardening, git workflow, observability, etc.). Only
  `skills/frontend-ui-engineering/SKILL.md` and the one referenced deep-dive
  (`references/accessibility-checklist.md`) were pulled in — the rest is out
  of scope for this task and was not copied.
- **Caveat for this project:** the skill's code examples are all HTML/JSX-for-web
  (`<button>`, `<label>`, `aria-*` attributes). Posted is React Native /
  react-native-web, so the *principles* apply but the concrete patterns need
  translation to RN's accessibility API (`accessibilityRole`,
  `accessibilityLabel`, `accessibilityState`, focus refs) — captured in the
  synthesized `product-design` skill rather than copied blind.
- **Vetting:** No scripts run; only the two markdown files were read and
  copied. No prompt-injection-shaped content in either file.

## joshuadavidthomas/agent-skills → `skills/frontend-design-principles`

- **Status:** Accepted: `SKILL.md`, `app.md` (dashboards/SaaS — Posted's
  category), and `references/principles.md` (concrete spacing/depth/type/color
  values). `marketing.md` was **not** copied — Posted has no marketing site in
  scope right now (only a login/landing screen, which is a supporting state,
  not a marketing surface); revisit if that changes.
- **Content:** Forces answering who-the-user-is / what-they're-doing /
  what-it-should-feel-like before generating anything; requires naming domain
  vocabulary, a "color world," a signature element, and defaults explicitly
  rejected; "sameness is failure" test; `app.md` gives a direction table
  (Precision & Density, Sophistication & Trust, Data & Analysis, etc.) suited
  to dashboards.
- **Modification:** The repo is also a large multi-skill monorepo (Rust,
  Svelte, jj, Coolify, roadmap-writing, etc. — all unrelated). Only the one
  skill's relevant files were pulled in.
- **Vetting:** No scripts run; markdown only. No prompt-injection-shaped
  content, no instructions to exfiltrate data or act outside frontend design.

## Reference repositories (shadcn/ui, Base UI, motion-primitives, Motion,
react-bits, Magic UI, Origin UI, awesome-shadcn-ui)

- **Status:** Cloned read-only to a scratch directory for pattern reference
  during design/implementation. **Not vendored into the project** — per the
  master prompt's own instruction not to blindly install these, and because
  Posted is Expo/React Native (these are mostly web-only React + Tailwind +
  Radix libraries that don't run as-is in React Native anyway). Any pattern
  borrowed from them during implementation gets rewritten against Posted's own
  tokens, RN primitives, and accessibility model — never copy-pasted.

## Overall

No source required stripping unsafe or off-topic instructions beyond the
monorepo-scoping above (pulling only the relevant skill out of otherwise
unrelated multi-skill repos). Nothing was rejected outright.
