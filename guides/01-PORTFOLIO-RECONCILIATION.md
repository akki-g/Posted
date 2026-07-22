# Guide 01 — Portfolio Reconciliation

[← Roadmap](00-LEARNING-ROADMAP.md) | [Next: Event pipeline →](02-EVENT-PIPELINE.md)

**You write:** `backend/app/portfolio/reconcile.py`

**Your immediate goal:** make the seven starter tests in `backend/app/tests/user_owned/test_portfolio_reconcile.py` pass. Do not think about FastAPI, Schwab OAuth, SQLAlchemy, or the frontend while working on this file.

This guide assumes you are learning reconciliation for the first time. It explains what every input means, what data structures to create, how to classify each change, and how to work through the tests one at a time. It deliberately stops short of giving you a finished implementation.

---

## 1. Begin here

Open these four files side by side:

1. `backend/app/portfolio/reconcile.py` — the only implementation file you edit.
2. `backend/app/domain/models.py` — the input and output dataclasses.
3. `backend/app/domain/enums.py` — the allowed change and rejection values.
4. `backend/app/tests/user_owned/test_portfolio_reconcile.py` — the executable requirements.

Run only this exercise from the `backend` directory:

```bash
uv run pytest -m user_owned app/tests/user_owned/test_portfolio_reconcile.py -q
```

Initially, all seven tests should fail at the `NotImplementedError`. That is the correct starting state.

To run one test while learning:

```bash
uv run pytest -m user_owned \
  app/tests/user_owned/test_portfolio_reconcile.py::test_new_position_is_opened -q
```

Your first milestone is one passing test, not the entire module.

---

## 2. The problem in plain English

Schwab periodically gives Posted a **snapshot**: “these are the positions in this account right now.” Posted already has the positions saved from the last successful snapshot.

Your function compares:

```text
previous stored positions  vs.  current provider observations
```

and returns:

```text
the new canonical positions
+ a description of what changed
+ any input records that could not be trusted
```

Imagine the previous state is:

| Account | Security | Quantity |
|---|---|---:|
| taxable | AAPL | 10 |
| taxable | MSFT | 3 |

The new snapshot contains:

| Account | Provider symbol | Quantity |
|---|---|---:|
| taxable | AAPL | 4 |
| taxable | AAPL | 8 |
| taxable | NVDA | 2 |

The two AAPL records first coalesce into one current position of 12 shares. The result is therefore:

| Security | Previous | Current | Delta | Classification |
|---|---:|---:|---:|---|
| AAPL | 10 | 12 | +2 | `INCREASED` |
| MSFT | 3 | 0 | -3 | `CLOSED` |
| NVDA | 0 | 2 | +2 | `OPENED` |

That is the entire job. Validation, identity resolution, duplicate coalescing, and deterministic ordering make the job reliable.

---

## 3. Understand the function contract

The function signature already exists:

```python
def reconcile_positions(
    *,
    observations: Sequence[PositionObservation],
    previous: Sequence[StoredPosition],
    resolve_security: SecurityResolver,
) -> ReconciliationResult:
```

### `observations`

These are provider-neutral records produced by the Schwab mapper. One observation says what Schwab reported for one instrument:

```python
PositionObservation(
    account_id=...,
    observed_at=...,
    provider_instrument_id="provider-aapl",
    symbol="AAPL",
    cusip=None,
    asset_type=AssetType.EQUITY,
    quantity=Decimal("10"),
    market_value=Decimal("2000"),
    average_price=Decimal("150"),
)
```

An observation does **not** contain Posted's `security_id`. Provider symbols and identifiers are not trusted as durable internal identity.

### `previous`

These are the positions Posted stored after the last successful sync:

```python
StoredPosition(
    position_id=...,
    account_id=...,
    security_id=...,
    canonical_symbol="AAPL",
    quantity=Decimal("10"),
    market_value=Decimal("2000"),
    average_price=Decimal("150"),
)
```

They already contain Posted's stable `security_id`.

### `resolve_security`

This is a function passed into your function. Call it with an observation:

```python
identity = resolve_security(observation)
```

It returns either:

```python
SecurityIdentity(security_id=..., canonical_symbol="AAPL")
```

or `None` if the observation cannot be mapped to a known security.

For the tests, the resolver is in `app/tests/user_owned/factories.py`. It recognizes AAPL, MSFT, and NVDA. Your code should call the resolver; it should not reproduce its lookup logic.

