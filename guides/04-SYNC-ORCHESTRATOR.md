# Guide 04 — Synchronization Orchestrator

[← Impact engine](03-IMPACT-ENGINE.md) | [Learning companion →](POSTED-LEARNING-COMPANION.md)

**You write:** `backend/app/sync/orchestrator.py`

**What exists when you finish:** one observable, retry-safe use case coordinates Schwab synchronization, event ingestion, persistence, scoring, and alert creation without mixing provider code with domain logic.

## Before you write code

This is the capstone. Do not start it while any of the first four files still has failing tests. Unlike the pure-function exercises, orchestration needs a larger fake-port test harness whose repository methods should match the implementation available when you reach this milestone.

The repository currently contains only a red completion gate:

```bash
cd backend
uv run pytest -m user_owned app/tests/user_owned/test_sync_orchestrator.py -q
```

### Important: the capstone is not implementable from the current scaffold yet

At the moment, `sync/ports.py` defines transaction entry/exit, brokerage fetching, event
fetching, locking, and a clock. It does **not** define repository methods for:

- checking connection ownership;
- looking up an idempotent prior result;
- creating or advancing a sync-run record;
- loading and replacing stored positions;
- persisting reconciliation rejections and deltas;
- loading provider cursors;
- persisting events and advancing cursors;
- loading exposures and persisting assessments;
- creating unique durable alerts.

The current test only checks that `run()` no longer contains `raise NotImplementedError`. That
is a milestone marker, not an executable behavioral specification. Do not replace the raise
with a dummy result merely to turn that test green.

Before you implement this guide, the agent must add the fake repositories and their Protocol
contracts to `sync/ports.py`, then replace the completion-gate test with behavior tests. Those
method signatures become the source of truth for the exact calls in `run()`. This is support
scaffolding, not part of the orchestration lesson.

When Guides 01–03 are green, ask the agent to expand `test_sync_orchestrator.py` with the fake clock, lock, brokerage, event-provider, and unit-of-work cases listed in section 10. The agent should write those fakes and tests; you should still write only `sync/orchestrator.py`.

Begin with a sequential happy path, not concurrency. On paper, draw exactly three kinds of region:

```text
external fetch (no transaction)
-> short database transaction and commit
-> external fetch (no transaction)
```

Then add idempotency and the connection lock before optional-provider concurrency. If you cannot state whether a line is an external call, domain calculation, or durable write, the orchestrator is trying to do too much itself.

This is the capstone because it makes the previous pure functions part of a reliable system.

---

## 1. What orchestration is

An orchestrator coordinates components; it should not reimplement them.

It answers:

- What happens first?
- Which external calls may run concurrently?
- Where are transaction boundaries?
- What is retried?
- What happens when one provider fails?
- How is a run resumed or safely repeated?
- What gets logged and persisted?

It should read like a use-case narrative, not like HTTP or SQL code.

---

## 2. Ports and adapters

The agent writes `sync/ports.py` using `Protocol` definitions. Your orchestrator depends only on these ports.

Conceptual ports:

```python
class BrokeragePort(Protocol):
    async def fetch_complete_snapshot(self, connection_id: UUID) -> BrokerageSnapshot: ...

class EventProviderPort(Protocol):
    async def fetch_events(
        self,
        securities: Sequence[TrackedSecurity],
        cursor: EventCursor | None,
    ) -> ProviderEventBatch: ...

class UnitOfWork(Protocol):
    portfolios: PortfolioRepository
    events: EventRepository
    assessments: AssessmentRepository
    alerts: AlertRepository
    sync_runs: SyncRunRepository

    async def __aenter__(self) -> "UnitOfWork": ...
    async def __aexit__(self, *args: object) -> None: ...
    async def commit(self) -> None: ...
    async def rollback(self) -> None: ...

class DistributedLock(Protocol):
    async def acquire(self, key: str, ttl: timedelta) -> AsyncContextManager[LockLease]: ...

class Clock(Protocol):
    def now(self) -> datetime: ...
```

