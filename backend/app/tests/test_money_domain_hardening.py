from dataclasses import replace
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.money.enums import (
    LedgerActionKind,
    RecurrenceFrequency,
    SpendingTreatment,
    TransactionDirection,
    TransactionRejectionReason,
    TransactionStatus,
)
from app.money.models import RecurringPolicy, SpendingPolicy
from app.money.normalize import normalize_transactions
from app.money.reconcile import reconcile_ledger
from app.money.recurring import detect_recurring_transactions
from app.money.spending import summarize_weekly_spending
from app.tests.user_owned.factories import NOW
from app.tests.user_owned.money_factories import (
    normalized_transaction,
    recurring_charge,
    resolve_money_account,
    stored_money_transaction,
    transaction_observation,
)


@pytest.mark.parametrize("amount", (Decimal("NaN"), Decimal("Infinity")))
def test_non_finite_amount_is_rejected(amount: Decimal) -> None:
    result = normalize_transactions(
        (replace(transaction_observation(), amount=amount),),
        resolve_account=resolve_money_account,
    )

    assert result.rejected[0].reason is TransactionRejectionReason.INVALID_AMOUNT


def test_normalization_trims_provider_identity_and_uses_utc() -> None:
    eastern = datetime(2026, 7, 22, 8, tzinfo=timezone(timedelta(hours=-4)))
    observation = replace(
        transaction_observation(),
        provider_transaction_id=" tx-coffee ",
        authorized_at=eastern,
        posted_at=eastern,
    )

    result = normalize_transactions((observation,), resolve_account=resolve_money_account)
    transaction = result.transactions[0]

    assert transaction.provider_transaction_id == "tx-coffee"
    assert transaction.occurred_at.tzinfo is UTC
    assert transaction.occurred_at.hour == 12


def test_incremental_absence_never_deletes_a_stored_transaction() -> None:
    result = reconcile_ledger(
        incoming=(),
        existing=(stored_money_transaction(),),
        removed=(),
    )

    assert result.actions == ()


def test_identical_incoming_duplicates_are_coalesced() -> None:
    transaction = normalized_transaction()
    result = reconcile_ledger(incoming=(transaction, transaction), existing=(), removed=())

    assert len(result.actions) == 1
    assert result.actions[0].kind is LedgerActionKind.INSERT


def test_conflicting_incoming_identity_is_rejected() -> None:
    first = normalized_transaction()
    second = replace(first, amount=Decimal("99.00"))

    with pytest.raises(ValueError, match="conflicting incoming"):
        reconcile_ledger(incoming=(first, second), existing=(), removed=())


def test_pending_record_does_not_replace_another_pending_record() -> None:
    stored = stored_money_transaction(
        "pending-existing",
        provider_transaction_id="pending-1",
        status=TransactionStatus.PENDING,
        posted_at=None,
    )
    incoming = replace(
        normalized_transaction("pending-new"),
        status=TransactionStatus.PENDING,
        posted_at=None,
        pending_provider_transaction_id="pending-1",
    )

    result = reconcile_ledger(incoming=(incoming,), existing=(stored,), removed=())

    assert result.actions[0].kind is LedgerActionKind.INSERT


def test_same_account_movements_are_not_internal_transfers() -> None:
    outflow = stored_money_transaction(
        "same-account-out",
        category_primary="TRANSFER_OUT",
        amount=Decimal("100"),
    )
    inflow = stored_money_transaction(
        "same-account-in",
        direction=TransactionDirection.INFLOW,
        category_primary="TRANSFER_IN",
        amount=Decimal("100"),
    )

    result = summarize_weekly_spending(
        (outflow, inflow),
        period_start=NOW - timedelta(days=1),
        period_end=NOW + timedelta(days=1),
    )

    assert SpendingTreatment.INTERNAL_TRANSFER not in {
        decision.treatment for decision in result.decisions
    }


def test_custom_spending_categories_are_case_insensitive() -> None:
    payment = stored_money_transaction("payment", category_primary="CARD_SETTLEMENT")
    policy = SpendingPolicy(credit_card_payment_categories=frozenset({"card_settlement"}))

    result = summarize_weekly_spending(
        (payment,),
        period_start=NOW - timedelta(days=1),
        period_end=NOW + timedelta(days=1),
        policy=policy,
    )

    assert result.decisions[0].treatment is SpendingTreatment.CREDIT_CARD_PAYMENT


def test_weekly_recurring_stream_is_detected() -> None:
    transactions = tuple(
        recurring_charge("weekly", days_ago=days, merchant="Saturday Market")
        for days in (22, 15, 8, 1)
    )

    result = detect_recurring_transactions(transactions, as_of=NOW)

    assert result.streams[0].frequency is RecurrenceFrequency.WEEKLY


def test_future_recurring_evidence_is_ignored() -> None:
    history = [
        recurring_charge("future", days_ago=61),
        recurring_charge("future", days_ago=31),
    ]
    future = replace(recurring_charge("future", days_ago=1), occurred_at=NOW + timedelta(days=1))

    result = detect_recurring_transactions((*history, future), as_of=NOW)

    assert result.streams == ()


def test_recurring_policy_and_as_of_are_validated() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        detect_recurring_transactions((), as_of=datetime(2026, 7, 22))
    with pytest.raises(ValueError, match="minimum_occurrences"):
        detect_recurring_transactions(
            (),
            as_of=NOW,
            policy=RecurringPolicy(minimum_occurrences=1),
        )
