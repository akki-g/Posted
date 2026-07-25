from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import uuid4

import structlog

from app.domain.enums import AssetType
from app.domain.models import PositionObservation
from app.services.brokerage_sync import PositionMetrics, RawBrokerageAccount

logger = structlog.get_logger()

ASSET_TYPES = {
    "equity": AssetType.EQUITY,
    "etf": AssetType.ETF,
    "mutual fund": AssetType.MUTUAL_FUND,
    "fixed income": AssetType.FIXED_INCOME,
    "cash": AssetType.CASH,
    "derivative": AssetType.OPTION,
}

ZERO = Decimal("0")


def _decimal(value: object) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def map_plaid_investment_accounts(
    payload: dict[str, Any], *, observed_at: datetime | None = None
) -> tuple[RawBrokerageAccount, ...]:
    observed_at = observed_at or datetime.now(UTC)
    if observed_at.tzinfo is None or observed_at.utcoffset() is None:
        raise ValueError("observed_at must be timezone-aware")
    observed_at = observed_at.astimezone(UTC)

    securities = {
        str(s.get("security_id")): s
        for s in payload.get("securities") or []
        if s.get("security_id")
    }
    holdings_by_account: dict[str, list[dict[str, Any]]] = {}
    for holding in payload.get("holdings") or []:
        account_id = str(holding.get("account_id") or "")
        if account_id:
            holdings_by_account.setdefault(account_id, []).append(holding)

    result: list[RawBrokerageAccount] = []
    for raw_account in payload.get("accounts") or []:
        provider_account_id = str(raw_account.get("account_id") or "")
        if not provider_account_id:
            continue
        placeholder = uuid4()
        balances = raw_account.get("balances") or {}
        balance = _decimal(balances.get("current")) or ZERO
        positions: list[PositionObservation] = []
        security_names: dict[str, str] = {}
        metrics: dict[str, PositionMetrics] = {}
        account_total_gain = ZERO
        for holding in holdings_by_account.get(provider_account_id, []):
            security = securities.get(str(holding.get("security_id")))
            if security is None:
                continue
            symbol = (
                str(security["ticker_symbol"]).strip().upper()
                if security.get("ticker_symbol")
                else None
            )
            raw_type = str(security.get("type") or "").strip().lower()
            asset_type = ASSET_TYPES.get(raw_type, AssetType.UNKNOWN)
            if asset_type is AssetType.UNKNOWN and raw_type:
                logger.warning(
                    "plaid_investments_unmapped_asset_type",
                    symbol=symbol, raw_asset_type=raw_type,
                )
            quantity = _decimal(holding.get("quantity")) or ZERO
            market_value = _decimal(holding.get("institution_value"))
            cost_basis = _decimal(holding.get("cost_basis"))
            total_gain = (
                (market_value - cost_basis)
                if market_value is not None and cost_basis is not None
                else ZERO
            )
            positions.append(
                PositionObservation(
                    account_id=placeholder, observed_at=observed_at,
                    provider_instrument_id=str(security.get("security_id")) or None,
                    symbol=symbol, cusip=(
                        str(security["cusip"]).strip().upper() if security.get("cusip") else None
                    ),
                    asset_type=asset_type, quantity=quantity,
                    market_value=market_value,
                    average_price=_decimal(holding.get("institution_price")),
                )
            )
            if symbol:
                security_names[symbol] = str(security.get("name") or symbol)
                metrics[symbol] = PositionMetrics(day_change=ZERO, total_gain=total_gain)
                account_total_gain += total_gain
        result.append(
            RawBrokerageAccount(
                provider_account_id=provider_account_id,
                display_name=str(raw_account.get("name") or "Brokerage account"),
                account_type=str(
                    raw_account.get("subtype") or raw_account.get("type") or "investment"
                ),
                balance=balance, day_change=ZERO, total_gain=account_total_gain,
                positions=tuple(positions), security_names=security_names, metrics=metrics,
            )
        )
    return tuple(result)