There may also be ports for token refresh, telemetry, and notification dispatch. Notification **delivery** should happen after durable alert creation, not inside your scoring transaction.

---

## 3. Your public use case

```python
class PortfolioSyncOrchestrator:
    async def run(
        self,
        command: SyncPortfolioCommand,
    ) -> SyncPortfolioResult:
        """Synchronize one brokerage connection and derive portfolio intelligence."""
```

Dependencies are injected through `__init__`. Do not construct Schwab clients, OpenBB clients, repositories, or Redis connections inside `run()`.

The mechanical lock-key helper has already been implemented in `orchestrator.py`:

```python
_connection_lock_key(connection_id) -> "portfolio-sync:{connection_id}"
```

Read and use it; do not spend exercise time rewriting string formatting.

Suggested command fields:

```python
@dataclass(frozen=True)
class SyncPortfolioCommand:
    user_id: UUID
    connection_id: UUID
    requested_by: SyncTrigger
    idempotency_key: str
    force_full_event_scan: bool = False
```

Suggested result fields:

```python
@dataclass(frozen=True)
class SyncPortfolioResult:
    sync_run_id: UUID
    status: SyncRunStatus
    positions_seen: int
    positions_changed: int
    events_fetched: int
    events_created: int
    events_merged: int
    assessments_created: int
    alerts_created: int
    provider_warnings: tuple[ProviderWarning, ...]
```

---

## 4. The end-to-end state machine

Design `run()` around explicit stages:

```text
REQUESTED
  -> LOCKED
  -> BROKERAGE_FETCHED
  -> PORTFOLIO_PERSISTED
  -> EVENTS_FETCHED
  -> EVENTS_PERSISTED
  -> ASSESSMENTS_PERSISTED
  -> COMPLETED

Any stage may transition to FAILED.
Optional providers may produce COMPLETED_WITH_WARNINGS.
```

Persist stage transitions so operations can answer where a run stopped.

The first implementation can restart the whole idempotent run rather than resume mid-stage. Explicit stages still give observability and create a future resume path.

---

## 5. Required orchestration sequence

### 5.1 Validate ownership and idempotency

Before external calls:

- verify that the connection belongs to the user;
- check for a completed run with the same idempotency key;
- return the prior result if it exists;
- reject reuse of the same key with materially different command parameters.

### 5.2 Acquire a connection-scoped lock

Use a lock key such as:

```text
portfolio-sync:{connection_id}
```

Only one portfolio sync per connection may run at once. The lock needs a TTL and, for long runs, lease renewal. A lock prevents concurrency; idempotency handles retries. They solve different problems.

### 5.3 Create the durable sync-run record

Persist `REQUESTED/LOCKED`, trigger type, timestamps, policy versions, and idempotency key.

### 5.4 Fetch the brokerage snapshot outside a transaction

Call the brokerage port. The adapter owns token refresh, HTTP timeouts, provider retry policy, and response validation.

Do not hold a database transaction open while waiting for Schwab.

If the adapter cannot prove the snapshot is complete, do not infer closed positions.

### 5.5 Reconcile and persist portfolio state atomically

In one short unit of work:

1. load previous positions;
2. call your pure `reconcile_positions()`;
3. persist the current snapshot;
4. persist position deltas and rejections;
5. update the sync stage;
6. commit.

If persistence fails, roll back the entire portfolio stage.

### 5.6 Build the tracked-security universe

Use current supported holdings. Preserve watchlist support as a separate source of tracked securities, but it can be empty in v1.

Do not request company news for cash-equivalent bookkeeping positions or unsupported instruments.

### 5.7 Fetch event providers with bounded concurrency

SEC and OpenBB-backed provider requests may run concurrently, but concurrency must be bounded according to provider limits.

Use one cursor per provider. A successful provider advances only its own cursor after its events are durably stored.

Classify providers:

- **required:** failure makes the event stage fail;
- **optional:** failure becomes a warning and the run may complete with warnings.

For the initial product, brokerage synchronization is required. The exact required/optional policy for news providers should be configuration.

