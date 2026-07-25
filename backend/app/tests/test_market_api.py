from datetime import date, datetime

from httpx import AsyncClient

from app.market.schemas import InsiderSentimentPoint, InsiderTransaction
from app.providers.market.finnhub import FinnhubMarketClient
from app.services.insider_analysis import summarize_insider_activity


async def test_market_search_prioritizes_portfolio_symbols(client: AsyncClient) -> None:
    response = await client.get("/api/v1/market/search", params={"q": "apple"})

    assert response.status_code == 200
    body = response.json()
    assert body[0]["symbol"] == "AAPL"
    assert body[0]["in_portfolio"] is True
    assert body[0]["source"] == "Portfolio"


async def test_stock_detail_combines_quote_position_earnings_and_news(
    client: AsyncClient,
) -> None:
    response = await client.get("/api/v1/market/stocks/AAPL")

    assert response.status_code == 200
    body = response.json()
    assert body["symbol"] == "AAPL"
    assert body["name"] == "Apple Inc."
    assert body["quote"]["price"] == 235.88
    assert body["quote"]["source"] == "Posted demo"
    assert body["position"]["quantity"] == 290.0
    assert body["position"]["portfolio_weight"] == 24.03
    assert body["earnings"][0]["eps_estimate"] == 2.16
    assert len(body["insider_transactions"]) == 2
    assert body["insider_transactions"][0]["transaction_code"] == "S"
    assert len(body["insider_sentiment"]) == 12
    assert len(body["related_news"]) == 1
    assert body["related_news"][0]["event_type"] == "regulatory_legal"
    assert body["is_demo"] is True


async def test_one_day_history_uses_one_minute_bars(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/market/stocks/MSFT/history",
        params={"period": "1D"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["interval"] == "1Min"
    assert len(body["points"]) == 390
    first = datetime.fromisoformat(body["points"][0]["timestamp"])
    second = datetime.fromisoformat(body["points"][1]["timestamp"])
    assert (second - first).total_seconds() == 60


async def test_wider_history_uses_uninterpolated_daily_bars(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/market/stocks/NVDA/history",
        params={"period": "1M"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["interval"] == "1Day"
    assert len(body["points"]) == 22
    assert "Daily sample bars" in body["coverage_note"]


async def test_market_rejects_invalid_ticker(client: AsyncClient) -> None:
    response = await client.get("/api/v1/market/stocks/not%20a%20ticker")

    assert response.status_code == 422


async def test_finnhub_insider_filing_rows_receive_unique_ids(monkeypatch) -> None:
    provider = FinnhubMarketClient(api_key="test")

    async def fake_get(path: str, params: dict[str, str | int]) -> dict:
        assert path == "/stock/insider-transactions"
        assert params == {"symbol": "AAPL"}
        shared = {
            "id": "filing-1",
            "name": "Example Insider",
            "filingDate": "2026-05-27",
            "transactionDate": "2026-05-26",
            "transactionCode": "S",
            "share": 1000,
            "currency": "USD",
        }
        return {
            "data": [
                {**shared, "change": -100, "transactionPrice": 310},
                {**shared, "change": -200, "transactionPrice": 311},
                {**shared, "change": -100, "transactionPrice": 310},
            ]
        }

    monkeypatch.setattr(provider, "_get", fake_get)
    rows = await provider.insider_transactions("AAPL")

    assert len(rows) == 2
    assert len({row.id for row in rows}) == 2


async def test_finnhub_insider_sentiment_maps_monthly_mspr(monkeypatch) -> None:
    provider = FinnhubMarketClient(api_key="test")

    async def fake_get(path: str, params: dict[str, str | int]) -> dict:
        assert path == "/stock/insider-sentiment"
        assert params["symbol"] == "MSFT"
        return {
            "data": [
                {"symbol": "MSFT", "year": 2026, "month": 5, "change": -900, "mspr": -12.5},
                {"symbol": "MSFT", "year": 2026, "month": 6, "change": 1200, "mspr": 18.25},
            ]
        }

    monkeypatch.setattr(provider, "_get", fake_get)
    points = await provider.insider_sentiment("MSFT")

    assert [point.mspr for point in points] == [-12.5, 18.25]
    assert points[-1].change == 1200


def test_insider_summary_separates_directional_and_compensation_activity() -> None:
    transactions = [
        InsiderTransaction(
            id="purchase",
            name="Executive",
            filing_date=date(2026, 6, 5),
            transaction_date=date(2026, 6, 3),
            transaction_code="P",
            shares_changed=1000,
            transaction_price=50,
        ),
        InsiderTransaction(
            id="sale",
            name="Director",
            filing_date=date(2026, 6, 6),
            transaction_date=date(2026, 6, 4),
            transaction_code="S",
            shares_changed=-400,
            transaction_price=55,
        ),
        InsiderTransaction(
            id="award",
            name="Executive",
            filing_date=date(2026, 6, 7),
            transaction_date=date(2026, 6, 5),
            transaction_code="A",
            shares_changed=5000,
            transaction_price=0,
        ),
    ]
    sentiment = [
        InsiderSentimentPoint(year=2026, month=4, change=100, mspr=10),
        InsiderSentimentPoint(year=2026, month=5, change=200, mspr=20),
        InsiderSentimentPoint(year=2026, month=6, change=300, mspr=30),
    ]

    summary = summarize_insider_activity(
        transactions=transactions,
        sentiment=sentiment,
    )

    assert summary.open_market_purchases == 1
    assert summary.open_market_sales == 1
    assert summary.non_directional_transactions == 1
    assert summary.purchase_value == 50_000
    assert summary.sale_value == 22_000
    assert summary.three_month_average_mspr == 20


async def test_insider_analysis_api_returns_interpretation_and_portfolio_context(
    client: AsyncClient,
) -> None:
    response = await client.get("/api/v1/market/stocks/AAPL/insiders", params={"ai": False})

    assert response.status_code == 200
    body = response.json()
    assert body["symbol"] == "AAPL"
    assert len(body["transactions"]) == 2
    assert len(body["sentiment"]) == 12
    assert body["summary"]["non_directional_transactions"] == 0
    assert body["interpretation"]["factors"]
    assert body["position"]["portfolio_weight"] == 24.03
    assert body["ai_insight"] is None


async def test_portfolio_insider_watch_tracks_equity_holdings(client: AsyncClient) -> None:
    response = await client.get("/api/v1/market/insiders/portfolio")

    assert response.status_code == 200
    body = response.json()
    assert body["items"]
    assert all(item["symbol"] != "VTI" for item in body["items"])
    assert all("signal" in item for item in body["items"])
