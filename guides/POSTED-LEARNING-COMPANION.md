# Posted — Learning Companion

[← Sync orchestrator](04-SYNC-ORCHESTRATOR.md) | [Roadmap](00-LEARNING-ROADMAP.md)

This is the conceptual companion to the four implementation exercises. Read the relevant section before each exercise, then return after the tests pass and make sure you can explain the design in your own words.

---

## 1. The architecture in one sentence

> Posted converts unreliable external observations into canonical portfolio and event state, then applies a deterministic, explainable impact policy before creating durable alerts.

That sentence identifies four layers:

```text
providers        observations from Schwab, OpenBB, SEC, news vendors
domain           canonical portfolio, event, and impact logic
persistence      PostgreSQL records, snapshots, cursors, assessments, alerts
delivery         FastAPI responses, Expo UI, push notifications, email
```

The provider and delivery layers change frequently. The domain rules should remain stable and independently testable.

---

## 2. Why the domain files are pure

A pure function returns the same output for the same inputs and causes no external side effects.

Posted's learning modules receive clocks, policies, prior state, and resolved identities explicitly. They do not call APIs or write databases. This produces several benefits:

- tests are fast and deterministic;
- provider failures cannot occur halfway through a calculation;
- the same logic can run in an API request, worker, replay job, or command-line tool;
- business decisions are visible rather than buried in framework code;
- policy versions allow historical scores to be reproduced.

The orchestrator is intentionally not pure because coordinating side effects is its purpose. Its dependencies are ports so the side effects can still be replaced by fakes in tests.

---

## 3. Ports and adapters without jargon

The domain wants capabilities:

```text
"fetch a complete brokerage snapshot"
"load previous positions"
"store canonical events"
```

It should not care whether those capabilities are implemented by Schwab, PostgreSQL, a JSON fixture, or a future second brokerage.

A **port** is the interface the application needs. An **adapter** connects a specific technology to that port.

```text
                   BrokeragePort
                         ^
                         |
             SchwabAdapter / FakeBrokerage

EventProviderPort <--- OpenBBAdapter / SecAdapter / FakeEventProvider

PortfolioRepository <--- SqlAlchemyPortfolioRepository / InMemoryRepository
```

This is why `sync/orchestrator.py` imports protocols rather than concrete clients.

An interview-quality explanation:

> I kept vendor schemas at an anti-corruption boundary. Adapters map them to provider-neutral observations, pure domain functions enforce invariants, and an orchestrator persists results through repository ports. This made every material business rule testable without a brokerage account or network.

---

## 4. Portfolio state is observed, not commanded

Posted does not execute trades. It periodically observes the brokerage and derives a local view.

This is a snapshot-based system:

```text
snapshot N-1 + snapshot N -> position deltas
```

Important implications:

- the brokerage remains the source of truth for holdings;
- Posted stores historical snapshots for performance and audit;
- missing data cannot automatically mean a closed position unless the snapshot is known to be complete;
- price movement changes market value but not position quantity;
- processing the same snapshot twice should create no new economic change.

### Identity is more important than display labels

Tickers are useful labels, not perfect durable identities. Symbols can change, be reused, or differ across security types. Posted resolves provider identifiers to an internal `security_id` and keys account positions by `(account_id, security_id)`.

This is the same architectural lesson as using a customer ID instead of a customer's email as a primary key.

### Why `Decimal` matters

Binary floating-point cannot represent many decimal fractions exactly. A quantity or price like `0.1` may accumulate small artifacts. Use `Decimal` for money, quantities, average prices, and portfolio weights that come from accounting data. Floating-point is acceptable for heuristic scores after inputs have been normalized.

---

## 5. Event ingestion is an entity-resolution problem

A feed is not simply a list returned by an API. Providers report overlapping views of real-world events.

```text
SEC 8-K ------------\
company release -----+--> one canonical earnings event
wire story ----------/
```

The architecture separates:

1. **Source record:** exactly what one provider said.
2. **Canonical event:** Posted's best representation of the underlying development.
3. **Source links:** retained evidence showing how the canonical event was formed.