### 5.8 Normalize and deduplicate before persistence

For each fetched batch:

1. map provider payloads to `ProviderEventEnvelope` in the adapter;
2. call your `normalize_event()`;
3. combine with relevant recent stored events;
4. call `deduplicate_events()`;
5. preserve rejections and merge reasons.

### 5.9 Upsert events and advance cursors atomically

In one short unit of work:

- insert new canonical events;
- attach new source evidence to existing events;
- persist dedupe clusters/reasons;
- update only successful provider cursors;
- update sync stage;
- commit.

An event needs a durable uniqueness constraint for strong identities so concurrent or retried inserts cannot duplicate it even if application logic is wrong.

### 5.10 Score affected events

Load current portfolio exposures and the versioned impact policy. Call your pure `assess_impact()` for new or materially updated events.

Persist assessments with:

- complete components;
- policy version;
- exposure snapshot reference;
- affected securities;
- reasons;
- assessed timestamp.

Never overwrite historical assessments when a policy changes. Create a new versioned assessment if rescoring.

### 5.11 Create alerts atomically, deliver later

Evaluate alert eligibility and user rules, then persist alert records using a uniqueness key such as:

```text
(user_id, canonical_event_id, alert_rule_id, assessment_policy_version)
```

Commit alerts before sending push or email. A separate delivery job reads durable undelivered alerts. This is an outbox-style boundary: a notification failure must not erase the decision that an alert exists.

### 5.12 Complete the run

Persist counts, durations, warnings, final status, and completion time. Release the lock through the context manager even on failure.

---

## 6. Transaction boundary rule

Use this sentence as a hard rule:

> No network request occurs while a database transaction is open.

Good:

```text
fetch external data
-> open transaction
-> calculate/persist
-> commit
```

Bad:

```text
open transaction
-> fetch Schwab
-> wait/retry
-> fetch OpenBB
-> finally commit
```

The bad version holds locks and connections across unpredictable latency and greatly increases contention and rollback scope.

---

## 7. Failure policy

### Brokerage failure

- mark the run failed at the brokerage stage;
- do not alter current positions;
- do not mark missing positions as closed;
- retain the previous successful snapshot.

### Partial account snapshot

- quarantine the incomplete batch;
- retain prior portfolio state for affected accounts;
- record a provider warning/error with safe metadata.

### One optional event provider fails

- retain successful provider data;
- do not advance the failed provider's cursor;
- complete with warnings if policy allows.

### Persistence failure

- roll back the current stage;
- retain prior committed stages;
- a retry with the same idempotency key resumes or safely repeats according to the defined policy.

### Scoring failure for one malformed event

- do not discard other assessments;
- quarantine the event assessment with an error reason;
- choose whether the run completes with warnings according to policy.

### Lock contention

- return an `already_running` result or typed retryable error;
- do not start a second synchronization.

Never log provider access tokens or complete raw account payloads.

---

## 8. Idempotency layers

Reliable systems use more than one defense:

1. **Command key:** repeated request returns the existing run.
2. **Connection lock:** concurrent runs do not overlap.
3. **Pure reconciliation:** repeated snapshot produces no false deltas.
4. **Event strong IDs/fingerprints:** repeated ingestion maps to existing events.
5. **Database unique constraints:** races cannot create duplicate durable records.
6. **Alert uniqueness:** retries cannot notify the same rule/event assessment twice.
7. **Provider cursors:** only successfully persisted batches advance.

Be able to explain why a lock alone is not idempotency: a retry after the lock expires can still duplicate work.

---

## 9. Observability requirements

Every log line should include where applicable:

```text
sync_run_id
user_id (safe internal identifier)
connection_id
stage
provider
duration_ms
item_count
warning/error code
retryable
```

Do not include:

- access tokens;
- refresh tokens;
- Schwab credentials;
- full account numbers;
- unredacted raw provider responses.

Metrics worth recording:

