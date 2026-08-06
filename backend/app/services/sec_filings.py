from datetime import date, timedelta
from typing import Any

from app.config import Settings
from app.providers.sec.client import SecEdgarAdapter


async def get_recent_filings(
    *, symbol: str, settings: Settings, days: int = 90, limit: int = 10
) -> dict[str, Any]:
    symbol = symbol.strip().upper()
    adapter = SecEdgarAdapter(user_agent=settings.sec_user_agent)
    cik = await adapter.resolve_cik(symbol)
    if cik is None:
        return {"symbol": symbol, "filings": [], "note": f"No SEC CIK found for {symbol}."}

    events = await adapter.fetch_recent_filings(
        companies={symbol: cik}, since=date.today() - timedelta(days=days)
    )
    return {
        "symbol": symbol,
        "filings": [
            {
                "form_type": event.form_type,
                "headline": event.headline,
                "source_url": event.source_url,
                "filed_at": event.published_at.isoformat(),
            }
            for event in events[:limit]
        ],
    }
