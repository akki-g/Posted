from datetime import date

import httpx

import app.providers.sec.client as sec_client_module
from app.domain.enums import EventProvider
from app.providers.sec.client import SecEdgarAdapter


async def test_maps_only_recent_material_sec_filings() -> None:
    payload = {
        "filings": {
            "recent": {
                "accessionNumber": ["0000320193-26-000010", "0000320193-25-000001"],
                "filingDate": ["2026-07-21", "2025-01-02"],
                "reportDate": ["2026-07-20", "2024-12-31"],
                "form": ["8-K", "4"],
                "primaryDocument": ["aapl-20260720.htm", "ownership.xml"],
                "primaryDocDescription": ["Current report", "Insider transaction"],
            }
        }
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["User-Agent"] == "Posted test@example.com"
        assert request.url.path.endswith("CIK0000320193.json")
        return httpx.Response(200, json=payload)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        headers={"User-Agent": "Posted test@example.com"},
    ) as http:
        events = await SecEdgarAdapter(
            user_agent="Posted test@example.com",
            http=http,
        ).fetch_recent_filings(
            companies={"AAPL": "320193"},
            since=date(2026, 7, 1),
        )

    assert len(events) == 1
    event = events[0]
    assert event.provider is EventProvider.SEC
    assert event.symbols == ("AAPL",)
    assert event.form_type == "8-K"
    assert event.accession_number == "0000320193-26-000010"
    assert event.source_url and "/320193/000032019326000010/" in event.source_url


async def test_resolve_cik_looks_up_ticker_in_sec_company_tickers_json() -> None:
    sec_client_module._TICKER_CIK_CACHE.clear()
    sec_client_module._TICKER_CIK_CACHE_LOADED_AT = None
    payload = {
        "0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."},
        "1": {"cik_str": 789019, "ticker": "MSFT", "title": "Microsoft Corp"},
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["User-Agent"] == "Posted test@example.com"
        assert request.url.path.endswith("company_tickers.json")
        return httpx.Response(200, json=payload)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        headers={"User-Agent": "Posted test@example.com"},
    ) as http:
        adapter = sec_client_module.SecEdgarAdapter(user_agent="Posted test@example.com", http=http)
        cik = await adapter.resolve_cik("aapl")
        missing = await adapter.resolve_cik("ZZZZ")

    assert cik == "320193"
    assert missing is None


async def test_resolve_cik_reuses_the_cache_within_the_ttl() -> None:
    sec_client_module._TICKER_CIK_CACHE.clear()
    sec_client_module._TICKER_CIK_CACHE_LOADED_AT = None
    payload = {"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}}
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(200, json=payload)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        headers={"User-Agent": "Posted test@example.com"},
    ) as http:
        adapter = sec_client_module.SecEdgarAdapter(user_agent="Posted test@example.com", http=http)
        await adapter.resolve_cik("AAPL")
        await adapter.resolve_cik("AAPL")

    assert call_count == 1
