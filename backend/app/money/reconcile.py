"""Human-owned incremental-ledger reconciliation exercise.

Implementation contract: guides/07-LEDGER-RECONCILIATION.md.
The coding agent must not implement or replace this module unless explicitly asked.
"""

from collections.abc import Sequence

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
    if provider_id is None:
        return None
    return (transaction.source.value, provider_id)


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


def reconcile_ledger(
    *,
    incoming: Sequence[NormalizedTransaction],
    existing: Sequence[StoredMoneyTransaction],
    removed: Sequence[ProviderTransactionRef],
) -> LedgerReconciliationResult:
    """Plan deterministic inserts, updates, deletes, and pending replacements."""
    raise NotImplementedError("Follow guides/07-LEDGER-RECONCILIATION.md")
