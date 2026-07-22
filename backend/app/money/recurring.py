"""Human-owned recurring-charge detection exercise.

Implementation contract: guides/09-RECURRING-TRANSACTIONS.md.
The coding agent must not implement or replace this module unless explicitly asked.
"""

from collections.abc import Mapping, Sequence
from datetime import date, datetime, timedelta
from decimal import Decimal
from hashlib import sha256
from statistics import median

from app.money.enums import RecurrenceFrequency
from app.money.models import (
    RecurringDetectionResult,
    RecurringPolicy,
    RecurringStreamCandidate,
    StoredMoneyTransaction,
)

_DEFAULT_FREQUENCY_WINDOWS: Mapping[RecurrenceFrequency, tuple[int, int]] = {
    RecurrenceFrequency.WEEKLY: (5, 9),
    RecurrenceFrequency.BIWEEKLY: (12, 16),
    RecurrenceFrequency.MONTHLY: (25, 35),
    RecurrenceFrequency.QUARTERLY: (80, 100),
    RecurrenceFrequency.ANNUAL: (350, 380),
}


def _merchant_key(value: str) -> str:
    """Return the conservative grouping form of a merchant name."""

    return " ".join(value.split()).casefold()


def _frequency_windows(
    policy: RecurringPolicy,
) -> Mapping[RecurrenceFrequency, tuple[int, int]]:
    """Return custom cadence windows when supplied, otherwise documented defaults."""

    if policy.frequency_windows is not None:
        return policy.frequency_windows
    return _DEFAULT_FREQUENCY_WINDOWS


def _amount_variation(amounts: Sequence[Decimal]) -> Decimal:
    """Return exact range-over-average variation for a non-empty amount sequence."""

    if not amounts:
        raise ValueError("amount variation requires at least one amount")
    average = sum(amounts, Decimal("0")) / len(amounts)
    if average == 0:
        return Decimal("Infinity")
    return (max(amounts) - min(amounts)) / average


def _representative_gap(gaps: Sequence[int]) -> int:
    """Return a positive integer median cadence from a non-empty gap sequence."""

    if not gaps:
        raise ValueError("representative gap requires at least one gap")
    result = round(median(gaps))
    if result <= 0:
        raise ValueError("recurrence gaps must be positive")
    return result


def _next_expected_date(last_charged_at: datetime, gap_days: int, as_of: date) -> date:
    """Advance a representative cadence until the prediction is in the future."""

    if gap_days <= 0:
        raise ValueError("gap_days must be positive")
    predicted = last_charged_at.date() + timedelta(days=gap_days)
    while predicted <= as_of:
        predicted += timedelta(days=gap_days)
    return predicted


def _stream_key(
    merchant_key: str,
    currency: str,
    frequency: RecurrenceFrequency,
) -> str:
    """Create a durable recurring-stream identity without using Python hash()."""

    seed = f"{merchant_key}|{currency}|{frequency.value}"
    return sha256(seed.encode("utf-8")).hexdigest()


def _stream_sort_key(stream: RecurringStreamCandidate) -> tuple[str, str]:
    """Return the documented deterministic result order."""

    return (stream.next_expected_date.isoformat(), stream.stream_key)


def detect_recurring_transactions(
    transactions: Sequence[StoredMoneyTransaction],
    *,
    as_of: datetime,
    policy: RecurringPolicy | None = None,
) -> RecurringDetectionResult:
    """Infer explainable recurring outflow streams from posted ledger history."""
    raise NotImplementedError("Follow guides/09-RECURRING-TRANSACTIONS.md")
