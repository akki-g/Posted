import asyncio
from datetime import UTC, date, datetime, timedelta
from typing import Any

import httpx

from app.market.schemas import (
    CompanyProfile,
    EarningsResult,
    InsiderSentimentPoint,
    InsiderTransaction,
    MarketQuote,
    MarketSearchResult,
)


class FinnhubMarketClient:
    """Finnhub free-tier lookup, quote, profile, earnings, and insider enrichment."""

    def __init__(self, *, api_key: str) -> None:
        self._headers = {"X-Finnhub-Token": api_key}

    async def _get(self, path: str, params: dict[str, str | int]) -> Any:
        async with httpx.AsyncClient(
            base_url="https://finnhub.io/api/v1",
            headers=self._headers,
            timeout=10,
        ) as client:
            response = await client.get(path, params=params)
            response.raise_for_status()
            return response.json()

    async def search(self, query: str) -> list[MarketSearchResult]:
        payload = await self._get("/search", {"q": query, "exchange": "US"})
        results: list[MarketSearchResult] = []
        for item in payload.get("result", []):
            symbol = str(item.get("displaySymbol") or item.get("symbol") or "").upper()
            item_type = str(item.get("type") or "")
            if not symbol or "." in symbol or item_type.lower() not in {
                "common stock",
                "etp",
                "reit",
                "adr",
            }:
                continue
            results.append(
                MarketSearchResult(
                    symbol=symbol,
                    name=str(item.get("description") or symbol).title(),
                    exchange="US",
                    asset_type=_asset_type(item_type),
                    source="Finnhub",
                )
            )
            if len(results) >= 8:
                break
        return results

    async def quote(self, symbol: str) -> MarketQuote:
        payload = await self._get("/quote", {"symbol": symbol})
        price = _number(payload.get("c"))
        if not price:
            raise ValueError(f"Finnhub returned no price for {symbol}")
        timestamp = datetime.fromtimestamp(int(payload.get("t") or 0), UTC)
        return MarketQuote(
            price=price,
            change=_number(payload.get("d")) or 0,
            change_percent=_number(payload.get("dp")) or 0,
            open=_number(payload.get("o")),
            high=_number(payload.get("h")),
            low=_number(payload.get("l")),
            previous_close=_number(payload.get("pc")),
            timestamp=timestamp,
            source="Finnhub",
            freshness="recent",
        )

    async def company(self, symbol: str) -> tuple[str | None, CompanyProfile]:
        profile, metrics = await asyncio.gather(
            self._get("/stock/profile2", {"symbol": symbol}),
            self._get("/stock/metric", {"symbol": symbol, "metric": "all"}),
            return_exceptions=True,
        )
        profile = profile if isinstance(profile, dict) else {}
        metric = metrics.get("metric", {}) if isinstance(metrics, dict) else {}
        return (
            str(profile.get("name")) if profile.get("name") else None,
            CompanyProfile(
                sector=_text(profile.get("finnhubIndustry")),
                industry=_text(profile.get("finnhubIndustry")),
                exchange=_text(profile.get("exchange")),
                website=_text(profile.get("weburl")),
                logo_url=_text(profile.get("logo")),
                market_cap=_millions_to_units(profile.get("marketCapitalization")),
                pe_ratio=_first_number(
                    metric, "peBasicExclExtraTTM", "peNormalizedAnnual", "peTTM"
                ),
                dividend_yield=_first_number(
                    metric, "dividendYieldIndicatedAnnual", "dividendYield5Y"
                ),
                beta=_first_number(metric, "beta"),
                fifty_two_week_high=_first_number(metric, "52WeekHigh"),
                fifty_two_week_low=_first_number(metric, "52WeekLow"),
            ),
        )

    async def earnings(self, symbol: str) -> list[EarningsResult]:
        today = date.today()
        calendar_payload, history_payload = await asyncio.gather(
            self._get(
                "/calendar/earnings",
                {
                    "symbol": symbol,
                    "from": (today - timedelta(days=35)).isoformat(),
                    "to": (today + timedelta(days=120)).isoformat(),
                },
            ),
            self._get("/stock/earnings", {"symbol": symbol, "limit": 4}),
            return_exceptions=True,
        )
        by_date: dict[date, EarningsResult] = {}
        if isinstance(history_payload, list):
            for item in history_payload:
                result_date = _date(item.get("period"))
                if result_date is None:
                    continue
                by_date[result_date] = EarningsResult(
                    date=result_date,
                    fiscal_quarter=_quarter(item.get("quarter"), item.get("year")),
                    eps_estimate=_number(item.get("estimate")),
                    eps_actual=_number(item.get("actual")),
                )
        if isinstance(calendar_payload, dict):
            for item in calendar_payload.get("earningsCalendar", []):
                result_date = _date(item.get("date"))
                if result_date is None:
                    continue
                by_date[result_date] = EarningsResult(
                    date=result_date,
                    fiscal_quarter=_quarter(item.get("quarter"), item.get("year")),
                    timing=_text(item.get("hour")),
                    eps_estimate=_number(item.get("epsEstimate")),
                    eps_actual=_number(item.get("epsActual")),
                    revenue_estimate=_number(item.get("revenueEstimate")),
                    revenue_actual=_number(item.get("revenueActual")),
                )
        return sorted(by_date.values(), key=lambda item: item.date, reverse=True)[:6]

    async def insider_sentiment(
        self,
        symbol: str,
        *,
        months: int = 12,
    ) -> list[InsiderSentimentPoint]:
        today = date.today()
        payload = await self._get(
            "/stock/insider-sentiment",
            {
                "symbol": symbol,
                "from": (today - timedelta(days=months * 31)).isoformat(),
                "to": today.isoformat(),
            },
        )
        if not isinstance(payload, dict):
            return []
        points: list[InsiderSentimentPoint] = []
        for item in payload.get("data", []):
            mspr = _number(item.get("mspr"))
            year = item.get("year")
            month = item.get("month")
            if mspr is None or not isinstance(year, int) or not isinstance(month, int):
                continue
            points.append(
                InsiderSentimentPoint(
                    year=year,
                    month=month,
                    change=_number(item.get("change")) or 0,
                    mspr=mspr,
                )
            )
        return sorted(points, key=lambda item: (item.year, item.month))[-months:]

    async def insider_transactions(
        self,
        symbol: str,
        *,
        limit: int = 50,
    ) -> list[InsiderTransaction]:
        today = date.today()
        payload = await self._get("/stock/insider-transactions", {"symbol": symbol, "from": (today - timedelta(days=30)).isoformat(),
                        "to": today.isoformat()})
        if not isinstance(payload, dict):
            return []
        transactions: dict[str, InsiderTransaction] = {}
        for item in payload.get("data", []):
            filing_date = _date(item.get("filingDate"))
            transaction_date = _date(item.get("transactionDate"))
            if filing_date is None or transaction_date is None:
                continue
            name = _text(item.get("name")) or "Company insider"
            transaction_code = _text(item.get("transactionCode")) or "unknown"
            shares_changed = _number(item.get("change"))
            transaction_price = _number(item.get("transactionPrice"))
            source_id = _text(item.get("id")) or symbol
            transaction_id = ":".join(
                (
                    source_id,
                    transaction_date.isoformat(),
                    transaction_code,
                    name,
                    str(shares_changed),
                    str(transaction_price),
                )
            )
            transactions[transaction_id] = InsiderTransaction(
                id=transaction_id,
                name=name,
                filing_date=filing_date,
                transaction_date=transaction_date,
                transaction_code=transaction_code,
                shares_owned=_number(item.get("share")),
                shares_changed=shares_changed,
                transaction_price=transaction_price,
                currency=_text(item.get("currency")) or "USD",
                is_derivative=bool(item.get("isDerivative")),
            )
        return sorted(
            transactions.values(),
            key=lambda item: (item.filing_date, item.transaction_date),
            reverse=True,
        )[:limit]


def _asset_type(item_type: str) -> str:
    lowered = item_type.lower()
    if "etp" in lowered or "fund" in lowered:
        return "etf"
    return "equity"


def _quarter(quarter: object, year: object) -> str | None:
    if quarter is None and year is None:
        return None
    return f"Q{quarter} {year}" if quarter is not None else str(year)


def _date(value: object) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _number(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _first_number(values: dict[str, object], *keys: str) -> float | None:
    for key in keys:
        result = _number(values.get(key))
        if result is not None:
            return result
    return None


def _millions_to_units(value: object) -> float | None:
    number = _number(value)
    return number * 1_000_000 if number is not None else None


def _text(value: object) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None