- sync duration by stage;
- provider error rate and latency;
- events fetched/created/merged/rejected;
- assessments and alerts created;
- stale connection count;
- time from provider publication to Posted alert creation.

---

## 10. Concrete implementation map after the fake-port scaffold exists

This section uses explicit repository names so the control flow is understandable. When the
agent creates the fakes, their names and signatures should match this map or the guide should
be updated at the same time.

### 10.1 Dependencies supplied through `__init__`

Do not accept an unstructured `**dependencies` dictionary in the finished implementation.
Replace it with named parameters so a missing dependency fails immediately:

```python
PSEUDOCODE __init__(
    *,
    clock: Clock,
    lock: DistributedLock,
    brokerage: BrokeragePort,
    event_providers: Sequence[EventProviderPort],
    uow_factory: UnitOfWorkFactory,
    resolve_position_security: SecurityResolver,
    resolve_event_securities: EventSecurityResolver,
    event_id_factory: Callable[[], UUID],
    dedupe_policy: DedupePolicy,
    impact_policy: ImpactPolicy,
    lock_ttl: timedelta,
):
    assign each argument to a same-named private attribute
```

The factories, policies, adapters, repositories, fake clock, and fake lock are agent-written
support. Your job is to invoke them in the correct order and place transactions correctly.

### 10.2 Repository behavior the fake unit of work must expose

The expanded fake `UnitOfWork` needs these capabilities. Exact parameter types should use the
domain models rather than `object`:

```text
uow.connections.require_owner(user_id, connection_id)

uow.sync_runs.find_completed(user_id, idempotency_key)
uow.sync_runs.create(command, started_at) -> sync_run_id
uow.sync_runs.set_status(sync_run_id, status, changed_at)
uow.sync_runs.complete(result, completed_at)
uow.sync_runs.fail(sync_run_id, failed_stage, safe_message, failed_at)

uow.portfolios.list_previous(connection_id) -> tuple[StoredPosition, ...]
uow.portfolios.replace_current(connection_id, reconciliation.positions)
uow.portfolios.add_deltas(sync_run_id, reconciliation.deltas)
uow.portfolios.add_rejections(sync_run_id, reconciliation.rejected)
uow.portfolios.list_tracked(connection_id) -> tuple[TrackedSecurity, ...]

uow.events.get_cursor(provider_name)
uow.events.list_recent(tracked_securities, policy_window)
uow.events.persist(dedupe_result, rejected_events)
uow.events.advance_cursor(provider_name, next_cursor)

uow.assessments.load_exposures(connection_id, canonical_event)
uow.assessments.add(impact_assessment)

uow.alerts.create_if_absent(user_id, canonical_event, impact_assessment)
```

These are not methods you implement inside the orchestrator. They are calls the orchestrator
makes against injected fake/real repositories.

### 10.3 First milestone: ownership, idempotency, lock, and run record

Implement this before fetching anything:

```python
PSEUDOCODE run(command):
    IF command.idempotency_key stripped is empty:
        raise ValueError

    now = self._clock.now()

    async with self._uow_factory() as uow:
        await uow.connections.require_owner(command.user_id, command.connection_id)
        prior = await uow.sync_runs.find_completed(
            command.user_id,
            command.idempotency_key,
        )

        IF prior exists:
            return prior

    lock_key = _connection_lock_key(command.connection_id)

    async with self._lock.acquire(lock_key, self._lock_ttl):
        # Check idempotency again after waiting for the lock. Another run may
        # have completed while this command was waiting.
        async with self._uow_factory() as uow:
            prior = await uow.sync_runs.find_completed(
                command.user_id,
                command.idempotency_key,
            )
            IF prior exists:
                return prior

            sync_run_id = await uow.sync_runs.create(command, self._clock.now())
            await uow.sync_runs.set_status(sync_run_id, SyncRunStatus.LOCKED, now)
            await uow.commit()

        return await self._run_locked(command, sync_run_id)
```

The second idempotency check closes the race between the initial lookup and lock acquisition.
The lock context manager releases automatically if `_run_locked` raises.

