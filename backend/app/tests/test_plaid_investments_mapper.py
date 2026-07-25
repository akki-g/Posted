from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest

from app.domain.enums import AssetType
from app.providers.plaid_investments.mapper import map_plaid_investment_accounts

OBSERVED = datetime(2026, 7, 25, 12, tzinfo=UTC)


def _payload() -> dict:
    return {
        "accounts": [
            {"account_id": "acc-1", "name": "Robinhood Individual",
             "type": "investment", "subtype": "brokerage",
             "balances": {"current": 15230.55, "iso_currency_code": "USD"}},
        ],
        "securities": [
            {"security_id": "sec-aapl", "ticker_symbol": "AAPL", "name": "Apple Inc.",
             "type": "equity", "close_price": 190.0},
            {"security_id": "sec-crypto", "ticker_symbol": "BTC", "name": "Bitcoin",
             "type": "cryptocurrency", "close_price": 60000.0},
        ],
        "holdings": [
            {"account_id": "acc-1", "security_id": "sec-aapl", "quantity": 50,
             "institution_price": 190.0, "institution_value": 9500.0, "cost_basis": 8000.0},
            {"account_id": "acc-1", "security_id": "sec-crypto", "quantity": 0.1,
             "institution_price": 60000.0, "institution_value": 6000.0, "cost_basis": 5000.0},
        ],
    }


def test_maps_holdings_to_raw_brokerage_account() -> None:
    accounts = map_plaid_investment_accounts(_payload(), observed_at=OBSERVED)
    assert len(accounts) == 1
    account = accounts[0]
    assert account.provider_account_id == "acc-1"
    assert account.balance == Decimal("15230.55")
    equity = next(p for p in account.positions if p.symbol == "AAPL")
    assert equity.asset_type is AssetType.EQUITY
    assert equity.quantity == Decimal("50")
    assert equity.market_value == Decimal("9500.0")
    # total_gain = institution_value - cost_basis
    assert account.metrics["AAPL"].total_gain == Decimal("1500.0")
    assert account.metrics["AAPL"].day_change == Decimal("0")
    assert account.security_names["AAPL"] == "Apple Inc."


def test_unmapped_security_type_becomes_unknown() -> None:
    accounts = map_plaid_investment_accounts(_payload(), observed_at=OBSERVED)
    crypto = next(p for p in accounts[0].positions if p.symbol == "BTC")
    assert crypto.asset_type is AssetType.UNKNOWN


def _two_account_payload() -> dict:
    return {
        "accounts": [
            {"account_id": "acc-1", "name": "Robinhood Individual",
             "type": "investment", "subtype": "brokerage",
             "balances": {"current": 15230.55, "iso_currency_code": "USD"}},
            {"account_id": "acc-2", "name": "Fidelity IRA",
             "type": "investment", "subtype": "ira",
             "balances": {"current": 5000.0, "iso_currency_code": "USD"}},
        ],
        "securities": [
            {"security_id": "sec-aapl", "ticker_symbol": "AAPL", "name": "Apple Inc.",
             "type": "equity", "close_price": 190.0},
            {"security_id": "sec-msft", "ticker_symbol": "MSFT", "name": "Microsoft Corp.",
             "type": "equity", "close_price": 420.0},
            {"security_id": "sec-voo", "ticker_symbol": "VOO", "name": "Vanguard S&P 500 ETF",
             "type": "etf", "close_price": 470.0},
            {"security_id": "sec-vti", "ticker_symbol": "VTI", "name": "Vanguard Total Stock",
             "type": "etf", "close_price": 260.0},
        ],
        "holdings": [
            {"account_id": "acc-1", "security_id": "sec-aapl", "quantity": 50,
             "institution_price": 190.0, "institution_value": 9500.0, "cost_basis": 8000.0},
            {"account_id": "acc-1", "security_id": "sec-msft", "quantity": 10,
             "institution_price": 420.0, "institution_value": 4200.0, "cost_basis": 4000.0},
            {"account_id": "acc-2", "security_id": "sec-voo", "quantity": 5,
             "institution_price": 470.0, "institution_value": 2350.0, "cost_basis": 2000.0},
            {"account_id": "acc-2", "security_id": "sec-vti", "quantity": 8,
             "institution_price": 260.0, "institution_value": 2080.0, "cost_basis": 1900.0},
        ],
    }


def test_position_account_id_is_a_distinct_per_account_uuid_placeholder() -> None:
    accounts = map_plaid_investment_accounts(_two_account_payload(), observed_at=OBSERVED)
    assert len(accounts) == 2
    account1 = next(a for a in accounts if a.provider_account_id == "acc-1")
    account2 = next(a for a in accounts if a.provider_account_id == "acc-2")

    assert len(account1.positions) == 2
    assert len(account2.positions) == 2

    # Every position within one account shares the same placeholder uuid.
    account1_ids = {p.account_id for p in account1.positions}
    account2_ids = {p.account_id for p in account2.positions}
    assert len(account1_ids) == 1
    assert len(account2_ids) == 1

    account1_id = account1_ids.pop()
    account2_id = account2_ids.pop()

    # It's a genuine uuid4, not a sentinel or something derived from the
    # provider_account_id string.
    assert isinstance(account1_id, UUID)
    assert isinstance(account2_id, UUID)
    assert account1_id.version == 4
    assert account2_id.version == 4
    assert account1_id != UUID(int=0)
    assert account2_id != UUID(int=0)

    # The two accounts get different placeholders (per-account, not global).
    assert account1_id != account2_id

    # No leakage of positions/metrics/security_names across accounts.
    assert {p.symbol for p in account1.positions} == {"AAPL", "MSFT"}
    assert {p.symbol for p in account2.positions} == {"VOO", "VTI"}
    assert set(account1.security_names) == {"AAPL", "MSFT"}
    assert set(account2.security_names) == {"VOO", "VTI"}
    assert set(account1.metrics) == {"AAPL", "MSFT"}
    assert set(account2.metrics) == {"VOO", "VTI"}


def test_naive_observed_at_is_rejected() -> None:
    naive = datetime(2026, 7, 25, 12)  # noqa: DTZ001 - intentionally naive for this test
    with pytest.raises(ValueError, match="observed_at must be timezone-aware"):
        map_plaid_investment_accounts(_payload(), observed_at=naive)
