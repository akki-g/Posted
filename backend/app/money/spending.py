"""Human-owned cash-flow classification exercise.

Implementation contract: guides/08-SPENDING-CLASSIFICATION.md.
The coding agent must not implement or replace this module unless explicitly asked.
"""

from collections.abc import Sequence
from datetime import datetime

from app.money.models import SpendingPolicy, StoredMoneyTransaction, WeeklySpendingSummary


def _is_timezone_aware(value: datetime) -> bool:
    """Return whether a reporting timestamp identifies an actual UTC offset."""

    return value.tzinfo is not None and value.utcoffset() is not None


def _in_period(
    transaction: StoredMoneyTransaction,
    *,
    period_start: datetime,
    period_end: datetime,
) -> bool:
    """Apply the exercise's inclusive reporting-window rule."""

    return period_start <= transaction.occurred_at <= period_end


def _normalized_category(transaction: StoredMoneyTransaction) -> str:
    """Return the comparison/grouping form of a transaction's primary category."""

    normalized = transaction.category_primary.strip().upper()
    return normalized or "UNCATEGORIZED"


def _transaction_sort_key(transaction: StoredMoneyTransaction) -> tuple[str, str]:
    """Return a stable order for transfer matching and spending decisions."""

    return (transaction.occurred_at.isoformat(), str(transaction.transaction_id))


def _validate_period(
    transactions: Sequence[StoredMoneyTransaction],
    *,
    period_start: datetime,
    period_end: datetime,
) -> None:
    """Validate aware, ordered reporting boundaries and transaction timestamps."""

    if not _is_timezone_aware(period_start) or not _is_timezone_aware(period_end):
        raise ValueError("reporting boundaries must be timezone-aware")
    if period_start > period_end:
        raise ValueError("period_start must not be after period_end")
    if any(not _is_timezone_aware(item.occurred_at) for item in transactions):
        raise ValueError("transaction occurrence times must be timezone-aware")


def summarize_weekly_spending(
    transactions: Sequence[StoredMoneyTransaction],
    *,
    period_start: datetime,
    period_end: datetime,
    policy: SpendingPolicy | None = None,
) -> WeeklySpendingSummary:
    """Classify ledger activity and total true spending without double counting transfers."""
    raise NotImplementedError("Follow guides/08-SPENDING-CLASSIFICATION.md")
