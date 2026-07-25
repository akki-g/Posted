"""Human-owned cash-flow classification exercise.

Implementation contract: guides/08-SPENDING-CLASSIFICATION.md.
The coding agent must not implement or replace this module unless explicitly asked.
"""

from collections import defaultdict
from collections.abc import Collection, Sequence
from dataclasses import replace
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from app.money.enums import SpendingTreatment, TransactionDirection, TransactionStatus
from app.money.models import (
    CategorySpend,
    SpendingDecision,
    SpendingPolicy,
    StoredMoneyTransaction,
    WeeklySpendingSummary,
)


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


def _normalized_values(values: Collection[str]) -> frozenset[str]:
    """Normalize caller-supplied policy categories once per summary."""

    return frozenset(value.strip().upper() for value in values if value.strip())


def _match_internal_transfers(
    transactions: Sequence[StoredMoneyTransaction],
    *,
    period_start: datetime,
    period_end: datetime,
    policy: SpendingPolicy,
) -> set[UUID]:
    """Conservatively match equal and opposite movements between owned accounts."""

    if policy.transfer_window.total_seconds() < 0:
        raise ValueError("transfer_window must not be negative")

    eligible = tuple(
        sorted(
            (
                transaction
                for transaction in transactions
                if transaction.status is TransactionStatus.POSTED
                and period_start - policy.transfer_window
                <= transaction.occurred_at
                <= period_end + policy.transfer_window
            ),
            key=_transaction_sort_key,
        )
    )
    transfer_categories = policy.transfer_categories

    # Amount/currency buckets avoid comparing every transaction with every other
    # transaction while preserving the exact conservative matching rules.
    buckets: dict[tuple[str, Decimal], list[StoredMoneyTransaction]] = defaultdict(list)
    for transaction in eligible:
        buckets[(transaction.currency.strip().upper(), transaction.amount)].append(transaction)

    matched_ids: set[UUID] = set()
    for transaction in eligible:
        if transaction.transaction_id in matched_ids:
            continue

        category = _normalized_category(transaction)
        candidates: list[StoredMoneyTransaction] = []
        bucket = buckets[(transaction.currency.strip().upper(), transaction.amount)]
        for other in bucket:
            if other.transaction_id == transaction.transaction_id:
                continue
            if other.transaction_id in matched_ids:
                continue
            if other.account_id == transaction.account_id:
                continue
            if other.direction is transaction.direction:
                continue
            if abs(other.occurred_at - transaction.occurred_at) > policy.transfer_window:
                continue
            if (
                category not in transfer_categories
                and _normalized_category(other) not in transfer_categories
            ):
                continue
            candidates.append(other)

        if not candidates:
            continue

        match = min(
            candidates,
            key=lambda other: (
                abs((other.occurred_at - transaction.occurred_at).total_seconds()),
                _transaction_sort_key(other),
            ),
        )
        matched_ids.update((transaction.transaction_id, match.transaction_id))

    return matched_ids


def _treatment(
    transaction: StoredMoneyTransaction,
    *,
    transfer_ids: set[UUID],
    period_start: datetime,
    period_end: datetime,
    policy: SpendingPolicy,
) -> tuple[SpendingTreatment, str]:
    """Apply the first matching cash-flow classification rule."""

    if transaction.status is TransactionStatus.PENDING:
        return (SpendingTreatment.PENDING, "Transaction is still pending")
    if transaction.transaction_id in transfer_ids:
        # Transfer settlement commonly straddles a reporting boundary. Classify the
        # economic pair before the date exclusion so the in-period side is never spend.
        return (
            SpendingTreatment.INTERNAL_TRANSFER,
            "Matched an equal opposite account movement",
        )
    if not _in_period(transaction, period_start=period_start, period_end=period_end):
        return (SpendingTreatment.EXCLUDED, "Transaction is outside the reporting period")

    category = _normalized_category(transaction)
    if category in policy.credit_card_payment_categories:
        return (
            SpendingTreatment.CREDIT_CARD_PAYMENT,
            "Credit-card payment is not new spending",
        )
    if category in policy.investment_categories:
        return (SpendingTreatment.INVESTMENT, "Investment movement is excluded from spending")
    if category in policy.refund_categories:
        return (SpendingTreatment.REFUND, "Refund is reported separately from income")
    if transaction.direction is TransactionDirection.INFLOW:
        return (SpendingTreatment.INCOME, "Posted non-transfer inflow counted as income")
    return (SpendingTreatment.SPENDING, "Posted outflow counted as consumer spending")


def summarize_weekly_spending(
    transactions: Sequence[StoredMoneyTransaction],
    *,
    period_start: datetime,
    period_end: datetime,
    policy: SpendingPolicy | None = None,
) -> WeeklySpendingSummary:
    """Classify ledger activity and total true spending without double counting transfers."""

    configured_policy = policy or SpendingPolicy()
    # Normalize policy collections once, not once per transaction. This keeps custom
    # configuration case-insensitive without adding work to the classification loop.
    active_policy = replace(
        configured_policy,
        transfer_categories=_normalized_values(configured_policy.transfer_categories),
        credit_card_payment_categories=_normalized_values(
            configured_policy.credit_card_payment_categories
        ),
        investment_categories=_normalized_values(configured_policy.investment_categories),
        refund_categories=_normalized_values(configured_policy.refund_categories),
    )
    ordered = tuple(sorted(transactions, key=_transaction_sort_key))
    _validate_period(ordered, period_start=period_start, period_end=period_end)
    transfer_ids = _match_internal_transfers(
        ordered,
        period_start=period_start,
        period_end=period_end,
        policy=active_policy,
    )

    zero = Decimal("0")
    total_spending = zero
    total_income = zero
    total_excluded = zero
    category_totals: dict[str, Decimal] = defaultdict(lambda: zero)
    decisions: list[SpendingDecision] = []

    for transaction in ordered:
        treatment, reason = _treatment(
            transaction,
            transfer_ids=transfer_ids,
            period_start=period_start,
            period_end=period_end,
            policy=active_policy,
        )
        decisions.append(
            SpendingDecision(
                transaction_id=transaction.transaction_id,
                treatment=treatment,
                reason=reason,
            )
        )

        if treatment is SpendingTreatment.SPENDING:
            total_spending += transaction.amount
            category_totals[_normalized_category(transaction)] += transaction.amount
        elif treatment is SpendingTreatment.INCOME:
            total_income += transaction.amount
        elif transaction.direction is TransactionDirection.OUTFLOW:
            total_excluded += transaction.amount

    categories = (
        CategorySpend(category=category, amount=amount)
        for category, amount in category_totals.items()
    )
    return WeeklySpendingSummary(
        period_start=period_start,
        period_end=period_end,
        total_spending=total_spending,
        total_income=total_income,
        total_excluded=total_excluded,
        by_category=tuple(sorted(categories, key=lambda item: (-item.amount, item.category))),
        decisions=tuple(decisions),
    )
