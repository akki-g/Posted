# .agent/ — redesign skill bundle

Normalized, vetted design-skill bundle for Posted's frontend redesign
(see `design/` for audits and the approved direction). Not auto-discovered by
Claude Code's skill loader (that only reads `.claude/skills/`) — this is
reference material for the lead agent and any subagents doing redesign work.
Read `skills/product-design/SKILL.md` first; it is the single source of truth
and resolves anywhere the three source skills below disagreed.

## skills/

- `frontend-design/` — anthropics/skills. Aesthetic-direction process:
  ground design in the actual subject, avoid the three current
  AI-design-cluster defaults, brainstorm → plan → critique → build.
- `frontend-ui-engineering/` — addyosmani/agent-skills (one skill pulled out
  of a much larger monorepo). Production-UI engineering: component
  architecture, state-management choice, WCAG 2.1 AA patterns, responsive
  breakpoints. Written for web HTML/JSX — translate to React Native's
  accessibility API per `product-design/SKILL.md`.
- `frontend-design-principles/` — joshuadavidthomas/agent-skills (one skill
  pulled out of a much larger monorepo). Forces domain-specific intent
  (who/what/feel) before generating anything; `app.md` is the
  dashboard/SaaS-specific deep dive, which is Posted's category.
- `product-design/` — **the project-specific synthesis.** Combines the three
  above with Posted's actual domain and the redesign's non-negotiable
  originality rules into one coherent workflow. Use this one; consult the
  others only for the deep-dive detail it points to.

## reports/

- `skill-acceptance.md` — what was accepted, modified, or rejected from each
  source, and why.

## Reference repositories (not a `skills/` entry — pattern references only)

Cloned read-only to scratch (not vendored here): shadcn/ui, MUI Base UI,
motion-primitives, Motion, react-bits, Magic UI, Origin UI,
awesome-shadcn-ui. Consult for interaction/animation *patterns* during
design and implementation; never copy a component wholesale — Posted is
Expo/React Native, these are mostly web-only React + Tailwind/Radix, and
anything borrowed gets rebuilt against Posted's own tokens and primitives.
