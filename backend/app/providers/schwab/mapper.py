from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

from app.domain.enums import AssetType
from app.domain.models import PositionObservation

ASSET_TYPES = {
    "EQUITY": AssetType.EQUITY,
    "ETF": AssetType.ETF,
    # Schwab's Trader API (inherited from TD Ameritrade) reports real ETF
    # holdings under this type, not "ETF" -- open-end mutual funds get their
    # own explicit "MUTUAL_FUND" type below, so this isn't ambiguous with them.
    "COLLECTIVE_INVESTMENT": AssetType.ETF,
    "MUTUAL_FUND": AssetType.MUTUAL_FUND,
    "OPTION": AssetType.OPTION,
    "FIXED_INCOME": AssetType.FIXED_INCOME,
    "CASH_EQUIVALENT": AssetType.CASH,
}


def _decimal(value: object) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def map_schwab_positions(
    account_payload: dict[str, Any],
    *,
    account_id: UUID,
    observed_at: datetime | None = None,
) -> tuple[PositionObservation, ...]:
    """Map one Schwab account object to provider-neutral observations."""
    observed_at = observed_at or datetime.now(UTC)
    if observed_at.tzinfo is None or observed_at.utcoffset() is None:
        raise ValueError("observed_at must be timezone-aware")
    observed_at = observed_at.astimezone(UTC)
    securities_account = account_payload.get("securitiesAccount", account_payload)
    raw_positions = securities_account.get("positions") or []
    if not isinstance(raw_positions, list):
        raise ValueError("Schwab positions must be a list")
    observations: list[PositionObservation] = []
    for raw_position in raw_positions:
        if not isinstance(raw_position, dict):
            raise ValueError("Schwab position must be an object")
        instrument = raw_position.get("instrument") or {}
        if not isinstance(instrument, dict):
            raise ValueError("Schwab position instrument must be an object")
        quantity = _decimal(raw_position.get("longQuantity"))
        short_quantity = _decimal(raw_position.get("shortQuantity")) or Decimal("0")
        if quantity is None:
            quantity = Decimal("0")
        quantity -= short_quantity
        asset_name = str(instrument.get("assetType") or "UNKNOWN").upper()
        observations.append(
            PositionObservation(
                account_id=account_id,
                observed_at=observed_at,
                provider_instrument_id=(
                    str(instrument["instrumentId"])
                    if instrument.get("instrumentId") is not None
                    else None
                ),
                symbol=(
                    str(instrument["symbol"]).strip().upper()
                    if instrument.get("symbol")
                    else None
                ),
                cusip=(
                    str(instrument["cusip"]).strip().upper()
                    if instrument.get("cusip")
                    else None
                ),
                asset_type=ASSET_TYPES.get(asset_name, AssetType.UNKNOWN),
                quantity=quantity,
                market_value=_decimal(raw_position.get("marketValue")),
                average_price=_decimal(raw_position.get("averagePrice")),
            )
        )
    return tuple(observations)
