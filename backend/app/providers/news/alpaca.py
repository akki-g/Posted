from datetime import UTC, date, datetime, timedelta
from typing import Any

import httpx

from app.domain.enums import EventProvider
from app.domain.models import ProviderEventEnvelope


class AlpacaNewsClient:
    """Fetch stock news with the same verified Alpaca credentials used for market data."""

    def __init__(self, *, api_key: str, api_secret: str) -> None:
        self._headers = {
            "APCA-API-KEY-ID": api_key,
            "APCA-API-SECRET-KEY": api_secret,
        }

    async def fetch_company_news(
        self,
        *,
        symbols: list[str],
        start_date: date | None = None,
        end_date: date | None = None,
        limit: int = 50,
    ) -> tuple[ProviderEventEnvelope, ...]:
        start_date = start_date or date.today() - timedelta(days=3)
        end_date = end_date or date.today()
        async with httpx.AsyncClient(
            base_url="https://data.alpaca.markets",
            headers=self._headers,
            timeout=12,
        ) as client:
            response = await client.get(
                "/v1beta1/news",
                params={
                    "symbols": ",".join(symbols),
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat(),
                    "sort": "desc",
                    "limit": min(max(limit, 1), 50),
                    "include_content": "true",
                    "exclude_contentless": "true",
                },
            )
            response.raise_for_status()
            payload = response.json()
        received_at = datetime.now(UTC)
        return tuple(
            envelope
            for item in payload.get("news", [])
            if (envelope := _to_envelope(item, requested_symbols=symbols, received_at=received_at))
            is not None
        )


def _to_envelope(
    item: dict[str, Any],
    *,
    requested_symbols: list[str],
    received_at: datetime,
) -> ProviderEventEnvelope | None:
    headline = _text(item.get("headline"))
    if headline is None:
        return None
    item_symbols = item.get("symbols")
    symbols = (
        tuple(str(symbol).strip().upper() for symbol in item_symbols if str(symbol).strip())
        if isinstance(item_symbols, list)
        else tuple(requested_symbols)
    )
    return ProviderEventEnvelope(
        provider=EventProvider.ALPACA,
        provider_event_id=_text(item.get("id")),
        source_name=_text(item.get("source")) or "Alpaca News",
        source_url=_text(item.get("url")),
        headline=headline,
        summary=_text(item.get("summary") or item.get("content")),
        published_at=_timestamp(item.get("created_at") or item.get("updated_at"), received_at),
        received_at=received_at,
        symbols=symbols,
        raw_category="general_news",
    )


def _timestamp(value: object, fallback: datetime) -> datetime:
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)
        except ValueError:
            pass
    return fallback


def _text(value: object) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None
