import asyncio
from datetime import UTC, date, datetime, timedelta
from typing import Any

from app.domain.enums import EventProvider
from app.domain.errors import ProviderNotConfiguredError
from app.domain.models import ProviderEventEnvelope

PROVIDER_NAMES = {
    "benzinga": EventProvider.BENZINGA,
    "fmp": EventProvider.FMP,
    "intrinio": EventProvider.INTRINIO,
    "yfinance": EventProvider.YFINANCE,
}


class OpenBBNewsAdapter:
    """Fetch standardized company news through the OpenBB Python interface."""

    def __init__(self, *, provider: str = "yfinance") -> None:
        self.provider = provider

    async def fetch_company_news(
        self,
        *,
        symbols: list[str],
        start_date: date | None = None,
        end_date: date | None = None,
        limit: int = 100,
    ) -> tuple[ProviderEventEnvelope, ...]:
        try:
            from openbb import obb  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ProviderNotConfiguredError(
                "Install the backend with the 'openbb' extra to enable live OpenBB data."
            ) from exc

        start_date = start_date or date.today() - timedelta(days=3)
        end_date = end_date or date.today()

        def fetch() -> list[dict[str, Any]]:
            response = obb.news.company(
                symbol=",".join(symbols),
                start_date=start_date,
                end_date=end_date,
                limit=limit,
                provider=self.provider,
            )
            return response.to_df().reset_index(drop=True).to_dict(orient="records")

        rows = await asyncio.to_thread(fetch)
        received_at = datetime.now(UTC)
        provider_enum = PROVIDER_NAMES.get(self.provider, EventProvider.OPENBB)
        envelopes: list[ProviderEventEnvelope] = []
        for row in rows:
            published = row.get("date") or row.get("published") or row.get("published_at")
            if isinstance(published, str):
                published_at = datetime.fromisoformat(published.replace("Z", "+00:00"))
            elif isinstance(published, datetime):
                published_at = published
            else:
                published_at = received_at
            if published_at.tzinfo is None:
                published_at = published_at.replace(tzinfo=UTC)
            related = row.get("symbols") or row.get("symbol") or symbols
            if isinstance(related, str):
                related_symbols = tuple(
                    part.strip().upper() for part in related.split(",") if part.strip()
                )
            else:
                related_symbols = tuple(str(item).upper() for item in related)
            envelopes.append(
                ProviderEventEnvelope(
                    provider=provider_enum,
                    provider_event_id=(str(row["id"]) if row.get("id") is not None else None),
                    source_name=str(row.get("source") or self.provider),
                    source_url=str(row.get("url")) if row.get("url") else None,
                    headline=str(row.get("title") or row.get("headline") or ""),
                    summary=str(row.get("text") or row.get("summary"))
                    if row.get("text") or row.get("summary")
                    else None,
                    published_at=published_at.astimezone(UTC),
                    received_at=received_at,
                    symbols=related_symbols,
                    raw_category=(
                        str(row["category"]) if row.get("category") is not None else None
                    ),
                )
            )
        return tuple(envelopes)
