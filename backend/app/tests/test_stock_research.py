from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from app.config import Settings
from app.market.schemas import (
    CompanyProfile,
    InsiderSentimentPoint,
    InsiderTransaction,
    MarketQuote,
)
from app.services.stock_research import run_stock_research


def _detail(*, position=None):
    from datetime import UTC, date, datetime

    return SimpleNamespace(
        symbol="AAPL",
        name="Apple Inc.",
        quote=MarketQuote(
            price=200.0,
            change=1.0,
            change_percent=0.5,
            timestamp=datetime(2026, 8, 1, tzinfo=UTC),
            source="Alpaca IEX",
            freshness="real_time_iex",
        ),
        company=CompanyProfile(sector="Technology"),
        earnings=[],
        insider_transactions=[
            InsiderTransaction(
                id="tx-1",
                name="Example Insider",
                filing_date=date(2026, 7, 1),
                transaction_date=date(2026, 6, 30),
                transaction_code="S",
                shares_changed=-500,
                transaction_price=190.0,
            )
        ],
        insider_sentiment=[InsiderSentimentPoint(year=2026, month=6, change=-500, mspr=-20)],
        position=position,
    )


async def test_run_stock_research_bundles_all_sources_concurrently() -> None:
    fake_indicators = SimpleNamespace(model_dump=lambda mode=None: {"rsi": {"value": 55.0}})
    fake_news = SimpleNamespace(
        providers=("alpaca",),
        warnings=(),
        envelopes=(),
    )
    fake_filings = {"symbol": "AAPL", "filings": []}

    with (
        patch(
            "app.services.stock_research.get_stock_detail", new=AsyncMock(return_value=_detail())
        ),
        patch(
            "app.services.stock_research.get_stock_indicators",
            new=AsyncMock(return_value=fake_indicators),
        ),
        patch(
            "app.services.stock_research.MultiSourceNewsAdapter"
        ) as adapter_cls,
        patch(
            "app.services.stock_research.get_recent_filings",
            new=AsyncMock(return_value=fake_filings),
        ),
    ):
        adapter_cls.return_value.fetch_company_news = AsyncMock(return_value=fake_news)
        result = await run_stock_research(
            None, user_id=uuid4(), symbol="aapl", settings=Settings()
        )

    assert result["symbol"] == "AAPL"
    assert result["technical_indicators"] == {"rsi": {"value": 55.0}}
    assert result["sec_filings"] == fake_filings
    assert result["news"]["providers"] == ["alpaca"]
    assert result["insider_summary"]["signal"] == "Moderate insider distribution"
    assert "not investment advice" in result["disclaimer"]


async def test_run_stock_research_keeps_the_bundle_when_news_lookup_fails() -> None:
    fake_indicators = SimpleNamespace(model_dump=lambda mode=None: {})
    fake_filings = {"symbol": "AAPL", "filings": []}

    with (
        patch(
            "app.services.stock_research.get_stock_detail", new=AsyncMock(return_value=_detail())
        ),
        patch(
            "app.services.stock_research.get_stock_indicators",
            new=AsyncMock(return_value=fake_indicators),
        ),
        patch("app.services.stock_research.MultiSourceNewsAdapter") as adapter_cls,
        patch(
            "app.services.stock_research.get_recent_filings",
            new=AsyncMock(return_value=fake_filings),
        ),
    ):
        adapter_cls.return_value.fetch_company_news = AsyncMock(side_effect=RuntimeError("boom"))
        result = await run_stock_research(
            None, user_id=uuid4(), symbol="AAPL", settings=Settings()
        )

    assert "error" in result["news"]
    assert result["symbol"] == "AAPL"
