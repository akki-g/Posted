"""Human-owned recurring-charge detection exercise.

Implementation contract: guides/09-RECURRING-TRANSACTIONS.md.
The coding agent must not implement or replace this module unless explicitly asked.
"""

from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import date, datetime, timedelta
from decimal import Decimal
from hashlib import sha256
from statistics import median

from app.money.enums import (
    RecurrenceFrequency,
    TransactionDirection,
    TransactionStatus,
)
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


def _is_timezone_aware(value: datetime) -> bool:
    """Return whether a datetime carries a usable UTC offset."""

    return value.tzinfo is not None and value.utcoffset() is not None


def _usable(transaction: StoredMoneyTransaction, as_of: datetime) -> bool:
    """Return whether a ledger record is stable evidence for an outflow cadence."""

    return (
        transaction.status is TransactionStatus.POSTED
        and transaction.direction is TransactionDirection.OUTFLOW
        and transaction.amount.is_finite()
        and transaction.amount > Decimal("0")
        and _is_timezone_aware(transaction.occurred_at)
        and transaction.occurred_at <= as_of
        and bool(_merchant_key(transaction.merchant_name))
        and bool(transaction.currency.strip())
    )


def _detect_frequency(
    gaps: Sequence[int],
    policy: RecurringPolicy,
) -> RecurrenceFrequency | None:
    """Choose the deterministic cadence whose inclusive window contains every gap."""

    windows = _frequency_windows(policy)
    for frequency in sorted(RecurrenceFrequency, key=lambda item: item.value):
        if frequency not in windows:
            continue
        minimum_days, maximum_days = windows[frequency]
        if minimum_days <= 0 or minimum_days > maximum_days:
            raise ValueError(f"invalid recurrence window for {frequency.value}")
        if gaps and all(minimum_days <= gap <= maximum_days for gap in gaps):
            return frequency
    return None


def _confidence(
    *,
    occurrence_count: int,
    gaps: Sequence[int],
    representative_gap: int,
    amount_variation: Decimal,
    policy: RecurringPolicy,
    last_charged_at: datetime,
    as_of: datetime,
) -> float:
    """Score timing, amount stability, recency, and additional observations."""

    gap_spread = max(gaps) - min(gaps)
    timing_consistency = max(0.0, 1.0 - gap_spread / representative_gap)
    if policy.maximum_amount_variation == Decimal("0"):
        amount_consistency = 1.0 if amount_variation == 0 else 0.0
    else:
        amount_consistency = max(
            0.0,
            1.0 - float(amount_variation / policy.maximum_amount_variation),
        )

    first_prediction = last_charged_at.date() + timedelta(days=representative_gap)
    overdue_days = max(0, (as_of.date() - first_prediction).days)
    overdue_cycles = overdue_days / representative_gap
    recency = max(0.0, 1.0 - 0.25 * overdue_cycles)
    extra_evidence = min(0.25, 0.05 * (occurrence_count - policy.minimum_occurrences))
    raw = 0.45 * timing_consistency + 0.35 * amount_consistency + 0.20 * recency + extra_evidence
    return max(0.0, min(1.0, raw))


def detect_recurring_transactions(
    transactions: Sequence[StoredMoneyTransaction],
    *,
    as_of: datetime,
    policy: RecurringPolicy | None = None,
) -> RecurringDetectionResult:
    """Infer explainable recurring outflow streams from posted ledger history."""

    if not _is_timezone_aware(as_of):
        raise ValueError("as_of must be timezone-aware")

    active_policy = policy or RecurringPolicy()
    if active_policy.minimum_occurrences < 2:
        raise ValueError("minimum_occurrences must be at least two")
    if active_policy.maximum_amount_variation < Decimal("0"):
        raise ValueError("maximum_amount_variation must not be negative")

    # Validate custom windows even when this particular batch has no candidate using
    # them; bad configuration should fail predictably rather than data-dependently.
    for frequency, (minimum_days, maximum_days) in _frequency_windows(active_policy).items():
        if minimum_days <= 0 or minimum_days > maximum_days:
            raise ValueError(f"invalid recurrence window for {frequency.value}")

    groups: dict[tuple[str, str], list[StoredMoneyTransaction]] = defaultdict(list)
    for transaction in transactions:
        if _usable(transaction, as_of):
            key = (
                _merchant_key(transaction.merchant_name),
                transaction.currency.strip().upper(),
            )
            groups[key].append(transaction)

    streams: list[RecurringStreamCandidate] = []
    for (merchant_key, currency), group in groups.items():
        ordered = tuple(
            sorted(
                group,
                key=lambda item: (item.occurred_at.isoformat(), str(item.transaction_id)),
            )
        )
        if len(ordered) < active_policy.minimum_occurrences:
            continue

        gaps = tuple(
            (current.occurred_at.date() - previous.occurred_at.date()).days
            for previous, current in zip(ordered, ordered[1:], strict=False)
        )
        frequency = _detect_frequency(gaps, active_policy)
        if frequency is None:
            continue

        amounts = tuple(item.amount for item in ordered)
        variation = _amount_variation(amounts)
        if variation > active_policy.maximum_amount_variation:
            continue

        average_amount = sum(amounts, Decimal("0")) / len(amounts)
        representative_gap = _representative_gap(gaps)
        last = ordered[-1]
        display_names = {" ".join(item.merchant_name.split()) for item in ordered}
        display_name = min(display_names, key=lambda value: (value.casefold(), value))

        streams.append(
            RecurringStreamCandidate(
                stream_key=_stream_key(merchant_key, currency, frequency),
                merchant_name=display_name,
                frequency=frequency,
                average_amount=average_amount,
                last_amount=last.amount,
                currency=currency,
                last_charged_at=last.occurred_at,
                next_expected_date=_next_expected_date(
                    last.occurred_at,
                    representative_gap,
                    as_of.date(),
                ),
                confidence=_confidence(
                    occurrence_count=len(ordered),
                    gaps=gaps,
                    representative_gap=representative_gap,
                    amount_variation=variation,
                    policy=active_policy,
                    last_charged_at=last.occurred_at,
                    as_of=as_of,
                ),
                transaction_ids=tuple(item.transaction_id for item in ordered),
            )
        )

    return RecurringDetectionResult(streams=tuple(sorted(streams, key=_stream_sort_key)))
