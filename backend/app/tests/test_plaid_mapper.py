from decimal import Decimal

from app.money.enums import TransactionDirection, TransactionStatus
from app.providers.plaid.mapper import map_plaid_account_values, map_plaid_transaction


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


def test_map_plaid_account_values_maps_checking_account() -> None:
    raw = {
        "account_id": "plaid-checking-1",
        "name": "Plaid Checking",
        "official_name": "Plaid Gold Standard 0% Interest Checking",
        "type": "depository",
        "subtype": "checking",
        "mask": "0000",
        "balances": {
            "current": 1250.45,
            "available": 1200.00,
            "iso_currency_code": "USD",
        },
    }

    result = map_plaid_account_values(raw)

    assert result["account_type"] == "checking"
    assert result["subtype"] == "checking"
    assert result["current_balance"] == Decimal("1250.45")
    assert result["available_balance"] == Decimal("1200.00")
    assert result["currency"] == "USD"
    assert result["is_active"] is True


def test_map_plaid_account_values_maps_credit_card_with_limit() -> None:
    raw = {
        "account_id": "plaid-credit-1",
        "name": "Plaid Credit Card",
        "type": "credit",
        "subtype": "credit card",
        "balances": {"current": 400, "limit": 5000},
    }

    result = map_plaid_account_values(raw)

    assert result["account_type"] == "credit_card"
    assert result["credit_limit"] == Decimal("5000")


def test_map_plaid_account_values_defaults_unknown_type_to_other() -> None:
    raw = {"account_id": "plaid-loan-1", "type": "investment", "balances": {}}

    result = map_plaid_account_values(raw)

    assert result["account_type"] == "other"
    assert result["current_balance"] == Decimal("0")
    assert result["currency"] == "USD"
