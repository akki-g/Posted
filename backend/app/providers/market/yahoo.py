import asyncio
from datetime import UTC
from typing import Any

import httpx

from app.market.schemas import CompanyProfile, MarketQuote, MarketSearchResult, PriceBar

PERIODS = {
    "1D": ("5d", "1m"),
    "5D": ("5d", "1d"),
    "1M": ("1mo", "1d"),
    "6M": ("6mo", "1d"),
    "1Y": ("1y", "1d"),
    "5Y": ("5y", "1d"),
}


class YahooMarketClient:
    """Personal-use fallback through yfinance; never treated as an entitlement source."""

    async def search(self, query: str) -> list[MarketSearchResult]:
        async with httpx.AsyncClient(
            timeout=8,
            headers={"User-Agent": "Posted/0.1 personal finance research"},
        ) as client:
            response = await client.get(
                "https://query1.finance.yahoo.com/v1/finance/search",
                params={"q": query, "quotesCount": 8, "newsCount": 0},
            )
            response.raise_for_status()
            payload = response.json()
        results: list[MarketSearchResult] = []
        for item in payload.get("quotes", []):
            quote_type = str(item.get("quoteType") or "").upper()
            if quote_type not in {"EQUITY", "ETF"}:
                continue
            symbol = str(item.get("symbol") or "").upper()
            if not symbol:
                continue
            results.append(
                MarketSearchResult(
                    symbol=symbol,
                    name=str(item.get("longname") or item.get("shortname") or symbol),
                    exchange=_text(item.get("exchDisp") or item.get("exchange")),
                    asset_type="etf" if quote_type == "ETF" else "equity",
                    source="Yahoo Finance",
                )
            )
        return results

    async def history(self, symbol: str, period: str) -> list[PriceBar]:
        return await asyncio.to_thread(_history_sync, symbol, period)

    async def detail(
        self, symbol: str
    ) -> tuple[str | None, MarketQuote | None, CompanyProfile]:
        return await asyncio.to_thread(_detail_sync, symbol)


def _history_sync(symbol: str, period: str) -> list[PriceBar]:
    import yfinance as yf

    yf_period, interval = PERIODS[period]
    frame = yf.Ticker(symbol).history(
        period=yf_period,
        interval=interval,
        auto_adjust=True,
        prepost=False,
        actions=False,
        repair=True,
        timeout=10,
    )
    if frame.empty:
        return []
    if period == "1D":
        latest_date = frame.index[-1].date()
        frame = frame[frame.index.date == latest_date]
    return [
        PriceBar(
            timestamp=index.to_pydatetime().astimezone(UTC),
            open=float(row["Open"]),
            high=float(row["High"]),
            low=float(row["Low"]),
            close=float(row["Close"]),
            volume=int(row["Volume"]),
        )
        for index, row in frame.iterrows()
    ]


def _detail_sync(
    symbol: str,
) -> tuple[str | None, MarketQuote | None, CompanyProfile]:
    import yfinance as yf

    ticker = yf.Ticker(symbol)
    info: dict[str, Any]
    try:
        info = ticker.info or {}
    except Exception:
        info = {}
    history = ticker.history(period="5d", interval="1d", auto_adjust=True, actions=False)
    quote = None
    if not history.empty:
        latest = history.iloc[-1]
        previous_close = (
            float(history.iloc[-2]["Close"])
            if len(history.index) > 1
            else _number(info.get("previousClose"))
        )
        price = float(latest["Close"])
        change = price - previous_close if previous_close else 0
        quote = MarketQuote(
            price=price,
            change=change,
            change_percent=(change / previous_close * 100) if previous_close else 0,
            open=float(latest["Open"]),
            high=float(latest["High"]),
            low=float(latest["Low"]),
            previous_close=previous_close,
            volume=int(latest["Volume"]),
            timestamp=history.index[-1].to_pydatetime().astimezone(UTC),
            source="Yahoo Finance",
            freshness="delayed_or_cached",
        )
    return (
        _text(info.get("longName") or info.get("shortName")),
        quote,
        CompanyProfile(
            description=_text(info.get("longBusinessSummary")),
            sector=_text(info.get("sector")),
            industry=_text(info.get("industry")),
            exchange=_text(info.get("fullExchangeName") or info.get("exchange")),
            website=_text(info.get("website")),
            logo_url=_text(info.get("logo_url")),
            market_cap=_number(info.get("marketCap")),
            pe_ratio=_number(info.get("trailingPE")),
            dividend_yield=_number(info.get("dividendYield")),
            beta=_number(info.get("beta")),
            fifty_two_week_high=_number(info.get("fiftyTwoWeekHigh")),
            fifty_two_week_low=_number(info.get("fiftyTwoWeekLow")),
        ),
    )


def _number(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _text(value: object) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None
