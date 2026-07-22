from datetime import timedelta
from decimal import Decimal

import pytest

from app.money.enums import SpendingTreatment, TransactionDirection, TransactionStatus
from app.money.spending import summarize_weekly_spending
from app.tests.user_owned.factories import NOW
from app.tests.user_owned.money_factories import MONEY_ACCOUNTS, stored_money_transaction

pytestmark = pytest.mark.user_owned


def summarize(*transactions: object):
    return summarize_weekly_spending(
        transactions,  # type: ignore[arg-type]
        period_start=NOW - timedelta(days=7),
        period_end=NOW,
    )


def test_posted_purchase_counts_as_spending() -> None:
    transaction = stored_money_transaction(
        "groceries", amount=Decimal("84.21"), category_primary="GROCERIES"
    )

    result = summarize(transaction)

    assert result.total_spending == Decimal("84.21")
    assert result.by_category[0].category == "GROCERIES"
    assert result.by_category[0].amount == Decimal("84.21")
    assert result.decisions[0].treatment is SpendingTreatment.SPENDING


def test_pending_transaction_is_excluded() -> None:
    transaction = stored_money_transaction(
        "pending", status=TransactionStatus.PENDING, posted_at=None
    )

    result = summarize(transaction)

    assert result.total_spending == 0
    assert result.decisions[0].treatment is SpendingTreatment.PENDING


def test_income_is_reported_separately() -> None:
    paycheck = stored_money_transaction(
        "paycheck",
        amount=Decimal("3250.00"),
        direction=TransactionDirection.INFLOW,
        category_primary="INCOME",
    )

    result = summarize(paycheck)

    assert result.total_income == Decimal("3250.00")
    assert result.total_spending == 0
    assert result.decisions[0].treatment is SpendingTreatment.INCOME


def test_matching_account_movements_are_internal_transfer() -> None:
    checking_out = stored_money_transaction(
        "card-payment-out",
        amount=Decimal("500.00"),
        category_primary="TRANSFER_OUT",
    )
    credit_in = stored_money_transaction(
        "card-payment-in",
        account_id=MONEY_ACCOUNTS["plaid-credit"].account_id,
        amount=Decimal("500.00"),
        direction=TransactionDirection.INFLOW,
        occurred_at=checking_out.occurred_at + timedelta(days=1),
        posted_at=checking_out.posted_at + timedelta(days=1),  # type: ignore[operator]
        category_primary="TRANSFER_IN",
    )

    result = summarize(checking_out, credit_in)

    assert result.total_spending == 0
    assert {decision.treatment for decision in result.decisions} == {
        SpendingTreatment.INTERNAL_TRANSFER
    }


def test_credit_card_payment_is_not_spending() -> None:
    payment = stored_money_transaction(
        "credit-payment",
        amount=Decimal("220.00"),
        category_primary="CREDIT_CARD_PAYMENT",
    )

    result = summarize(payment)

    assert result.total_spending == 0
    assert result.decisions[0].treatment is SpendingTreatment.CREDIT_CARD_PAYMENT


def test_summary_is_order_independent() -> None:
    coffee = stored_money_transaction("coffee", amount=Decimal("6.50"))
    groceries = stored_money_transaction(
        "groceries", amount=Decimal("84.21"), category_primary="GROCERIES"
    )

    assert summarize(coffee, groceries) == summarize(groceries, coffee)
