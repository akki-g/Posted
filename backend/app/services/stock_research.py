import asyncio
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.providers.news.multi import MultiSourceNewsAdapter
from app.services.insider_analysis import interpret_insider_activity, summarize_insider_activity
from app.services.market_data import get_stock_detail, get_stock_indicators, normalize_symbol
from app.services.sec_filings import get_recent_filings


async def run_stock_research(
    session: AsyncSession, *, user_id: UUID, symbol: str, settings: Settings
) -> dict[str, Any]:
    symbol = normalize_symbol(symbol)

    async def _safe_news() -> dict[str, Any]:
        try:
            result = await MultiSourceNewsAdapter(settings=settings).fetch_company_news(
                symbols=[symbol], limit=10
            )
        except Exception as exc:  # noqa: BLE001 - one failing source must not break the bundle
            return {"error": f"news lookup failed: {exc}"}
        return {
            "providers": list(result.providers),
            "articles": [
                {
                    "headline": envelope.headline,
                    "summary": envelope.summary,
                    "source": envelope.source_name,
                    "url": envelope.source_url,
                    "published_at": envelope.published_at.isoformat(),
                }
                for envelope in result.envelopes
            ],
        }

    async def _safe_filings() -> dict[str, Any]:
        try:
            return await get_recent_filings(symbol=symbol, settings=settings)
        except Exception as exc:  # noqa: BLE001 - one failing source must not break the bundle
            return {"error": f"SEC filings lookup failed: {exc}"}

    async def _safe_indicators() -> dict[str, Any]:
        try:
            indicators = await get_stock_indicators(symbol=symbol, settings=settings)
        except Exception as exc:  # noqa: BLE001 - one failing source must not break the bundle
            return {"error": f"indicator calculation failed: {exc}"}
        return indicators.model_dump(mode="json")

    detail, indicators, news, filings = await asyncio.gather(
        get_stock_detail(session, user_id=user_id, symbol=symbol, settings=settings),
        _safe_indicators(),
        _safe_news(),
        _safe_filings(),
    )

    insider_summary = summarize_insider_activity(
        transactions=detail.insider_transactions, sentiment=detail.insider_sentiment
    )
    insider_interpretation = interpret_insider_activity(
        symbol=symbol, summary=insider_summary, has_position=detail.position is not None
    )

    return {
        "symbol": symbol,
        "company_name": detail.name,
        "quote": detail.quote.model_dump(mode="json"),
        "company_profile": detail.company.model_dump(mode="json"),
        "earnings": [item.model_dump(mode="json") for item in detail.earnings],
        "position": detail.position.model_dump(mode="json") if detail.position else None,
        "technical_indicators": indicators,
        "insider_summary": insider_summary.model_dump(mode="json"),
        "insider_interpretation": insider_interpretation.model_dump(mode="json"),
        "news": news,
        "sec_filings": filings,
        "disclaimer": (
            "This bundle is informational context assembled from multiple third-party "
            "sources; it is not investment advice and no part of it is a recommendation "
            "to buy, sell, or hold."
        ),
    }
