# Posted — Learning-First Roadmap

[Project README](../README.md) | [Next: Portfolio reconciliation →](01-PORTFOLIO-RECONCILIATION.md)

**Purpose:** define exactly which files you should write, which files the coding agent should write, and the order in which the system should be built.

Posted should teach you how a production data application works without making you spend your time on repetitive CRUD, CSS, OAuth boilerplate, or infrastructure configuration.

---

## 1. The rule for deciding ownership

You should hand-write a file when it answers at least one of these questions:

1. How does raw brokerage data become trustworthy portfolio state?
2. How do inconsistent external events become one canonical event?
3. How does Posted decide whether an event matters to this portfolio?
4. How does the system remain correct when providers fail, retry, or return duplicate data?

You should delegate a file when its main purpose is:

- framework configuration;
- database or HTTP plumbing;
- converting a well-defined domain object to JSON or a UI component;
- calling an external API according to its documentation;
- rendering the frontend;
- deployment, CI, logging configuration, or generated migrations;
- repetitive repository and CRUD operations.

This gives you four portfolio exercises and four money exercises instead of an entire backend full of distractions.

---

## 2. Files you definitely write

| Order | File | Core lesson | Guide |
|---|---|---|---|
| 1 | `backend/app/portfolio/reconcile.py` | Canonical state, accounting invariants, snapshot diffs, idempotency | [Guide 01](01-PORTFOLIO-RECONCILIATION.md) |
| 2 | `backend/app/events/normalize.py` | Anti-corruption layers and canonical event modeling | [Guide 02](02-EVENT-PIPELINE.md) |
| 3 | `backend/app/events/dedupe.py` | Entity resolution, fingerprints, conservative merging | [Guide 02](02-EVENT-PIPELINE.md) |
| 4 | `backend/app/impact/scoring.py` | Explainable ranking, portfolio exposure, confidence, recency | [Guide 03](03-IMPACT-ENGINE.md) |
| 5 | `backend/app/sync/orchestrator.py` | Ports and adapters, failure boundaries, retries, transactions | [Guide 04](04-SYNC-ORCHESTRATOR.md) |

There are five files but four exercises because event normalization and deduplication are learned together.

“You write” means you own the public business workflow and the decisions named in that row. It
does not mean you must spend learning time on generic whitespace cleanup, tuple sort keys,
linear interpolation, or stable hashing boilerplate. When a focused guide labels a helper as
**provided**, the agent may implement that helper in the same file. You should read it and use
its contract, but you do not need to recreate it.

After those five work, continue with the money-domain track:

| Order | File | Core lesson | Guide |
|---|---|---|---|
| 6 | `backend/app/money/normalize.py` | Canonical transactions, account identity, fingerprints | [Guide 06](06-TRANSACTION-NORMALIZATION.md) |
| 7 | `backend/app/money/reconcile.py` | Incremental ledgers and pending-to-posted replacement | [Guide 07](07-LEDGER-RECONCILIATION.md) |
| 8 | `backend/app/money/spending.py` | Transfer-safe spending and income classification | [Guide 08](08-SPENDING-CLASSIFICATION.md) |
| 9 | `backend/app/money/recurring.py` | Cadence detection, confidence, and false positives | [Guide 09](09-RECURRING-TRANSACTIONS.md) |

Use [Guide 05](05-MONEY-ROADMAP.md) for the complete money-domain architecture. Do not start these while one of the original five files is still your active exercise.

### Optional capstone files

Write these only after the five required files work:

- `backend/app/impact/rules.py` — user-configurable alert predicates.
- `backend/app/portfolio/performance.py` — time-weighted return calculations.
- `backend/app/events/classifier.py` — a richer deterministic event taxonomy.

Do not start with the optional files.

---

## 3. Files the agent writes completely

### Backend foundation

- `backend/app/main.py`
- `backend/app/config.py`
- `backend/app/logging.py`
- `backend/app/deps.py`
- `backend/app/api/**`
- `backend/app/db/**`
- `backend/alembic/**`
- `backend/app/repositories/**`

### External integrations

- `backend/app/providers/schwab/**`
- `backend/app/providers/openbb/**`
- `backend/app/providers/sec/**`
- `backend/app/providers/plaid/**`
- the future native Apple FinanceKit adapter
- OAuth routes, token exchange, token refresh, and encrypted token storage
- provider rate limiting, HTTP retries, and response fixtures

