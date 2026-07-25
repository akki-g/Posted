"""Human-owned incremental-ledger reconciliation exercise.

Implementation contract: guides/07-LEDGER-RECONCILIATION.md.
The coding agent must not implement or replace this module unless explicitly asked.
"""

from collections.abc import Sequence

from app.money.enums import LedgerActionKind, TransactionStatus
from app.money.models import (
    LedgerAction,
    LedgerReconciliationResult,
    NormalizedTransaction,
    ProviderTransactionRef,
    StoredMoneyTransaction,
)

TransactionRecord = NormalizedTransaction | StoredMoneyTransaction


def _provider_key(
    transaction: TransactionRecord | ProviderTransactionRef,
) -> tuple[str, str] | None:
    """Return strong provider identity, or None when a transaction has no provider ID."""

    provider_id = transaction.provider_transaction_id
    if provider_id is None or not provider_id.strip():
        return None
    return (transaction.source.value, provider_id.strip())


def _fingerprint_key(transaction: TransactionRecord) -> tuple[str, str, str]:
    """Return the account-scoped fallback identity for a transaction."""

    return (transaction.source.value, str(transaction.account_id), transaction.fingerprint)


def _canonical_values(transaction: TransactionRecord) -> tuple[object, ...]:
    """Project stored and incoming records onto the same persisted domain fields."""

    return (
        transaction.account_id,
        transaction.account_type,
        transaction.source,
        transaction.provider_transaction_id,
        transaction.pending_provider_transaction_id,
        transaction.status,
        transaction.direction,
        transaction.amount,
        transaction.currency,
        transaction.merchant_name,
        transaction.description,
        transaction.occurred_at,
        transaction.posted_at,
        transaction.category_primary,
        transaction.category_detailed,
        transaction.payment_channel,
        transaction.fingerprint,
    )


def _transaction_sort_key(transaction: TransactionRecord) -> tuple[str, str, str, str]:
    """Return a stable order for incoming and existing transaction records."""

    return (
        transaction.source.value,
        transaction.provider_transaction_id or transaction.fingerprint,
        transaction.occurred_at.isoformat(),
        str(transaction.account_id),
    )


def _action_sort_key(action: LedgerAction) -> tuple[str, str, str, str]:
    """Return a deterministic action order without relying on provider-page order."""

    transaction = action.transaction
    return (
        transaction.source.value if transaction is not None else "",
        (transaction.provider_transaction_id or transaction.fingerprint)
        if transaction is not None
        else "",
        action.kind.value,
        str(action.existing_transaction_id or ""),
    )


def _coalesce_incoming(
    incoming: Sequence[NormalizedTransaction],
) -> tuple[NormalizedTransaction, ...]:
    """Collapse identical provider repeats and reject identity conflicts."""

    unique: dict[tuple[object, ...], NormalizedTransaction] = {}
    for transaction in sorted(incoming, key=_transaction_sort_key):
        strong_key = _provider_key(transaction)
        identity_key: tuple[object, ...]
        if strong_key is not None:
            identity_key = ("provider", *strong_key)
        else:
            identity_key = ("fingerprint", *_fingerprint_key(transaction))

        prior = unique.get(identity_key)
        if prior is None:
            unique[identity_key] = transaction
        elif _canonical_values(prior) != _canonical_values(transaction):
            # Silently picking one provider row would make the ledger depend on page
            # order. Failing the batch is safer until a quarantine result is modeled.
            raise ValueError("conflicting incoming transactions share one identity")

    return tuple(sorted(unique.values(), key=_transaction_sort_key))


def reconcile_ledger(
    *,
    incoming: Sequence[NormalizedTransaction],
    existing: Sequence[StoredMoneyTransaction],
    removed: Sequence[ProviderTransactionRef],
) -> LedgerReconciliationResult:
    """Plan deterministic inserts, updates, deletes, and pending replacements."""

    existing_by_provider: dict[tuple[str, str], StoredMoneyTransaction] = {}
    existing_by_fingerprint: dict[tuple[str, str, str], StoredMoneyTransaction] = {}
    pending_by_provider: dict[tuple[str, str], StoredMoneyTransaction] = {}

    for stored in sorted(existing, key=_transaction_sort_key):
        provider_key = _provider_key(stored)
        if provider_key is not None:
            prior = existing_by_provider.get(provider_key)
            if prior is not None and prior.transaction_id != stored.transaction_id:
                raise ValueError("stored transactions share one provider identity")
            existing_by_provider[provider_key] = stored
            if stored.status is TransactionStatus.PENDING:
                pending_by_provider[provider_key] = stored

        fingerprint_key = _fingerprint_key(stored)
        prior_fingerprint = existing_by_fingerprint.get(fingerprint_key)
        if (
            prior_fingerprint is not None
            and prior_fingerprint.transaction_id != stored.transaction_id
        ):
            raise ValueError("stored transactions share one fallback identity")
        existing_by_fingerprint[fingerprint_key] = stored

    incoming_once = _coalesce_incoming(incoming)
    actions: list[LedgerAction] = []
    consumed_existing_ids = set()

    # Incremental feeds delete only records named by the provider. Absence from this
    # page is not deletion evidence.
    for reference in sorted(
        removed,
        key=lambda item: (item.source.value, item.provider_transaction_id),
    ):
        stored = existing_by_provider.get(_provider_key(reference))
        if stored is None or stored.transaction_id in consumed_existing_ids:
            continue
        actions.append(
            LedgerAction(
                kind=LedgerActionKind.DELETE,
                existing_transaction_id=stored.transaction_id,
                transaction=None,
                detail="Provider explicitly removed this transaction",
            )
        )
        consumed_existing_ids.add(stored.transaction_id)

    for transaction in incoming_once:
        pending_id = transaction.pending_provider_transaction_id
        if transaction.status is TransactionStatus.POSTED and pending_id:
            pending_key = (transaction.source.value, pending_id.strip())
            pending = pending_by_provider.get(pending_key)
            if pending is not None and pending.transaction_id not in consumed_existing_ids:
                actions.append(
                    LedgerAction(
                        kind=LedgerActionKind.REPLACE_PENDING,
                        existing_transaction_id=pending.transaction_id,
                        transaction=transaction,
                        detail="Posted transaction replaces its pending predecessor",
                    )
                )
                consumed_existing_ids.add(pending.transaction_id)
                continue

        provider_key = _provider_key(transaction)
        stored = existing_by_provider.get(provider_key) if provider_key is not None else None
        if stored is None:
            stored = existing_by_fingerprint.get(_fingerprint_key(transaction))

        if stored is None:
            actions.append(
                LedgerAction(
                    kind=LedgerActionKind.INSERT,
                    existing_transaction_id=None,
                    transaction=transaction,
                    detail="No stored transaction matched this identity",
                )
            )
            continue

        if stored.transaction_id in consumed_existing_ids:
            # Explicit removal/replacement wins. The provider may repeat the row in
            # the same page, but one stored record must receive at most one action.
            continue

        unchanged = _canonical_values(stored) == _canonical_values(transaction)
        actions.append(
            LedgerAction(
                kind=LedgerActionKind.UNCHANGED if unchanged else LedgerActionKind.UPDATE,
                existing_transaction_id=stored.transaction_id,
                transaction=transaction,
                detail=(
                    "Stored and incoming canonical values are identical"
                    if unchanged
                    else "Incoming canonical values changed"
                ),
            )
        )
        consumed_existing_ids.add(stored.transaction_id)

    return LedgerReconciliationResult(actions=tuple(sorted(actions, key=_action_sort_key)))
