import asyncio
from datetime import UTC, date, datetime, timedelta
from typing import Any

import httpx

from app.domain.enums import EventProvider
from app.domain.models import ProviderEventEnvelope


class FinnhubNewsClient:
    """Fetch North American company news through Finnhub's verified free endpoint."""

    def __init__(self, *, api_key: str) -> None:
        self._headers = {"X-Finnhub-Token": api_key}

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
        semaphore = asyncio.Semaphore(5)
        async with httpx.AsyncClient(
            base_url="https://finnhub.io/api/v1",
            headers=self._headers,
            timeout=12,
        ) as client:

            async def fetch_symbol(symbol: str) -> tuple[str, list[dict[str, Any]]]:
                async with semaphore:
                    response = await client.get(
                        "/company-news",
                        params={
                            "symbol": symbol,
                            "from": start_date.isoformat(),
                            "to": end_date.isoformat(),
                        },
                    )
                    response.raise_for_status()
                    return symbol, response.json()

            responses = await asyncio.gather(
                *(fetch_symbol(symbol) for symbol in symbols[:50]),
                return_exceptions=True,
            )

        received_at = datetime.now(UTC)
        envelopes: list[ProviderEventEnvelope] = []
        errors: list[Exception] = []
        for result in responses:
            if isinstance(result, Exception):
                errors.append(result)
                continue
            symbol, items = result
            envelopes.extend(
                envelope
                for item in items
                if (envelope := _to_envelope(item, symbol=symbol, received_at=received_at))
                is not None
            )
        if errors and not envelopes:
            raise errors[0]
        envelopes.sort(key=lambda item: item.published_at, reverse=True)
        return tuple(envelopes[: max(limit, 1)])


def _to_envelope(
    item: dict[str, Any],
    *,
    symbol: str,
    received_at: datetime,
) -> ProviderEventEnvelope | None:
    headline = _text(item.get("headline"))
    if headline is None:
        return None
    related = _text(item.get("related"))
    related_symbols = (
        tuple(
            sorted(
                {
                    symbol.upper(),
                    *(
                        part.strip().upper()
                        for part in related.replace(";", ",").split(",")
                        if part.strip()
                    ),
                }
            )
        )
        if related
        else (symbol.upper(),)
    )
    return ProviderEventEnvelope(
        provider=EventProvider.FINNHUB,
        provider_event_id=_text(item.get("id")),
        source_name=_text(item.get("source")) or "Finnhub News",
        source_url=_text(item.get("url")),
        headline=headline,
        summary=_text(item.get("summary")),
        published_at=_timestamp(item.get("datetime"), received_at),
        received_at=received_at,
        symbols=related_symbols,
        raw_category=_text(item.get("category")) or "general_news",
    )


def _timestamp(value: object, fallback: datetime) -> datetime:
    try:
        timestamp = int(value) if value is not None else 0
    except (TypeError, ValueError):
        timestamp = 0
    return datetime.fromtimestamp(timestamp, UTC) if timestamp > 0 else fallback


def _text(value: object) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None
