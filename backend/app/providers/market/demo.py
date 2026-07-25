import math
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.market.schemas import (
    CompanyProfile,
    EarningsResult,
    InsiderSentimentPoint,
    InsiderTransaction,
    MarketQuote,
    MarketSearchResult,
    PriceBar,
)

DEMO_STOCKS = {
    "AAPL": {
        "name": "Apple Inc.",
        "price": 235.88,
        "change": 4.24,
        "sector": "Technology",
        "industry": "Consumer Electronics",
        "market_cap": 3_560_000_000_000,
        "pe": 36.2,
    },
    "MSFT": {
        "name": "Microsoft Corporation",
        "price": 514.60,
        "change": 9.36,
        "sector": "Technology",
        "industry": "Software—Infrastructure",
        "market_cap": 3_830_000_000_000,
        "pe": 39.1,
    },
    "NVDA": {
        "name": "NVIDIA Corporation",
        "price": 187.42,
        "change": -1.02,
        "sector": "Technology",
        "industry": "Semiconductors",
        "market_cap": 4_570_000_000_000,
        "pe": 53.4,
    },
    "VTI": {
        "name": "Vanguard Total Stock Market ETF",
        "price": 315.10,
        "change": 4.34,
        "sector": "Broad market",
        "industry": "Large Blend",
        "market_cap": None,
        "pe": 27.4,
        "asset_type": "etf",
    },
    "GOOGL": {
        "name": "Alphabet Inc.",
        "price": 196.45,
        "change": 1.12,
        "sector": "Communication Services",
        "industry": "Internet Content & Information",
        "market_cap": 2_410_000_000_000,
        "pe": 24.9,
    },
    "AMZN": {
        "name": "Amazon.com, Inc.",
        "price": 224.73,
        "change": -0.68,
        "sector": "Consumer Cyclical",
        "industry": "Internet Retail",
        "market_cap": 2_390_000_000_000,
        "pe": 36.8,
    },
    "TSLA": {
        "name": "Tesla, Inc.",
        "price": 318.20,
        "change": 5.71,
        "sector": "Consumer Cyclical",
        "industry": "Auto Manufacturers",
        "market_cap": 1_020_000_000_000,
        "pe": 171.0,
    },
    "JPM": {
        "name": "JPMorgan Chase & Co.",
        "price": 286.35,
        "change": 0.42,
        "sector": "Financial Services",
        "industry": "Banks—Diversified",
        "market_cap": 786_000_000_000,
        "pe": 15.1,
    },
}

PERIOD_POINTS = {"1D": 390, "5D": 5, "1M": 22, "6M": 130, "1Y": 252, "5Y": 1260}


def search_demo(query: str) -> list[MarketSearchResult]:
    needle = query.casefold()
    return [
        MarketSearchResult(
            symbol=symbol,
            name=str(item["name"]),
            exchange="NASDAQ" if symbol not in {"VTI", "JPM"} else "NYSE",
            asset_type=str(item.get("asset_type", "equity")),
            source="Posted demo",
        )
        for symbol, item in DEMO_STOCKS.items()
        if needle in symbol.casefold() or needle in str(item["name"]).casefold()
    ][:8]


def demo_detail(
    symbol: str,
) -> tuple[str, str, MarketQuote, CompanyProfile, list[EarningsResult]]:
    item = DEMO_STOCKS.get(symbol, _generic_stock(symbol))
    now = datetime.now(UTC).replace(microsecond=0)
    price = float(item["price"])
    change = float(item["change"])
    previous_close = price - change
    quote = MarketQuote(
        price=price,
        change=change,
        change_percent=change / previous_close * 100,
        open=previous_close * 1.002,
        high=max(price, previous_close) * 1.006,
        low=min(price, previous_close) * 0.994,
        previous_close=previous_close,
        bid=price - 0.02,
        ask=price + 0.02,
        volume=48_320_100,
        timestamp=now - timedelta(minutes=1),
        source="Posted demo",
        freshness="demo",
    )
    profile = CompanyProfile(
        description=(
            f"{item['name']} is shown with deterministic sample market data so the stock "
            "research experience remains fully testable before live provider keys are configured."
        ),
        sector=str(item["sector"]),
        industry=str(item["industry"]),
        exchange="NASDAQ" if symbol not in {"VTI", "JPM"} else "NYSE",
        website="https://posted.local/demo",
        market_cap=float(item["market_cap"]) if item["market_cap"] else None,
        pe_ratio=float(item["pe"]),
        dividend_yield=0.45 if symbol in {"AAPL", "MSFT"} else None,
        beta=1.21,
        fifty_two_week_high=price * 1.14,
        fifty_two_week_low=price * 0.68,
    )
    today = date.today()
    earnings = [
        EarningsResult(
            date=today + timedelta(days=42),
            fiscal_quarter="Q3",
            timing="amc",
            eps_estimate=2.16,
            revenue_estimate=102_400_000_000,
        ),
        EarningsResult(
            date=today - timedelta(days=49),
            fiscal_quarter="Q2",
            timing="amc",
            eps_estimate=1.74,
            eps_actual=1.81,
            revenue_estimate=95_200_000_000,
            revenue_actual=97_100_000_000,
        ),
        EarningsResult(
            date=today - timedelta(days=140),
            fiscal_quarter="Q1",
            timing="amc",
            eps_estimate=2.35,
            eps_actual=2.40,
            revenue_estimate=122_900_000_000,
            revenue_actual=124_300_000_000,
        ),
    ]
    return (
        str(item["name"]),
        str(item.get("asset_type", "equity")),
        quote,
        profile,
        earnings,
    )


