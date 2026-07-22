from datetime import UTC, datetime
from decimal import Decimal
from uuid import NAMESPACE_URL, UUID, uuid5

from app.domain.enums import AssetType, EventProvider, EventType
from app.domain.models import (
    CanonicalEvent,
    EventSourceRef,
    PositionObservation,
    SecurityIdentity,
    SecurityMatch,
    StoredPosition,
)

NOW = datetime(2026, 7, 22, 12, tzinfo=UTC)


def stable_id(name: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"https://posted.test/{name}")


SECURITIES = {
    "AAPL": SecurityIdentity(stable_id("aapl"), "AAPL"),
    "MSFT": SecurityIdentity(stable_id("msft"), "MSFT"),
    "NVDA": SecurityIdentity(stable_id("nvda"), "NVDA"),
}


def resolve_security(observation: PositionObservation) -> SecurityIdentity | None:
    return SECURITIES.get((observation.symbol or "").upper())


def resolve_event_securities(
    *, symbols: list[str] | tuple[str, ...], cik: str | None
) -> tuple[SecurityMatch, ...]:
    matches = []
    for symbol in symbols:
        identity = SECURITIES.get(symbol.upper())
        if identity:
            matches.append(SecurityMatch(identity.security_id, identity.canonical_symbol, 0.98))
    return tuple(matches)


def observation(
    symbol: str = "AAPL",
    *,
    account: str = "account-1",
    quantity: str = "10",
    market_value: str | None = "2000",
    average_price: str | None = "150",
    asset_type: AssetType = AssetType.EQUITY,
) -> PositionObservation:
    return PositionObservation(
        account_id=stable_id(account),
        observed_at=NOW,
        provider_instrument_id=f"provider-{symbol.lower()}",
        symbol=symbol,
        cusip=None,
        asset_type=asset_type,
        quantity=Decimal(quantity),
        market_value=Decimal(market_value) if market_value is not None else None,
        average_price=Decimal(average_price) if average_price is not None else None,
    )


def stored_position(
    symbol: str = "AAPL", *, account: str = "account-1", quantity: str = "10"
) -> StoredPosition:
    identity = SECURITIES[symbol]
    return StoredPosition(
        position_id=stable_id(f"position-{account}-{symbol}"),
        account_id=stable_id(account),
        security_id=identity.security_id,
        canonical_symbol=identity.canonical_symbol,
        quantity=Decimal(quantity),
        market_value=Decimal("2000"),
        average_price=Decimal("150"),
    )


def canonical_event(
    name: str,
    *,
    symbol: str = "AAPL",
    headline: str = "Company reports quarterly results",
    event_type: EventType = EventType.EARNINGS,
    provider: EventProvider = EventProvider.FMP,
    provider_event_id: str | None = None,
    url: str | None = None,
    accession_number: str | None = None,
) -> CanonicalEvent:
    source = EventSourceRef(
        provider=provider,
        source_name=provider.value,
        source_url=url,
        provider_event_id=provider_event_id,
        confidence=0.95,
    )
    return CanonicalEvent(
        event_id=stable_id(name),
        event_type=event_type,
        headline=headline,
        summary=None,
        occurred_at=NOW,
        first_seen_at=NOW,
        last_seen_at=NOW,
        primary_source=source,
        sources=(source,),
        security_ids=(SECURITIES[symbol].security_id,),
        symbols=(symbol,),
        cik=None,
        accession_number=accession_number,
        form_type="8-K" if accession_number else None,
        canonical_url=url,
        fingerprint=f"fingerprint-{name}",
    )