### Operations

- Dockerfiles and local Compose configuration
- CI, linting, formatting, and type-check configuration
- health endpoints, metrics, tracing, and structured logging
- push notification, email, and mobile device-token adapters

### Frontend

The agent owns the entire Expo/React Native application:

- iOS, Android, and web configuration;
- Expo Router navigation;
- authentication screens;
- portfolio dashboard;
- holdings and account screens;
- company detail views;
- impact feed;
- alert settings;
- charts, loading states, empty states, and responsive behavior;
- money overview, transactions, recurring-charge review, and bank connection screens;
- TanStack Query hooks and typed API client.

You should review frontend API contracts, but you do not need to hand-write frontend code.

---

## 4. Files you read but do not rewrite

These are important to understand, but implementing them by hand gives a poor learning-to-time ratio.

| Area | What to understand |
|---|---|
| Schwab OAuth | Authorization-code flow, server-side token exchange, refresh, encryption, revocation |
| SQLAlchemy models | Which tables own durable state and which records are derived |
| Alembic migrations | Why schema changes are ordered and reversible |
| OpenBB provider | OpenBB standardizes providers; it does not guarantee identical entitlements or freshness |
| API routes | Routes validate/authorize and delegate; they do not contain business logic |
| Notification adapters | Delivery is separate from deciding whether an alert should exist |
| Expo auth callback | Browser-based OAuth returns through a universal link; tokens stay server-side |

---

## 5. Planned repository structure

```text
Posted/
  README.md
  guides/
    00-LEARNING-ROADMAP.md
    01-PORTFOLIO-RECONCILIATION.md
    02-EVENT-PIPELINE.md
    03-IMPACT-ENGINE.md
    04-SYNC-ORCHESTRATOR.md
    05-MONEY-ROADMAP.md
    06-TRANSACTION-NORMALIZATION.md
    07-LEDGER-RECONCILIATION.md
    08-SPENDING-CLASSIFICATION.md
    09-RECURRING-TRANSACTIONS.md
    10-BANKING-CONNECTORS.md
    POSTED-LEARNING-COMPANION.md

  apps/
    client/                         # AGENT WRITES: Expo universal app
      app/
      components/
      features/
      lib/
      stores/

  backend/
    pyproject.toml
    alembic.ini
    alembic/
    app/
      main.py
      config.py
      api/
      db/
      repositories/

      domain/
        models.py                   # AGENT WRITES: canonical types/contracts
        enums.py
        errors.py

      providers/
        schwab/                     # AGENT WRITES
        openbb/                     # AGENT WRITES
        sec/                        # AGENT WRITES
        plaid/                      # AGENT WRITES

      portfolio/
        reconcile.py                # YOU WRITE
        service.py                  # AGENT WRITES: calls your function
        performance.py              # FUTURE OPTIONAL EXERCISE

      events/
        normalize.py                # YOU WRITE
        dedupe.py                   # YOU WRITE
        service.py                  # AGENT WRITES

      impact/
        scoring.py                  # YOU WRITE
        rules.py                    # FUTURE OPTIONAL EXERCISE
        service.py                  # AGENT WRITES

      sync/
        ports.py                    # AGENT WRITES: Protocol contracts
        orchestrator.py             # YOU WRITE
        jobs.py                     # AGENT WRITES: scheduler entrypoints

      notifications/                # AGENT WRITES
      money/
        normalize.py                # YOU WRITE, after the original five
        reconcile.py                # YOU WRITE
        spending.py                 # YOU WRITE
        recurring.py                # YOU WRITE
      tests/
        fixtures/                   # AGENT WRITES
        test_portfolio_reconcile.py # AGENT WRITES before your implementation
        test_event_normalize.py     # AGENT WRITES before your implementation
        test_event_dedupe.py        # AGENT WRITES before your implementation
        test_impact_scoring.py      # AGENT WRITES before your implementation
        test_sync_orchestrator.py   # AGENT WRITES before your implementation
```

---

## 6. The build protocol

### How to use a guide when you are new to the topic

Do not read a guide once and then attempt the whole file from memory. Use this loop:

```text
read one implementation pass
-> run one named test
-> trace one fixture through your variables
-> make that test pass
-> explain why it passes
-> move to the next behavior
```

Every guide should distinguish between:

- the **starter tests**, which are already in the repository and define your immediate target;
- **hardening tests**, which the agent adds after the starter behavior works;
- **production concerns**, which belong to later infrastructure and should not distract you during the pure-function exercise.

If a section still feels abstract, stop and ask about the first failing test by name. Do not ask for the entire implementation. A useful request is: “Trace the inputs and expected output of `test_new_position_is_opened`, but let me write the code.”

Each learning milestone follows the same sequence.

### Step A — Agent creates the executable specification

The agent creates:

- domain types used by the module;
- a file containing the public signature, docstring, and `NotImplementedError`;
- any generic helper explicitly labeled **provided** by the focused guide;
- deterministic fixtures with no live external calls;
- failing unit tests describing required behavior;
- supporting repositories/adapters needed to run the tests.

The agent must **not** fill in the learner-owned public workflow or business-rule helpers.

### Step B — You implement one module

You read the relevant guide, implement the smallest passing version, and run only that module's tests while iterating.

### Step C — Explain it before moving on

Before the next milestone, you should be able to answer:

1. What are the input and output contracts?
2. Which invariants does the module enforce?
3. Is it deterministic and idempotent?
4. What can fail, and where is the failure handled?
5. Why does this logic belong in the domain layer rather than an API route or provider adapter?

### Step D — Agent reviews without replacing

Ask the agent to review your implementation. It may:

- identify correctness problems;
- suggest smaller functions or clearer names;
- add missing tests;
- explain a failing test.

It must not replace the whole file unless you explicitly request a reference implementation.

---

## 7. Milestones

### Milestone 0 — Contracts and local foundation

**Agent work:** scaffold FastAPI, PostgreSQL, configuration, canonical domain models, fake provider adapters, and test infrastructure.

**Acceptance criteria:** the API boots, tests run, and no real credentials are needed.

### Milestone 1 — Portfolio truth

**Your work:** `portfolio/reconcile.py`.

**Outcome:** repeated Schwab snapshots produce stable canonical positions and explicit opened/changed/closed deltas.

### Milestone 2 — Event truth

**Your work:** `events/normalize.py` and `events/dedupe.py`.

**Outcome:** OpenBB, SEC, and provider-specific records become one auditable stream without duplicate alerts.

### Milestone 3 — Relevance

**Your work:** `impact/scoring.py`.

**Outcome:** every event receives an explainable portfolio-specific score and component breakdown.

### Milestone 4 — Reliability

**Your work:** `sync/orchestrator.py`.

**Outcome:** one safe, observable pipeline coordinates providers and persistence without corrupting state during retries or partial failures.

### Milestone 5 — Product surface

**Agent work:** full Expo frontend, API routes, notification delivery, deployments, and polish.

**Your work:** verify that the UI explanations correspond to the component scores your backend produced.

### Milestone 6 — Money truth

**Your work:** normalize and reconcile provider transactions.

**Outcome:** Plaid and future FinanceKit data produce one durable, replay-safe ledger.

### Milestone 7 — Spending intelligence

**Your work:** classify weekly spending and detect recurring streams.

**Outcome:** card payments and transfers are not double counted, and every recurring inference is explainable.

---

## 8. Scope guardrails

For the first working version:

- Support US-listed stocks and ETFs.
- Treat options, bonds, mutual funds, and short positions as explicitly unsupported or quarantined records.
- Use read-only Schwab access.
- Use SEC filings as the authoritative regulatory source.
- Use OpenBB as the standardized research-data layer.
- Start with deterministic scoring, not an LLM judge.
- Never place external provider calls inside a database transaction.
- Never use binary floating-point for money or quantities that require exact decimal handling.
- Never send Schwab access or refresh tokens to the Expo client.
- Never send Plaid access tokens or provider secrets to the Expo client.
- Treat Apple FinanceKit as a separately entitled on-device source, not a universal Apple Pay ledger.

---

## 9. Definition of learning complete

You have completed the learning portion when you can draw this from memory and explain every boundary:

```text
SchwabAdapter ----\
                   -> SyncOrchestrator -> Repositories -> PostgreSQL
OpenBBAdapter ----/          |
                              -> Reconcile positions
                              -> Normalize/dedupe events
                              -> Score portfolio impact
                              -> Create alert decisions
```

You do not need to memorize FastAPI, SQLAlchemy, or Expo syntax. You do need to understand why the domain logic is pure, why adapters are replaceable, why synchronization is idempotent, and why every score is explainable.