def demo_history(symbol: str, period: str) -> list[PriceBar]:
    item = DEMO_STOCKS.get(symbol, _generic_stock(symbol))
    count = PERIOD_POINTS[period]
    final_price = float(item["price"])
    intraday = period == "1D"
    eastern = ZoneInfo("America/New_York")
    if intraday:
        session_day = datetime.now(eastern).date()
        cursor = datetime.combine(session_day, time(9, 30), tzinfo=eastern)
        step = timedelta(minutes=1)
        total_drift = float(item["change"])
    else:
        cursor = datetime.now(eastern) - timedelta(days=count * 1.45)
        step = timedelta(days=1)
        period_drift = {"5D": 0.014, "1M": 0.048, "6M": 0.12, "1Y": 0.21, "5Y": 0.82}
        total_drift = final_price * period_drift[period]

    start_price = final_price - total_drift
    bars: list[PriceBar] = []
    index = 0
    while len(bars) < count:
        timestamp = cursor + step * index
        index += 1
        if not intraday and timestamp.weekday() >= 5:
            continue
        progress = len(bars) / max(count - 1, 1)
        wave = math.sin(progress * math.pi * 7) * final_price * (0.003 if intraday else 0.018)
        close = start_price + total_drift * progress + wave
        open_price = close - math.sin(progress * 31) * final_price * 0.0015
        high = max(open_price, close) * 1.0022
        low = min(open_price, close) * 0.9978
        bars.append(
            PriceBar(
                timestamp=timestamp.astimezone(UTC),
                open=round(open_price, 4),
                high=round(high, 4),
                low=round(low, 4),
                close=round(close, 4),
                volume=120_000 + (len(bars) * 7919) % 780_000,
            )
        )
    return bars


def demo_insider_transactions(symbol: str) -> list[InsiderTransaction]:
    today = date.today()
    return [
        InsiderTransaction(
            id=f"demo-{symbol}-insider-1",
            name="Sample executive",
            filing_date=today - timedelta(days=8),
            transaction_date=today - timedelta(days=10),
            transaction_code="S",
            shares_owned=185_400,
            shares_changed=-4_500,
            transaction_price=float(DEMO_STOCKS.get(symbol, _generic_stock(symbol))["price"]),
        ),
        InsiderTransaction(
            id=f"demo-{symbol}-insider-2",
            name="Sample director",
            filing_date=today - timedelta(days=36),
            transaction_date=today - timedelta(days=38),
            transaction_code="P",
            shares_owned=42_300,
            shares_changed=1_250,
            transaction_price=(
                float(DEMO_STOCKS.get(symbol, _generic_stock(symbol))["price"]) * 0.96
            ),
        ),
    ]


def demo_insider_sentiment(symbol: str) -> list[InsiderSentimentPoint]:
    today = date.today()
    seed = sum(ord(character) for character in symbol)
    points: list[InsiderSentimentPoint] = []
    for offset in range(11, -1, -1):
        month_index = today.year * 12 + today.month - 1 - offset
        year, zero_based_month = divmod(month_index, 12)
        wave = math.sin((seed + offset) * 0.73) * 24
        drift = (6 - offset) * 1.25
        mspr = max(-100, min(100, wave + drift))
        points.append(
            InsiderSentimentPoint(
                year=year,
                month=zero_based_month + 1,
                change=round(mspr * 1_850),
                mspr=round(mspr, 2),
            )
        )
    return points


def _generic_stock(symbol: str) -> dict[str, object]:
    return {
        "name": f"{symbol} Corporation",
        "price": 100.0,
        "change": 0.85,
        "sector": "Unclassified",
        "industry": "Equity",
        "market_cap": None,
        "pe": 24.0,
    }
