# Guide 07 — Ledger Reconciliation

[← Transaction normalization](06-TRANSACTION-NORMALIZATION.md) | [Next: Spending classification →](08-SPENDING-CLASSIFICATION.md)

**You write:** `backend/app/money/reconcile.py`

**Immediate goal:** turn an incremental provider update into explicit ledger actions without inventing deletions.

## 1. Run the exercise

```bash
cd backend
uv run pytest -m user_owned app/tests/user_owned/test_money_reconcile.py -q
```

Start with:

```bash
uv run pytest -m user_owned \
  app/tests/user_owned/test_money_reconcile.py::test_new_transaction_is_inserted -q
```

## 2. This is not snapshot reconciliation

Schwab positions are a complete snapshot: a position missing from the new snapshot is closed. Plaid `/transactions/sync` is incremental: one response contains only added, modified, and removed changes since a cursor.

Therefore:

```text
transaction absent from incoming page != delete it
transaction present in explicit removed list = delete it
```

This is the most important invariant in the file.

## 3. Strong identity

When `provider_transaction_id` exists, use:

```text
(source, provider_transaction_id)
```

Build indexes for existing records:

```text
existing_by_provider_key
existing_pending_by_provider_key
```

The fingerprint is a fallback identity for sources that do not issue IDs. Keep the fallback account-scoped:

```text
(source, account_id, fingerprint)
```

Do not match only by merchant and amount. Two coffee purchases can have identical values.

## 4. Action meanings

| Kind | Existing ID | Transaction | Meaning |
|---|---|---|---|
| `INSERT` | `None` | incoming object | No durable record matches. |
| `UNCHANGED` | stored UUID | incoming object | Same identity and canonical values. |
| `UPDATE` | stored UUID | incoming object | Same identity, some stored value changed. |
| `DELETE` | stored UUID | `None` | Provider explicitly removed it. |
| `REPLACE_PENDING` | pending stored UUID | posted object | A posted record supersedes its pending predecessor. |

Always add a short `detail` explaining the decision. Tests do not prescribe its exact wording, but production logs and audit screens need it.

## 5. Apply precedence in three passes

### Pass 1 — Explicit removals

For every `ProviderTransactionRef` in `removed`, find the existing record using `(source, provider_transaction_id)`. If found, emit `DELETE`.

Track consumed existing IDs so the same record cannot also receive an update. An unknown removed ID is safe to ignore; providers may repeat removal notices after a local cleanup.

### Pass 2 — Pending-to-posted replacement

Banks often first emit:

```text
pending provider ID = pending-123
amount              = 6.50
```

and later emit:

```text
posted provider ID             = posted-987
pending_provider_transaction_id = pending-123
amount                          = 6.84
```

The posted record is not a second purchase. If an incoming transaction names a pending predecessor and that predecessor exists with `PENDING` status, emit `REPLACE_PENDING` against the pending record.

This rule must run before ordinary insert matching. The posted transaction intentionally has a different provider ID.

### Pass 3 — Insert, update, or unchanged

For every remaining incoming transaction:

1. Find its existing match by provider key, then fingerprint fallback.
2. If none exists, emit `INSERT`.
3. If one exists and all persisted canonical fields are equal, emit `UNCHANGED`.
4. Otherwise emit `UPDATE`.

Compare the fields represented on both `NormalizedTransaction` and `StoredMoneyTransaction`; ignore only the database's `transaction_id`. A helper that projects both objects to the same tuple keeps this explicit.

## 6. Collision and duplicate policy

Before emitting actions, make duplicate input deterministic:

- If two incoming rows have the same strong provider key and identical values, coalesce them.
- If the same key has conflicting values, choose a deterministic winner only if you can state the policy; a conservative production version would quarantine the batch.
- Never emit two actions for one existing transaction.
- Never emit two inserts for one provider key.

The starter fixtures do not force a conflict policy, but your data structures should make a future conflict check possible.

## 7. Deterministic ordering

Sort actions using stable values rather than the order of provider pages. A reasonable order key is:

```text
(source, provider ID or fingerprint, action kind, existing UUID or "")
```

For a `DELETE`, obtain source/provider ID from the removal reference or matched existing record. For other actions, use the incoming transaction.

Return `LedgerReconciliationResult(actions=tuple(...))`.

## 8. Exact implementation walkthrough

The repetitive identity projections and sorting code are already implemented:

```python
_provider_key(transaction_or_ref)
_fingerprint_key(transaction)
_canonical_values(transaction)
_transaction_sort_key(transaction)
_action_sort_key(action)
```

Read their return values once. Do not rewrite them. Your learning task is action precedence and
preventing one stored record from receiving two actions.

Add these imports:

```python
from app.money.enums import LedgerActionKind, TransactionStatus
from app.money.models import LedgerAction
```

### 8.1 Build the existing-record indexes

```python
PSEUDOCODE:
    existing_by_provider = {}
    existing_by_fingerprint = {}
    pending_by_provider = {}

    FOR stored IN sorted(existing, key=_transaction_sort_key):
        provider_key = _provider_key(stored)

        IF provider_key IS NOT None:
            existing_by_provider[provider_key] = stored

            IF stored.status IS TransactionStatus.PENDING:
                pending_by_provider[provider_key] = stored

        existing_by_fingerprint[_fingerprint_key(stored)] = stored
```

