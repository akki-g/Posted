from dataclasses import replace
from decimal import Decimal

import pytest

from app.money.enums import RecurrenceFrequency, TransactionDirection, TransactionStatus
from app.money.recurring import detect_recurring_transactions
from app.tests.user_owned.factories import NOW
from app.tests.user_owned.money_factories import recurring_charge

pytestmark = pytest.mark.user_owned


def test_three_regular_monthly_charges_form_a_stream() -> None:
    transactions = [
        recurring_charge("streambox", days_ago=61),
        recurring_charge("streambox", days_ago=31),
        recurring_charge("streambox", days_ago=1),
    ]

    result = detect_recurring_transactions(transactions, as_of=NOW)

    assert len(result.streams) == 1
    stream = result.streams[0]
    assert stream.merchant_name == "Streambox"
    assert stream.frequency is RecurrenceFrequency.MONTHLY
    assert stream.average_amount == Decimal("14.99")
    assert stream.last_amount == Decimal("14.99")
    assert stream.next_expected_date > NOW.date()
    assert 0 <= stream.confidence <= 1


def test_two_charges_are_not_enough_evidence() -> None:
    transactions = [
        recurring_charge("streambox", days_ago=31),
        recurring_charge("streambox", days_ago=1),
    ]

    result = detect_recurring_transactions(transactions, as_of=NOW)

    assert result.streams == ()


def test_large_amount_variation_rejects_candidate() -> None:
    transactions = [
        recurring_charge("streambox", days_ago=61, amount="10.00"),
        recurring_charge("streambox", days_ago=31, amount="10.00"),
        recurring_charge("streambox", days_ago=1, amount="30.00"),
    ]

    result = detect_recurring_transactions(transactions, as_of=NOW)

    assert result.streams == ()


def test_pending_and_inflow_transactions_are_ignored() -> None:
    base = [
        recurring_charge("streambox", days_ago=61),
        recurring_charge("streambox", days_ago=31),
        recurring_charge("streambox", days_ago=1),
    ]
    ignored = [
        replace(base[0], status=TransactionStatus.PENDING, posted_at=None),
        replace(base[1], direction=TransactionDirection.INFLOW),
        replace(base[2], status=TransactionStatus.PENDING, posted_at=None),
    ]

    result = detect_recurring_transactions(ignored, as_of=NOW)

    assert result.streams == ()


def test_detection_is_order_independent() -> None:
    transactions = [
        recurring_charge("streambox", days_ago=61),
        recurring_charge("streambox", days_ago=31),
        recurring_charge("streambox", days_ago=1),
    ]

    forward = detect_recurring_transactions(transactions, as_of=NOW)
    reverse = detect_recurring_transactions(list(reversed(transactions)), as_of=NOW)

    assert forward == reverse
