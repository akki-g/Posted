import asyncio
import time
from datetime import UTC, date, datetime, timedelta
from typing import Any

import httpx

from app.domain.enums import EventProvider
from app.domain.models import ProviderEventEnvelope

SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
ARCHIVES_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{document}"
DEFAULT_FORMS = frozenset({"8-K", "10-K", "10-Q", "6-K", "20-F"})
TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"
_TICKER_CIK_CACHE_TTL_SECONDS = 24 * 60 * 60
_TICKER_CIK_CACHE: dict[str, str] = {}
_TICKER_CIK_CACHE_LOADED_AT: float | None = None


class SecEdgarAdapter:
    """Read recent material filings from the SEC's submissions JSON endpoint."""

    def __init__(self, *, user_agent: str, http: httpx.AsyncClient | None = None) -> None:
        self._user_agent = user_agent
        self._http = http

    async def fetch_recent_filings(
        self,
        *,
        companies: dict[str, str],
        since: date | None = None,
        forms: frozenset[str] = DEFAULT_FORMS,
    ) -> tuple[ProviderEventEnvelope, ...]:
        since = since or date.today() - timedelta(days=7)
        received_at = datetime.now(UTC)
        owns_client = self._http is None
        client = self._http or httpx.AsyncClient(
            timeout=20,
            headers={"User-Agent": self._user_agent, "Accept": "application/json"},
        )
        events: list[ProviderEventEnvelope] = []
        try:
            for index, (symbol, raw_cik) in enumerate(companies.items()):
                if index:
                    # SEC asks automated clients to stay below ten requests per second.
                    await asyncio.sleep(0.11)
                cik = raw_cik.lstrip("0").zfill(10)
                response = await client.get(
                    SUBMISSIONS_URL.format(cik=cik),
                    headers={"User-Agent": self._user_agent, "Accept": "application/json"},
                )
                response.raise_for_status()
                events.extend(
                    _map_recent_filings(
                        response.json(),
                        symbol=symbol.upper(),
                        cik=cik,
                        since=since,
                        forms=forms,
                        received_at=received_at,
                    )
                )
        finally:
            if owns_client:
                await client.aclose()
        return tuple(sorted(events, key=lambda event: event.published_at, reverse=True))

    async def resolve_cik(self, symbol: str) -> str | None:
        await self._ensure_ticker_cache()
        return _TICKER_CIK_CACHE.get(symbol.upper())

    async def _ensure_ticker_cache(self) -> None:
        global _TICKER_CIK_CACHE_LOADED_AT
        now = time.monotonic()
        if (
            _TICKER_CIK_CACHE_LOADED_AT is not None
            and now - _TICKER_CIK_CACHE_LOADED_AT < _TICKER_CIK_CACHE_TTL_SECONDS
        ):
            return
        owns_client = self._http is None
        client = self._http or httpx.AsyncClient(
            timeout=20, headers={"User-Agent": self._user_agent, "Accept": "application/json"}
        )
        try:
            response = await client.get(
                TICKER_MAP_URL,
                headers={"User-Agent": self._user_agent, "Accept": "application/json"},
            )
            response.raise_for_status()
            payload = response.json()
        finally:
            if owns_client:
                await client.aclose()
        _TICKER_CIK_CACHE.clear()
        for entry in payload.values():
            ticker = str(entry.get("ticker") or "").upper()
            cik = entry.get("cik_str")
            if ticker and cik is not None:
                _TICKER_CIK_CACHE[ticker] = str(cik)
        _TICKER_CIK_CACHE_LOADED_AT = now


def _map_recent_filings(
    payload: dict[str, Any],
    *,
    symbol: str,
    cik: str,
    since: date,
    forms: frozenset[str],
    received_at: datetime,
) -> list[ProviderEventEnvelope]:
    recent = payload.get("filings", {}).get("recent", {})
    columns = zip(
        recent.get("accessionNumber", []),
        recent.get("filingDate", []),
        recent.get("reportDate", []),
        recent.get("form", []),
        recent.get("primaryDocument", []),
        recent.get("primaryDocDescription", []),
        strict=False,
    )
    events: list[ProviderEventEnvelope] = []
    for accession, filing_text, report_text, form, document, description in columns:
        filing_date = date.fromisoformat(filing_text)
        if filing_date < since or form not in forms:
            continue
        archive_url = ARCHIVES_URL.format(
            cik=int(cik),
            accession=str(accession).replace("-", ""),
            document=document,
        )
        label = description or f"{form} filing"
        events.append(
            ProviderEventEnvelope(
                provider=EventProvider.SEC,
                provider_event_id=str(accession),
                source_name="SEC EDGAR",
                source_url=archive_url,
                headline=f"{symbol} filed {form}: {label}",
                summary=f"Report date: {report_text}" if report_text else None,
                published_at=datetime.combine(filing_date, datetime.min.time(), tzinfo=UTC),
                received_at=received_at,
                symbols=(symbol,),
                cik=cik,
                accession_number=str(accession),
                form_type=str(form),
                raw_category="sec_filing",
            )
        )
    return events
