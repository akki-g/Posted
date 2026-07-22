from decimal import Decimal

from app.money.enums import TransactionDirection, TransactionStatus
from app.providers.plaid.mapper import map_plaid_transaction


def plaid_transaction(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "transaction_id": "plaid-transaction-1",
        "account_id": "plaid-account-1",
        "pending_transaction_id": None,
        "pending": False,
        "amount": 42.15,
        "iso_currency_code": "USD",
        "merchant_name": "Greenway Market",
        "name": "GREENWAY MARKET 104",
        "authorized_date": "2026-07-20",
        "date": "2026-07-21",
        "personal_finance_category": {
            "primary": "FOOD_AND_DRINK",
            "detailed": "FOOD_AND_DRINK_GROCERIES",
        },
        "payment_channel": "in store",
    }
    values.update(overrides)
    return values


def test_plaid_positive_amount_maps_to_outflow() -> None:
    result = map_plaid_transaction(plaid_transaction())

    assert result.direction is TransactionDirection.OUTFLOW
    assert result.amount == Decimal("42.15")
    assert result.status is TransactionStatus.POSTED
    assert result.authorized_at is not None
    assert result.authorized_at.tzinfo is not None
    assert result.category_primary == "FOOD_AND_DRINK"


def test_plaid_negative_amount_maps_to_inflow() -> None:
    result = map_plaid_transaction(plaid_transaction(amount=-3250, merchant_name="Acme Payroll"))

    assert result.direction is TransactionDirection.INFLOW
    assert result.amount == Decimal("3250")


def test_pending_transaction_has_no_posted_time() -> None:
    result = map_plaid_transaction(
        plaid_transaction(
            pending=True,
            pending_transaction_id="pending-previous",
        )
    )

    assert result.status is TransactionStatus.PENDING
    assert result.posted_at is None
    assert result.pending_provider_transaction_id == "pending-previous"