### 10.4 Brokerage stage with a visible transaction boundary

```python
PSEUDOCODE _run_locked(command, sync_run_id):
    # EXTERNAL CALL: no UnitOfWork is open here.
    snapshot = await self._brokerage.fetch_complete_snapshot(command.connection_id)

    IF NOT snapshot.complete:
        record a failed/incomplete stage in a short UnitOfWork
        do not call reconcile_positions
        do not replace stored positions
        return or raise the typed incomplete-snapshot outcome defined by the tests

    # DATABASE TRANSACTION: no provider calls inside this block.
    async with self._uow_factory() as uow:
        previous = await uow.portfolios.list_previous(command.connection_id)

        reconciliation = reconcile_positions(
            observations=snapshot.observations,
            previous=previous,
            resolve_security=self._resolve_position_security,
        )

        await uow.portfolios.replace_current(
            command.connection_id,
            reconciliation.positions,
        )
        await uow.portfolios.add_deltas(sync_run_id, reconciliation.deltas)
        await uow.portfolios.add_rejections(sync_run_id, reconciliation.rejected)
        await uow.sync_runs.set_status(
            sync_run_id,
            SyncRunStatus.PORTFOLIO_PERSISTED,
            self._clock.now(),
        )
        tracked = await uow.portfolios.list_tracked(command.connection_id)
        await uow.commit()

    # Only after commit may event-provider calls begin.
    return await self._run_event_stages(
        command,
        sync_run_id,
        reconciliation,
        tracked,
    )
```

The fake call-order test should fail if `fetch_events` occurs before the portfolio commit.

### 10.5 Event fetching and provider failure handling

Start sequentially. Bounded concurrency is a later refactor that must preserve these rules:

```python
PSEUDOCODE:
    successful_batches = []
    warnings = []

    FOR provider IN self._event_providers:
        cursor = load that provider's cursor in a short read UnitOfWork

        TRY:
            # EXTERNAL CALL: no UnitOfWork remains open.
            batch = await provider.fetch_events(tracked, cursor)
        EXCEPT expected provider error AS error:
            IF provider.required:
                mark run failed in a short UnitOfWork
                raise

            warnings.append(ProviderWarning built from safe error fields)
            CONTINUE

        successful_batches.append((provider, batch))
```

Do not advance a cursor yet. Fetch success is not durability.

### 10.6 Normalize, deduplicate, persist, then advance cursors

```python
PSEUDOCODE:
    normalized = []
    rejected_events = []

    FOR provider, batch IN successful_batches:
        FOR envelope IN batch.events:
            result = normalize_event(
                envelope,
                resolve_securities=self._resolve_event_securities,
                event_id=self._event_id_factory(),
            )

            IF result is RejectedEvent:
                rejected_events.append(result)
            ELSE:
                normalized.append(result)

    load recent stored events in a short read UnitOfWork
    dedupe_result = deduplicate_events(
        normalized + relevant recent events,
        policy=self._dedupe_policy,
    )

    async with self._uow_factory() as uow:
        persistence = await uow.events.persist(dedupe_result, rejected_events)

        FOR provider, batch IN successful_batches:
            await uow.events.advance_cursor(provider.name, batch.next_cursor)

        set EVENTS_PERSISTED stage
        await uow.commit()
```

Cursor advancement shares the event-persistence commit. If the commit rolls back, cursors do
not advance.

### 10.7 Score, persist assessments, and create alerts

```python
PSEUDOCODE:
    assessments_created = 0
    alerts_created = 0

    async with self._uow_factory() as uow:
        FOR event IN persistence.new_or_changed_events:
            exposures = await uow.assessments.load_exposures(
                command.connection_id,
                event,
            )

            assessment_input = EventAssessmentInput(
                event=event,
                exposures=exposures,
                source_confidence=derive from persisted source evidence,
                entity_match_confidence=derive from persisted security matches,
                assessed_at=self._clock.now(),
                previous_related_event_at=load if available,
            )

            impact = assess_impact(assessment_input, policy=self._impact_policy)
            await uow.assessments.add(impact)
            assessments_created += 1

            IF impact.eligible_for_immediate_alert:
                created = await uow.alerts.create_if_absent(
                    command.user_id,
                    event,
                    impact,
                )
                alerts_created += integer form of created

        set ASSESSMENTS_PERSISTED stage
        await uow.commit()
```