### Strong identity beats fuzzy similarity

Use accession numbers, provider story IDs, and canonical URLs before headline similarity. Fuzzy matching is a last conservative step because similar financial headlines are common.

### Preserve evidence

Merging must attach sources, not overwrite them. If dedupe policy changes later, the pipeline can replay source records and produce a new canonical result.

### Why false merges are dangerous

If two separate guidance changes are incorrectly merged, Posted may hide the later and more important change. Showing an occasional duplicate is annoying; erasing an event can be materially misleading. Bias toward conservative merges.

---

## 6. OpenBB's role

OpenBB is the standardized research-data layer. Its Python package exposes common models and routes across data providers. It can run inside Posted's backend initially; a separate REST service is an optional scaling boundary later.

Use OpenBB for capabilities such as:

- company news;
- profiles and fundamentals;
- earnings and corporate-action calendars;
- estimates and analyst data;
- SEC-related discovery;
- ETF holdings and eventual indirect exposure.

Do not confuse OpenBB with a single underlying source. Coverage, freshness, entitlements, and licensing still come from the selected provider. Provider identity must remain attached to every source record.

Useful official references:

- [OpenBB Python introduction](https://docs.openbb.co/odp/python)
- [Company news reference](https://docs.openbb.co/odp/python/reference/news/company)
- [SEC filings discovery](https://docs.openbb.co/odp/python/reference/equity/discovery/filings)
- [OpenBB REST API](https://docs.openbb.co/odp/python/quickstart/rest_api)

---

## 7. The impact score is a ranking policy

Posted's score is not a prediction of return. It ranks the user's attention.

The distinction matters:

```text
wrong: "This event will make the stock fall."
right: "This is a recent guidance change affecting 8% of the portfolio,
        reported in an authoritative filing, so it deserves attention."
```

### Why components remain separate

A score of 78 is meaningless without context. Components let the system explain and debug it:

```text
materiality    85
exposure       72
recency        96
novelty        60
confidence     98
final          80.4
```

They also support later evaluation. If users consistently dismiss high-scoring low-novelty alerts, the novelty policy can change without rewriting ingestion.

### Policy versioning

Store the component inputs, output, and policy version. When weights change, do not pretend old scores were produced by the new policy. Versioning makes alerts reproducible and allows A/B or offline evaluation.

### Deterministic before AI

An LLM may summarize sources into clear prose, but it should not be the sole materiality judge in the first version. A deterministic baseline is:

- testable;
- reproducible;
- fast;
- cheap;
- explainable;
- measurable against later human feedback.

---

## 8. Direct and indirect exposure

Direct exposure is straightforward:

```text
position market value / total portfolio market value
```

Indirect exposure appears through funds:

```text
ETF portfolio weight × company's weight inside the ETF
```

Example:

```text
15% of portfolio in ETF
ETF has 6% weight in Company X
indirect Company X exposure = 15% × 6% = 0.9%
```

Avoid double counting:

- keep every exposure path;
- deduplicate equivalent paths;
- separate direct and indirect weights;
- record the holdings date used for ETF constituents;
- recognize that ETF holdings may be delayed.

ETF look-through is a later feature, but the v1 scoring contract anticipates it.

---

## 9. Reliability: at-least-once work, exactly-once effects

Schedulers and networks retry. A worker can complete a database write and crash before acknowledging success. The job will run again.

Trying to guarantee that code executes only once is usually unrealistic. Instead design for:

> Work may run more than once, but durable economic effects appear once.

Posted achieves this through layers:

- command idempotency keys;
- per-connection locks;
- pure snapshot reconciliation;
- event fingerprints and strong identifiers;
- database uniqueness constraints;
- per-provider cursors;
- alert uniqueness keys;
- durable notification delivery records.

### Lock versus idempotency

A lock prevents overlap at one moment. An idempotency key recognizes a repeated logical command over time. You need both.

### Cursor rule

Never advance a provider cursor merely because fetch succeeded. Advance it in the same transaction that durably stores the batch. Otherwise a crash can permanently skip events.

---

## 10. Transaction boundaries

A transaction protects a small, coherent durable state change. It should not wrap slow, failure-prone network calls.

```text
GOOD
fetch provider -> normalize -> begin transaction -> persist -> cursor -> commit

BAD
begin transaction -> fetch provider -> retry -> normalize -> persist -> commit
```

The good version uses fewer database connections, holds locks for less time, and reduces rollback scope.

The orchestrator may commit between stages. A portfolio snapshot can remain committed even if an optional news source later fails. The sync-run state records that partial progress explicitly.

---

## 11. Alerts and the outbox idea

Creating an alert and delivering a push notification are different responsibilities.

```text
impact assessment
    -> durable alert decision
        -> delivery job
            -> push/email/in-app receipt
```

If push delivery happens before the alert record commits, the user can receive a notification that Posted cannot later explain. If the database commits but push fails, a delivery worker can retry safely.

The general pattern is to persist an event/outbox record in the same transaction as the business decision, then deliver asynchronously.

---

## 12. Security model you must understand

The agent can implement the code, but you must be able to audit the design.

### Brokerage access

- use the Schwab authorization-code flow;
- request the minimum read-only permissions;
- exchange codes only on the backend;
- encrypt refresh tokens with a managed key;
- never store Schwab passwords;
- never send Schwab tokens to Expo;
- support disconnect/revocation and deletion;
- redact account numbers in logs and UI.

### App authentication

- native and web clients receive Posted session credentials, not provider tokens;
- authorize every account/portfolio request by user ownership;
- use secure device storage for mobile session material;
- configure universal links for OAuth returns;
- protect web sessions against cross-site attacks according to the chosen session strategy.

Expo Router supports universal routes across native and web, including deep-link flows. See the [Expo Router introduction](https://docs.expo.dev/router/introduction/) and [Expo linking overview](https://docs.expo.dev/linking/overview/).

### Data minimization

Store what the product needs. Avoid retaining complete raw brokerage responses indefinitely. If raw payloads are temporarily retained for debugging, encrypt them, restrict access, and establish deletion windows.

---

## 13. Frontend architecture you should recognize

The agent owns the Expo frontend, but it should follow feature boundaries that mirror the backend:

```text
apps/client/
  app/                         Expo Router screens
  features/
    auth/
    portfolio/
    holdings/
    feed/
    events/
    alerts/
    settings/
  components/                 reusable visual components
  lib/api/                    typed client and schemas
  lib/query/                  TanStack Query configuration
  stores/                     local-only state
```

Server state belongs in TanStack Query. Local interface state belongs in component state or a small Zustand store. Do not duplicate the portfolio into a global client store.

The web layout may use platform-specific components for dense tables and charts while sharing domain hooks, navigation, API schemas, colors, and most components with native.

The UI must show:

- when portfolio data was last synchronized;
- whether an event is source-confirmed or inferred;
- why an impact score was assigned;
- direct and indirect exposure separately;
- links to primary source evidence;
- that summaries are informational and not investment advice.

---

## 14. How to work with the coding agent

Use this pattern for each milestone.

### Scaffold prompt

```text
Read guides/00-LEARNING-ROADMAP.md and the guide for the current milestone.
Scaffold the agent-owned types, ports, fixtures, and tests. In the user-owned
file, add the public signature, docstring, NotImplementedError, and only the
generic helpers that the focused guide explicitly labels as provided. Do not
implement the learner-owned workflow or business-rule helpers. Run the tests
and confirm they fail only because the learner-owned function is unfinished.
```

### Review prompt

```text
Review my implementation against the relevant guide and tests. Do not rewrite
the whole file. Identify invariant violations, correctness bugs, unclear names,
and missing edge-case tests. Explain each issue and let me make the correction.
```

### Hint prompt

```text
Give me one conceptual hint for the failing test without providing finished
code. Point me to the invariant or algorithm step I am violating.
```

### Reference implementation prompt

Use only after you have passed the tests and can explain your own version:

```text
Create a separate reference file or diff showing an idiomatic alternative.
Do not replace my implementation. Explain the tradeoffs between the two.
```

---

## 15. Suggested study rhythm

For each core module:

1. Read its guide once without coding.
2. Draw its input/output boundary on paper.
3. Write the invariants as comments.
4. Run the failing tests.
5. Implement the simplest happy path.
6. Add one edge case at a time.
7. Refactor only after all behavior passes.
8. Explain the file aloud in under three minutes.
9. Ask the agent for review, then make the corrections yourself.
10. Commit the milestone independently.

Do not delete an agent solution and copy it back from memory. The agent should never implement the core file before your attempt. The tests and guide are the specification.

---

## 16. Questions you should be able to answer

### Architecture

**Why Python instead of Go or Rust?**

The dominant work is provider I/O and data transformation, while OpenBB is Python-native. Python minimizes service boundaries and development time. Go or Rust can be introduced later for a measured CPU or throughput bottleneck without changing the domain contracts.

**Why a modular monolith?**

The product is early and benefits from one deployment and one transaction boundary. Modules enforce logical separation. Split services only when independent scaling, ownership, or reliability needs justify operational complexity.

**Why PostgreSQL as the source of truth?**

It provides transactions, constraints, historical records, and flexible relational queries for accounts, positions, source evidence, assessments, and alerts. Redis caches and queues work; they do not own durable financial state.

### Portfolio

**What makes reconciliation idempotent?**

Stable identity, canonical grouping, deterministic output, comparison against current stored state, and unique snapshot/run identifiers ensure the same observation creates no second economic change.

**Why retain position snapshots?**

They support audit, historical portfolio value, performance calculations, and the ability to explain which exposure an alert used.

### Events

**Why not just display OpenBB results directly?**

Providers overlap and change. Canonical events prevent duplicate alerts, preserve source evidence, and let the rest of the application use one stable vocabulary.

**How do you prevent bad fuzzy merges?**

Use strong IDs first, restrict candidates by company and compatible type/time, block on identifier conflicts, keep conservative thresholds, and preserve merge reasons.

### Impact

**Why not let an LLM rank everything?**

A deterministic baseline is reproducible, testable, cheap, and explainable. LLMs can summarize evidence, while user feedback later provides labels for improving ranking.

**Is the score financial advice?**

No. It ranks attention based on event type, exposure, source/match confidence, recency, and novelty. It makes no claim about future returns or a suitable trade.

### Reliability

**What happens if a worker crashes after commit?**

The job may retry, but idempotency keys and database constraints recognize previously committed effects. Provider cursors and alert uniqueness prevent skipped or duplicated downstream work.

**Why create the alert before sending push?**

Durable business state must exist before an unreliable delivery attempt. Delivery can retry independently and always link back to an explainable assessment.

---

## 17. Evaluation plan after the MVP

Do not tune impact weights from intuition forever. Record privacy-conscious feedback:

- opened alert;
- dismissed alert;
- muted company/event type;
- marked useful/not useful;
- time to open;
- duplicate report;
- incorrect company match report.

Build an offline dataset containing component scores and outcomes. Evaluate:

- precision of urgent/important alerts;
- duplicate-event rate;
- missed event reports;
- alert latency;
- company-link precision;
- calibration by score bucket;
- per-provider quality.

Only then adjust policy weights or train a ranker. Retain the deterministic policy as a fallback and explanation layer.

---

## 18. Definition of mastery

You understand Posted's architecture when you can explain this chain without framework vocabulary:

```text
1. A brokerage snapshot is an observation, not automatically trusted state.
2. Reconciliation creates stable positions and explicit deltas.
3. Provider records are normalized and conservatively merged into events.
4. Events are scored against the exposure snapshot using a versioned policy.
5. Alert decisions are persisted once and delivery retries independently.
6. An orchestrator coordinates side effects while pure modules remain testable.
```

If you can implement the original five user-owned files, pass their failure-oriented tests, and defend those six statements, you have learned the mission-critical portfolio architecture. Continue with [the money-domain roadmap](05-MONEY-ROADMAP.md) for transaction truth, ledger reconciliation, transfer-safe spending, and recurring-charge detection; completing all four gives you the same architectural understanding for personal finance.
