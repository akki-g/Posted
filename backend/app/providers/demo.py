from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from app.domain.enums import AssetType, EventProvider
from app.domain.models import PositionObservation, ProviderEventEnvelope


@dataclass(frozen=True, slots=True)
class DemoBrokerageSnapshot:
    observations: tuple[PositionObservation, ...]
    complete: bool = True


class DemoBrokerageAdapter:
    async def fetch_complete_snapshot(self, connection_id: UUID) -> DemoBrokerageSnapshot:
        now = datetime.now(UTC)
        return DemoBrokerageSnapshot(
            observations=(
                PositionObservation(
                    account_id=connection_id,
                    observed_at=now,
                    provider_instrument_id="demo-aapl",
                    symbol="AAPL",
                    cusip="037833100",
                    asset_type=AssetType.EQUITY,
                    quantity=Decimal("10"),
                    market_value=Decimal("2358.80"),
                    average_price=Decimal("188.20"),
                ),
            )
        )


class DemoEventAdapter:
    name = "demo"
    required = False

    async def fetch_for_symbols(self, symbols: list[str]) -> tuple[ProviderEventEnvelope, ...]:
        now = datetime.now(UTC)
        return tuple(
            ProviderEventEnvelope(
                provider=EventProvider.DEMO,
                provider_event_id=f"demo-{symbol.lower()}",
                source_name="Posted demo feed",
                source_url=None,
                headline=f"Demo event for {symbol}",
                summary="A deterministic local record used without external credentials.",
                published_at=now,
                received_at=now,
                symbols=(symbol,),
                raw_category="general_news",
            )
            for symbol in symbols
        )