The resolver is already supplied to `reconcile_positions` as its third argument. You are not
supposed to write or import a concrete resolver in this exercise. Think of it as a question
your function can ask:

```text
"Which permanent Posted security does this temporary provider record describe?"
```

The test resolver is approximately:

```python
def resolve_security(observation):
    return SECURITIES.get((observation.symbol or "").upper())
```

That means the calls behave conceptually like this:

```text
resolve_security(an AAPL observation)
    -> SecurityIdentity(AAPL's stable security_id, "AAPL")

resolve_security(an MSFT observation)
    -> SecurityIdentity(MSFT's stable security_id, "MSFT")

resolve_security(an unknown observation)
    -> None
```

The important separation is:

- `PositionObservation` contains what the provider reported.
- `SecurityIdentity` contains Posted's permanent identity for that security.
- `resolve_security` converts from the first concept to the second.
- `reconcile_positions` uses the resolver but does not know how its lookup works.

Inside your loop, `obs` is already a `PositionObservation`:

```python
for obs in observations:
    identity = resolve_security(obs)
```

You do not construct another `PositionObservation`. You read fields from `obs` and eventually
construct output objects such as `ReconciledPosition` and `PositionDelta`.

### The result

Return exactly one `ReconciliationResult`:

```python
ReconciliationResult(
    positions=(...),
    deltas=(...),
    rejected=(...),
)
```

- `positions` is the complete trustworthy current state.
- `deltas` explains the quantity transition for every current or previous position.
- `rejected` explains why an observation was excluded.

All three fields are tuples, not lists.

---

## 4. The identity key is the central idea

Use this key everywhere:

```text
(account_id, security_id)
```

In Python, that can be represented by a tuple:

```python
key = (account_id, security_id)
```

Why both fields?

- One person can own AAPL in a taxable account and an IRA. Those are two positions.
- A ticker can change, while Posted's `security_id` remains stable.
- Two provider aliases can resolve to the same Posted security.

Do not use only `symbol`, only `security_id`, or `provider_instrument_id` as the dictionary key.

The algorithm becomes manageable once both current and previous state use the same key:

```text
current_by_key[(account_id, security_id)] = ReconciledPosition(...)
previous_by_key[(account_id, security_id)] = StoredPosition(...)
```

Then you compare the union of their keys.

---

## 5. Build the implementation in four passes

Do these passes in order. Do not begin with every edge case at once.

### Pass 1 — Resolve, group, and open positions

For every observation:

1. Confirm that its asset type is supported.
2. Call `resolve_security(observation)`.
3. If it resolves, create the `(account_id, security_id)` key.
4. Append the observation to a list stored under that key.

The useful intermediate structure is conceptually:

```python
groups: dict[tuple[UUID, UUID], list[tuple[PositionObservation, SecurityIdentity]]]
```

Do not worry if you choose a small dataclass instead of the inner tuple. The important property is that every group retains both the observations and the resolved canonical identity.

For each group, create one `ReconciledPosition`. With a single observation, its values are copied directly except that identity comes from `SecurityIdentity`:

```text
account_id       <- observation.account_id
security_id      <- resolved identity.security_id
canonical_symbol <- resolved identity.canonical_symbol
quantity         <- observation.quantity
market_value     <- observation.market_value
average_price    <- observation.average_price
```

With no previous position, emit an `OPENED` delta:

```text
previous_quantity = 0
current_quantity  = current position quantity
quantity_delta    = current - previous
```

Stop and run `test_new_position_is_opened`.

### Pass 2 — Compare current and previous state

Build `previous_by_key` with the same `(account_id, security_id)` key. Then iterate over:

```python
all_keys = set(current_by_key) | set(previous_by_key)
```

For each key, read the quantities. Use `Decimal("0")` when one side does not exist:

```text
previous quantity = previous position quantity, otherwise Decimal("0")
current quantity  = current position quantity, otherwise Decimal("0")
quantity delta    = current quantity - previous quantity
```

Classify using this table:

| Previous exists? | Current exists? | Quantity relationship | Kind |
|---|---|---|---|
| no | yes | current > 0 | `OPENED` |
| yes | no | current = 0 | `CLOSED` |
| yes | yes | current > previous | `INCREASED` |
| yes | yes | current < previous | `DECREASED` |
| yes | yes | current = previous | `UNCHANGED` |

The kind depends on **quantity**, not market value. If AAPL remains at 10 shares but its market value rises, its position delta is still `UNCHANGED`.

