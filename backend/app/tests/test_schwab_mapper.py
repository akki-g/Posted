from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from app.domain.enums import AssetType
from app.providers.schwab.mapper import map_schwab_positions


def test_maps_schwab_position_to_provider_neutral_observation() -> None:
    account_id = uuid4()
    observed_at = datetime(2026, 7, 22, 12, tzinfo=UTC)
    payload = {
        "securitiesAccount": {
            "positions": [
                {
                    "longQuantity": 12.5,
                    "shortQuantity": 0,
                    "averagePrice": 188.2,
                    "marketValue": 2948.5,
                    "instrument": {
                        "assetType": "EQUITY",
                        "symbol": "AAPL",
                        "cusip": "037833100",
                        "instrumentId": 42,
                    },
                }
            ]
        }
    }
    result = map_schwab_positions(payload, account_id=account_id, observed_at=observed_at)
    assert len(result) == 1
    assert result[0].account_id == account_id
    assert result[0].asset_type is AssetType.EQUITY
    assert result[0].quantity == Decimal("12.5")
    assert result[0].average_price == Decimal("188.2")
    assert result[0].provider_instrument_id == "42"


def test_unknown_asset_is_preserved_for_domain_rejection() -> None:
    payload = {
        "securitiesAccount": {
            "positions": [
                {
                    "longQuantity": "1",
                    "instrument": {"assetType": "FUTURE", "symbol": "/ES"},
                }
            ]
        }
    }
    result = map_schwab_positions(payload, account_id=uuid4())
    assert result[0].asset_type is AssetType.UNKNOWN
