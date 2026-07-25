from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from app.market.schemas import MarketQuote, PriceBar

PERIOD_DAYS = {
    "1D": 5,
    "5D": 10,
    "1M": 35,
    "6M": 190,
    "1Y": 370,
    "5Y": 1830,
}


class AlpacaMarketClient:
    """Small async client for the free Alpaca IEX market-data surface."""

    def __init__(self, *, api_key: str, api_secret: str) -> None:
        self._headers = {
            "APCA-API-KEY-ID": api_key,
            "APCA-API-SECRET-KEY": api_secret,
        }

    async def _get(self, path: str, params: dict[str, str | int]) -> dict[str, Any]:
        async with httpx.AsyncClient(
            base_url="https://data.alpaca.markets",
            headers=self._headers,
            timeout=10,
        ) as client:
            response = await client.get(path, params=params)
            response.raise_for_status()
            return response.json()

    async def quote(self, symbol: str) -> MarketQuote:
        payload = await self._get(f"/v2/stocks/{symbol}/snapshot", {"feed": "iex"})
        latest_trade = payload.get("latestTrade") or {}
        latest_quote = payload.get("latestQuote") or {}
        daily = payload.get("dailyBar") or payload.get("minuteBar") or {}
        previous = payload.get("prevDailyBar") or {}
        price = _number(latest_trade.get("p")) or _number(daily.get("c"))
        previous_close = _number(previous.get("c"))
        if price is None:
            raise ValueError(f"Alpaca returned no price for {symbol}")
        change = price - previous_close if previous_close is not None else 0.0
        change_percent = (change / previous_close * 100) if previous_close else 0.0
        timestamp = _timestamp(latest_trade.get("t") or daily.get("t"))
        return MarketQuote(
            price=price,
            change=change,
            change_percent=change_percent,
            open=_number(daily.get("o")),
            high=_number(daily.get("h")),
            low=_number(daily.get("l")),
            previous_close=previous_close,
            bid=_positive_number(latest_quote.get("bp")),
            ask=_positive_number(latest_quote.get("ap")),
            volume=_integer(daily.get("v")),
            timestamp=timestamp,
            source="Alpaca IEX",
            freshness="real_time_iex",
        )

    async def history(self, symbol: str, period: str) -> list[PriceBar]:
        now = datetime.now(UTC)
        start = now - timedelta(days=PERIOD_DAYS[period])
        timeframe = "1Min" if period == "1D" else "1Day"
        payload = await self._get(
            f"/v2/stocks/{symbol}/bars",
            {
                "timeframe": timeframe,
                "start": start.isoformat(),
                "end": now.isoformat(),
                "limit": 10_000,
                "adjustment": "all",
                "feed": "iex",
                "sort": "asc",
            },
        )
        bars = [_bar(item) for item in payload.get("bars", [])]
        if period == "1D" and bars:
            eastern = ZoneInfo("America/New_York")
            latest_session = bars[-1].timestamp.astimezone(eastern).date()
            bars = [
                bar for bar in bars if bar.timestamp.astimezone(eastern).date() == latest_session
            ]
        return bars


def _bar(item: dict[str, Any]) -> PriceBar:
    return PriceBar(
        timestamp=_timestamp(item.get("t")),
        open=float(item.get("o", 0)),
        high=float(item.get("h", 0)),
        low=float(item.get("l", 0)),
        close=float(item.get("c", 0)),
        volume=int(item.get("v", 0)),
    )


def _timestamp(value: object) -> datetime:
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    return datetime.now(UTC)


def _number(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _integer(value: object) -> int | None:
    number = _number(value)
    return int(number) if number is not None else None


def _positive_number(value: object) -> float | None:
    number = _number(value)
    return number if number is not None and number > 0 else None