The two “derive/load” lines require explicit support contracts in the expanded fake harness.
They must not be guessed from headlines inside the orchestrator.

### 10.8 Complete or fail exactly once

Build `SyncPortfolioResult` from counters accumulated during the stages. Its final status is
`COMPLETED_WITH_WARNINGS` when `warnings` is non-empty, otherwise `COMPLETED`. Persist that
same result before returning it.

Wrap the locked workflow in one outer `try/except` that:

1. re-raises cancellation after rollback/cleanup;
2. records a safe failed stage in a new short unit of work;
3. never logs tokens or raw provider payloads;
4. does not convert programming bugs into successful warning results.

Do not write one giant transaction around this pseudocode. Every displayed `async with
self._uow_factory()` is a separate short transaction, and every external provider call is
outside those blocks.

---

## 11. Tests the agent must write first

`test_sync_orchestrator.py` should use fake ports, a fake clock, and an in-memory fake unit of work. It must cover:

1. happy-path call order and completed counts;
2. duplicate idempotency key returns prior result without provider calls;
3. same key with different command is rejected;
4. lock contention starts no provider calls;
5. brokerage failure preserves prior positions;
6. incomplete brokerage snapshot never closes missing positions;
7. portfolio persistence failure rolls back that stage;
8. no event provider is called before portfolio commit;
9. tracked universe excludes unsupported assets;
10. successful providers may execute concurrently within the configured bound;
11. optional provider failure produces warning and preserves other results;
12. required provider failure marks the appropriate stage failed;
13. failed provider cursor does not advance;
14. successful provider cursor advances only after commit;
15. duplicate events produce one canonical durable event with multiple sources;
16. scoring receives the committed current exposure snapshot;
17. policy version is stored with assessments;
18. alert uniqueness prevents duplicates on retry;
19. notification delivery is not called inside the scoring transaction;
20. every failure releases the lock;
21. state transitions occur in legal order;
22. logs/telemetry never receive token values;
23. rerunning after a partial failure is safe;
24. cancellation triggers rollback/cleanup.

Add an integration test with PostgreSQL after the fake-based unit tests pass. External APIs remain faked.

---

## 12. Recommended implementation order

1. Implement command validation, idempotency lookup, and the lock.
2. Add sync-run stage persistence.
3. Implement brokerage fetch and atomic portfolio stage.
4. Add sequential event providers first.
5. Normalize/dedupe and persist events with cursors.
6. Add scoring and durable alerts.
7. Add optional-provider warnings.
8. Add bounded concurrency only after sequential behavior passes.
9. Finish telemetry and cancellation cleanup.

Correct sequential orchestration is easier to reason about than prematurely concurrent orchestration.

---

## 13. Acceptance criteria

- The orchestrator imports ports and domain functions, never concrete Schwab/OpenBB clients.
- No external request runs inside a database transaction.
- Repeated and concurrent commands cannot duplicate durable effects.
- Failed brokerage fetches cannot corrupt the last good portfolio.
- Provider cursors advance only with durable event persistence.
- Alerts exist durably before delivery is attempted.
- Every run has an inspectable state history and policy versions.
- Unit tests prove failure behavior without live services.
- You can draw the orchestration stages and transaction boundaries from memory.

---

## 14. Self-test

1. What is the difference between orchestration and domain logic?
2. Why do we need both a distributed lock and an idempotency key?
3. Why must external calls happen outside transactions?
4. What happens when Schwab returns an incomplete account snapshot?
5. When is a provider cursor safe to advance?
6. Why are alerts persisted before push/email delivery?
7. Which stages may safely complete when one optional news provider fails?
8. How would you resume a run in the future without redesigning the state model?