Every `PositionDelta` needs:

```text
account_id
security_id
kind
previous_quantity
current_quantity
quantity_delta
```

A closed position appears in `deltas` but not in `positions`.

Stop and run these tests:

```bash
uv run pytest -m user_owned \
  app/tests/user_owned/test_portfolio_reconcile.py::test_identical_position_is_unchanged \
  app/tests/user_owned/test_portfolio_reconcile.py::test_missing_current_position_is_closed -q
```

### Pass 3 — Coalesce duplicate observations

The provider may return multiple observations that resolve to the same key. One group must become one position.

#### Quantity

Sum every quantity using `Decimal`:

```text
total quantity = q1 + q2 + ... + qN
```

#### Market value

Only report a total market value when every record has one:

```text
[400, 900]  -> 1300
[400, None] -> None
```

Returning 400 in the second case would falsely describe an incomplete value as complete.

#### Average price

Use a quantity-weighted average when every contributing average price exists and total quantity is positive:

```text
weighted average = sum(quantity × average price) / total quantity
```

The test example is:

```text
2 shares at 100 + 3 shares at 200

(2 × 100 + 3 × 200) / (2 + 3)
= (200 + 600) / 5
= 160
```

Do not average `100` and `200` directly; that would produce 150 and incorrectly give the smaller lot equal weight.

For the first implementation, use the conservative rule that if any contributing average price is `None`, the coalesced average price is also `None`.

Stop and run:

```bash
uv run pytest -m user_owned \
  app/tests/user_owned/test_portfolio_reconcile.py::test_duplicates_coalesce_with_weighted_average \
  app/tests/user_owned/test_portfolio_reconcile.py::test_partial_market_value_is_unknown -q
```

### Pass 4 — Rejections and deterministic ordering

For the MVP, the supported position asset types are:

```text
EQUITY and ETF
```

Reject unsupported observations instead of silently dropping them. Construct a `RejectedObservation` using:

```text
observation = the original input object
reason      = a RejectionReason enum value
detail      = a short human-readable explanation
```

Use these rules in this order so one malformed record always receives the same reason:

| Condition | Reason |
|---|---|
| `observed_at` has no timezone | `INVALID_TIMESTAMP` |
| quantity is negative | `NEGATIVE_QUANTITY` |
| asset type is not supported | `UNSUPPORTED_ASSET_TYPE` |
| symbol, CUSIP, and provider instrument ID are all absent | `MISSING_IDENTITY` |
| resolver returns `None` | `UNRESOLVED_SECURITY` |

The starter suite directly tests unsupported assets. The other rejection rules are hardening cases you should add after the seven tests pass.

Finally, make every output order deterministic. Input order must not affect equality. A simple stable key for positions and deltas is:

```python
(str(account_id), str(security_id))
```

For rejections, use only comparable values and replace missing strings with `""`, for example account ID, symbol-or-empty, provider-ID-or-empty, and timestamp.

Stop and run the entire exercise:

```bash
uv run pytest -m user_owned app/tests/user_owned/test_portfolio_reconcile.py -q
```

---

## 6. Implementation walkthrough: translate this pseudocode into Python

This section makes one design choice for every previously vague point. Follow this shape for
your first implementation. The pseudocode is deliberately one step short of copy-and-paste
Python, but every condition, lookup, collection, and constructor is shown.

Keep the imports already in the starter and add the missing names so the top of the file has
this overall shape:

```python
from decimal import Decimal
from typing import Protocol, Sequence

from app.domain.enums import AssetType, PositionChangeKind, RejectionReason
from app.domain.models import (
    PositionDelta,
    PositionObservation,
    ReconciledPosition,
    ReconciliationResult,
    RejectedObservation,
    SecurityIdentity,
    StoredPosition,
)
```

You do not need FastAPI, Schwab, a database, or any other application import in this file.

### 6.1 What “validate the invariants” means

An invariant is simply a condition that must be true before an observation is trusted. You
are not calling a validation library. You are writing ordinary `if` statements against the
fields on `PositionObservation`.

Use these exact checks, in this exact order:

| Question | Python condition when invalid | Returned reason |
|---|---|---|
| Does the timestamp identify a timezone? | `obs.observed_at.tzinfo is None or obs.observed_at.utcoffset() is None` | `INVALID_TIMESTAMP` |
| Is the quantity non-negative? | `obs.quantity < Decimal("0")` | `NEGATIVE_QUANTITY` |
| Is this an MVP-supported asset? | `obs.asset_type not in {AssetType.EQUITY, AssetType.ETF}` | `UNSUPPORTED_ASSET_TYPE` |
| Is there anything the resolver could identify? | `not obs.symbol and not obs.cusip and not obs.provider_instrument_id` | `MISSING_IDENTITY` |

Implement those checks in one helper:

```python
PSEUDOCODE _rejection_reason(obs: PositionObservation):
    IF obs.observed_at.tzinfo is None OR obs.observed_at.utcoffset() is None:
        return RejectionReason.INVALID_TIMESTAMP

    IF obs.quantity < Decimal("0"):
        return RejectionReason.NEGATIVE_QUANTITY

    IF obs.asset_type NOT IN {AssetType.EQUITY, AssetType.ETF}:
        return RejectionReason.UNSUPPORTED_ASSET_TYPE

    IF NOT obs.symbol AND NOT obs.cusip AND NOT obs.provider_instrument_id:
        return RejectionReason.MISSING_IDENTITY

    return None
```

Why return only one reason? A record could be wrong in multiple ways, but a fixed priority
makes repeated runs produce the same diagnosis. `None` means the observation passed these
four checks. It does not yet mean the security can be resolved.

### 6.2 Exactly how to call `resolve_security`

`resolve_security` is the function parameter already present in the starter signature:

```python
def reconcile_positions(..., resolve_security: SecurityResolver):
```

Do not define another resolver and do not inspect the test's `SECURITIES` dictionary from
production code. Call the supplied function once for each observation that passes validation:

```python
identity = resolve_security(obs)
```

The result has only two possibilities:

```text
SecurityIdentity(...) -> use identity.security_id and identity.canonical_symbol
None                  -> reject obs with RejectionReason.UNRESOLVED_SECURITY
```

The security ID from the resolver, not the provider symbol, becomes part of the grouping key.

### 6.3 Use these exact collections

Use two dictionaries while processing the current snapshot:

```python
groups = {}             # key -> list[PositionObservation]
identity_by_key = {}    # key -> SecurityIdentity
```

The same key is used in both:

```python
key = (obs.account_id, identity.security_id)
```

Here is the complete validation, resolution, and grouping loop:

```python
PSEUDOCODE:
    rejected = []
    groups = {}
    identity_by_key = {}

    FOR obs IN observations:
        reason = _rejection_reason(obs)

        IF reason IS NOT None:
            rejected.append(
                RejectedObservation(
                    observation=obs,
                    reason=reason,
                    detail="Observation failed validation: " + reason.value,
                )
            )
            CONTINUE

        identity = resolve_security(obs)

        IF identity IS None:
            rejected.append(
                RejectedObservation(
                    observation=obs,
                    reason=RejectionReason.UNRESOLVED_SECURITY,
                    detail="No canonical security matched this observation",
                )
            )
            CONTINUE

        key = (obs.account_id, identity.security_id)

        IF key NOT IN groups:
            groups[key] = []
            identity_by_key[key] = identity

        groups[key].append(obs)
```

After this loop, two AAPL records for the same account are stored in the same list. AAPL in a
different account has a different key and therefore a different list.

### 6.4 Coalesce one group

`_coalesce` receives the list from `groups[key]` and the matching
`identity_by_key[key]`. It returns either one current position or `None`.

```python
PSEUDOCODE _coalesce(group, identity):
    ZERO = Decimal("0")

    total_quantity = sum(
        (obs.quantity FOR obs IN group),
        ZERO,
    )

    IF total_quantity == ZERO:
        return None

    IF any(obs.market_value IS None FOR obs IN group):
        total_market_value = None
    ELSE:
        total_market_value = sum(
            (obs.market_value FOR obs IN group),
            ZERO,
        )

    IF any(obs.average_price IS None FOR obs IN group):
        combined_average_price = None
    ELSE:
        weighted_cost = sum(
            (obs.quantity * obs.average_price FOR obs IN group),
            ZERO,
        )
        combined_average_price = weighted_cost / total_quantity

    first = group[0]

    return ReconciledPosition(
        account_id=first.account_id,
        security_id=identity.security_id,
        canonical_symbol=identity.canonical_symbol,
        quantity=total_quantity,
        market_value=total_market_value,
        average_price=combined_average_price,
    )
```