### 8.2 Coalesce identical incoming duplicates

The current result model has no quarantine field. Therefore, use an explicit `ValueError` for
conflicting duplicates rather than silently selecting a winner:

```python
PSEUDOCODE _coalesce_incoming(incoming):
    unique = {}

    FOR transaction IN sorted(incoming, key=_transaction_sort_key):
        strong_key = _provider_key(transaction)
        identity_key = (
            ("provider", strong_key)
            IF strong_key IS NOT None
            ELSE ("fingerprint", _fingerprint_key(transaction))
        )

        prior = unique.get(identity_key)

        IF prior IS None:
            unique[identity_key] = transaction
        ELSE IF _canonical_values(prior) != _canonical_values(transaction):
            raise ValueError("conflicting incoming transactions share one identity")

    return tuple(sorted(unique.values(), key=_transaction_sort_key))
```

Identical duplicates collapse because the existing value remains in `unique`.

### 8.3 Pass one: explicit removals

```python
PSEUDOCODE reconcile_ledger(...):
    build the three existing indexes from section 8.1
    incoming_once = _coalesce_incoming(incoming)
    actions = []
    consumed_existing_ids = empty set

    FOR reference IN sorted(removed, key=lambda ref: (ref.source.value, ref.provider_transaction_id)):
        stored = existing_by_provider.get(_provider_key(reference))

        IF stored IS None OR stored.transaction_id IN consumed_existing_ids:
            CONTINUE

        actions.append(
            LedgerAction(
                kind=LedgerActionKind.DELETE,
                existing_transaction_id=stored.transaction_id,
                transaction=None,
                detail="Provider explicitly removed this transaction",
            )
        )
        consumed_existing_ids.add(stored.transaction_id)
```

Do not inspect which other stored records were absent. Only `removed` creates deletes.

### 8.4 Pass two: pending replacement, then ordinary matching

Continue the same function:

```python
PSEUDOCODE:
    FOR transaction IN incoming_once:
        pending_id = transaction.pending_provider_transaction_id

        IF pending_id IS NOT None:
            pending_key = (transaction.source.value, pending_id)
            pending = pending_by_provider.get(pending_key)

            IF pending exists AND pending.transaction_id NOT IN consumed_existing_ids:
                actions.append(
                    LedgerAction(
                        kind=LedgerActionKind.REPLACE_PENDING,
                        existing_transaction_id=pending.transaction_id,
                        transaction=transaction,
                        detail="Posted transaction replaces its pending predecessor",
                    )
                )
                consumed_existing_ids.add(pending.transaction_id)
                CONTINUE

        provider_key = _provider_key(transaction)
        stored = (
            existing_by_provider.get(provider_key)
            IF provider_key IS NOT None
            ELSE None
        )

        IF stored IS None:
            stored = existing_by_fingerprint.get(_fingerprint_key(transaction))

        IF stored IS None:
            actions.append(
                LedgerAction(
                    kind=LedgerActionKind.INSERT,
                    existing_transaction_id=None,
                    transaction=transaction,
                    detail="No stored transaction matched this identity",
                )
            )
            CONTINUE

        IF stored.transaction_id IN consumed_existing_ids:
            CONTINUE because explicit removal/replacement already won

        IF _canonical_values(stored) == _canonical_values(transaction):
            kind = LedgerActionKind.UNCHANGED
            detail = "Stored and incoming canonical values are identical"
        ELSE:
            kind = LedgerActionKind.UPDATE
            detail = "Incoming canonical values changed"

        actions.append(
            LedgerAction(
                kind=kind,
                existing_transaction_id=stored.transaction_id,
                transaction=transaction,
                detail=detail,
            )
        )
        consumed_existing_ids.add(stored.transaction_id)

    return LedgerReconciliationResult(
        actions=tuple(sorted(actions, key=_action_sort_key))
    )
```

The learner-owned code is `_coalesce_incoming` and `reconcile_ledger`. Persistence remains out
of this file; an agent-owned repository applies the returned plan transactionally.

## 9. Test-by-test route

1. `test_new_transaction_is_inserted`
2. `test_identical_transaction_is_unchanged`
3. `test_changed_provider_transaction_is_updated`
4. `test_explicitly_removed_provider_transaction_is_deleted`
5. `test_posted_transaction_replaces_its_pending_predecessor`
6. `test_reconciliation_is_order_independent`

Run only the next failing test. Print or inspect your indexes if the identity is unclear.

## 10. Common mistakes

- Deleting stored records merely because they are absent from `incoming`.
- Treating posted and pending forms as two purchases.
- Matching globally on provider ID without including source.
- considering same identity automatically unchanged without comparing values.
- applying database changes in the pure domain function.
- depending on input order for conflict resolution or action order.

## 11. Completion check

```bash
uv run pytest -m user_owned app/tests/user_owned/test_money_reconcile.py -q
```

You should be able to contrast complete-snapshot reconciliation with cursor-based incremental reconciliation in your own words.
