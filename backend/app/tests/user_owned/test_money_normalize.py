from dataclasses import replace
from datetime import datetime
from decimal import Decimal

import pytest

from app.money.enums import TransactionRejectionReason
from app.money.normalize import normalize_transactions
from app.tests.user_owned.money_factories import (
    resolve_money_account,
    transaction_observation,
)

pytestmark = pytest.mark.user_owned


def test_valid_transaction_is_canonicalized() -> None:
    result = normalize_transactions(
        [transaction_observation()], resolve_account=resolve_money_account
    )

    assert result.rejected == ()
    assert len(result.transactions) == 1
    transaction = result.transactions[0]
    assert transaction.amount == Decimal("6.50")
    assert transaction.currency == "USD"
    assert transaction.merchant_name == "Northstar Coffee"
    assert transaction.occurred_at.tzinfo is not None
    assert transaction.fingerprint


@pytest.mark.parametrize("amount", ["0", "-1.00"])
def test_non_positive_amount_is_rejected(amount: str) -> None:
    result = normalize_transactions(
        [transaction_observation(amount=amount)],
        resolve_account=resolve_money_account,
    )

    assert result.transactions == ()
    assert result.rejected[0].reason is TransactionRejectionReason.INVALID_AMOUNT


def test_naive_or_missing_timestamp_is_rejected() -> None:
    naive = transaction_observation(occurred_at=datetime(2026, 7, 22, 12))
    missing = replace(naive, authorized_at=None, posted_at=None)

    result = normalize_transactions([naive, missing], resolve_account=resolve_money_account)

    assert result.transactions == ()
    assert {rejection.reason for rejection in result.rejected} == {
        TransactionRejectionReason.INVALID_TIMESTAMP
    }


def test_unknown_account_is_rejected() -> None:
    result = normalize_transactions(
        [transaction_observation(account="missing-account")],
        resolve_account=resolve_money_account,
    )

    assert result.transactions == ()
    assert result.rejected[0].reason is TransactionRejectionReason.UNRESOLVED_ACCOUNT


def test_normalization_is_order_independent() -> None:
    coffee = transaction_observation("coffee")
    groceries = transaction_observation("groceries", amount="84.21")

    forward = normalize_transactions([coffee, groceries], resolve_account=resolve_money_account)
    reverse = normalize_transactions([groceries, coffee], resolve_account=resolve_money_account)

    assert forward == reverse