The `None` rules are conservative: if one provider record lacks part of a total, Posted must
not present the known portion as the complete value.

Build the current-position index like this:

```python
PSEUDOCODE:
    current_by_key = {}

    FOR key, group IN groups.items():
        current = _coalesce(group, identity_by_key[key])

        IF current IS NOT None:
            current_by_key[key] = current
```

### 6.5 Index the previous snapshot

The previous positions already have internal security IDs, so they do not go through the
resolver:

```python
PSEUDOCODE:
    previous_by_key = {}

    FOR stored IN previous:
        key = (stored.account_id, stored.security_id)
        previous_by_key[key] = stored
```

Now `current_by_key` and `previous_by_key` use identical keys and can be compared directly.

### 6.6 Classify one transition

This helper accepts the actual objects, not quantities. Either argument can be `None` because
a position may exist on only one side of the comparison.

```python
PSEUDOCODE _change_kind(old, new):
    IF old IS None AND new IS None:
        raise AssertionError("a reconciliation key must exist in at least one snapshot")

    IF old IS None:
        return PositionChangeKind.OPENED

    IF new IS None:
        return PositionChangeKind.CLOSED

    IF new.quantity > old.quantity:
        return PositionChangeKind.INCREASED

    IF new.quantity < old.quantity:
        return PositionChangeKind.DECREASED

    return PositionChangeKind.UNCHANGED
```

The caller only invokes this helper for a key from the union of both dictionaries, so `old`
and `new` cannot both be `None`.

Construct deltas from that union:

```python
PSEUDOCODE:
    ZERO = Decimal("0")
    deltas = []
    all_keys = set(current_by_key) | set(previous_by_key)

    FOR key IN all_keys:
        old = previous_by_key.get(key)
        new = current_by_key.get(key)

        old_quantity = old.quantity IF old IS NOT None ELSE ZERO
        new_quantity = new.quantity IF new IS NOT None ELSE ZERO

        account_id, security_id = key

        deltas.append(
            PositionDelta(
                account_id=account_id,
                security_id=security_id,
                kind=_change_kind(old, new),
                previous_quantity=old_quantity,
                current_quantity=new_quantity,
                quantity_delta=new_quantity - old_quantity,
            )
        )
```

The union is why a missing current position still produces a `CLOSED` delta.

### 6.7 Sort and return

Sets and input dictionaries must not determine output order. The mechanical sort helpers are
already implemented in `reconcile.py`:

```python
_position_sort_key(value)
_rejection_sort_key(rejection)
```

Use them to create the required tuples:

```python
PSEUDOCODE:
    positions_in_order = sorted(current_by_key.values(), key=_position_sort_key)
    deltas_in_order = sorted(deltas, key=_position_sort_key)
    rejected_in_order = sorted(rejected, key=_rejection_sort_key)

    return ReconciliationResult(
        positions=tuple(positions_in_order),
        deltas=tuple(deltas_in_order),
        rejected=tuple(rejected_in_order),
    )
```

### 6.8 The exact functions in the finished file

Your completed module should contain these functions:

```python
def _rejection_reason(
    observation: PositionObservation,
) -> RejectionReason | None: ...

def _coalesce(
    observations: Sequence[PositionObservation],
    identity: SecurityIdentity,
) -> ReconciledPosition | None: ...

def _change_kind(
    previous: StoredPosition | None,
    current: ReconciledPosition | None,
) -> PositionChangeKind: ...

def reconcile_positions(
    *,
    observations: Sequence[PositionObservation],
    previous: Sequence[StoredPosition],
    resolve_security: SecurityResolver,
) -> ReconciliationResult: ...
```

`_position_sort_key` and `_rejection_sort_key` also exist in the finished file, but they are
provided utilities rather than functions you need to implement.

You may place the public function before or after the private helpers. Python only requires
the helpers to be defined by the time `reconcile_positions` is actually called.

---

## 7. Follow one record through the pipeline

When the code feels abstract, trace this object from the test factory:

```python
observation()
```

It produces an AAPL equity observation with:

```text
account_id    = stable UUID for "account-1"
symbol        = AAPL
quantity      = 10
market_value  = 2000
average_price = 150
```

The test resolver returns the AAPL `SecurityIdentity`. Your grouping key becomes:

```text
(stable account-1 UUID, stable AAPL security UUID)
```

With `previous=[]`, coalescing produces one position and comparison produces:

```text
previous quantity = 0
current quantity  = 10
delta             = 10
kind              = OPENED
```

If you cannot explain what value a variable holds at each of those stages, add a temporary debugger breakpoint or print the value while running the single test. Remove debug output before finishing.

---

## 8. What each starter test is telling you

### `test_new_position_is_opened`

You need current grouping, a current position, an `OPENED` classification, and `current - previous` delta arithmetic.

### `test_identical_position_is_unchanged`

Current and previous dictionaries must use exactly the same identity key. Do not classify identical quantities as an increase because the market value differs.

### `test_missing_current_position_is_closed`

Iterating only over current keys is insufficient. You must iterate over the union of current and previous keys.

### `test_duplicates_coalesce_with_weighted_average`

Group before creating positions. Sum quantities and market values; use quantity-weighted cost.

### `test_partial_market_value_is_unknown`

Missing information must propagate rather than producing a plausible but incomplete total.

### `test_unsupported_asset_is_rejected`

Rejection is data, not an exception. One bad observation should not abort reconciliation of the valid observations around it.

### `test_result_does_not_depend_on_observation_order`

Never rely on dictionary insertion order for returned values. Sort every returned collection explicitly.

---

## 9. Common mistakes and how to diagnose them

### “My opened test passes, but the closed test has no delta”

You probably iterate only over current positions. Compare the union of current and previous keys.

### “The weighted average is 150 instead of 160”

You computed the ordinary mean. Weight each price by that observation's quantity.

### “Forward and reverse inputs produce different results”

Your returned tuple follows input or dictionary insertion order. Sort by stable scalar keys before creating tuples.

### “My resolver returns `None` unexpectedly”

Look at `factories.py`: the starter resolver recognizes only AAPL, MSFT, and NVDA by uppercased symbol.

### “I get a float/Decimal error”

Do not use `0.0`, `sum(..., 0.0)`, or convert values to `float`. Start sums with `Decimal("0")`.

### “The result has a zero-quantity current position”

A closed position belongs in `deltas`, not `positions`. After coalescing, omit a group whose total quantity is zero. For the starter implementation, use exact zero; add a residual tolerance only after the baseline tests pass.

### “The unsupported option throws instead of appearing in `rejected`”

Validation failures in this pure batch function should append a `RejectedObservation` and continue processing.

---

## 10. Rules that are intentionally outside this function

Do not solve these here:

- Whether Schwab's snapshot was complete. The orchestrator decides whether reconciliation may run.
- Database reads or writes. Repositories load `previous` and persist your result.
- Schwab field names. The provider mapper creates `PositionObservation`.
- Security lookup details. The injected resolver owns that.
- Portfolio percentages and gains. This exercise reconciles position truth and quantity changes.
- Alerts. Later modules determine whether a change or company event warrants an alert.

Keeping these concerns out is what makes reconciliation easy to test.

---

## 11. Hardening after the starter tests pass

Once all seven current tests are green, ask the agent to add these tests before extending the implementation:

1. quantity increase and decrease;
2. same quantity with a changed market value remains `UNCHANGED`;
3. same security in two accounts remains two positions;
4. symbol aliases resolving to one security coalesce;
5. unresolved identity is returned in `rejected`;
6. negative quantity is rejected while shorts are out of scope;
7. naive timestamps are rejected;
8. partial average-price data produces `None`;
9. a zero-total group does not create a current position;
10. feeding the result back as `previous` produces only `UNCHANGED` deltas.

Do not add tolerance, short-position support, options, or mutual-fund behavior until a test states the intended rule.

---

## 12. Completion checklist

Before asking for review, confirm:

- [ ] Only `backend/app/portfolio/reconcile.py` was edited for the exercise.
- [ ] No Schwab, FastAPI, SQLAlchemy, or database module is imported.
- [ ] All arithmetic remains `Decimal`.
- [ ] The identity key is `(account_id, security_id)`.
- [ ] Duplicate observations coalesce before comparison.
- [ ] Missing current positions produce `CLOSED` deltas.
- [ ] Quantity, not market value, determines the change kind.
- [ ] Invalid observations are returned in `rejected`.
- [ ] Every output tuple is deterministically sorted.
- [ ] The seven starter tests pass.
- [ ] You can explain the AAPL/MSFT/NVDA worked example without reading the guide.

When you reach that point, ask the agent to review your file rather than replace it. The review should identify the first failing invariant, add hardening tests, and explain any correction while keeping the implementation yours.
