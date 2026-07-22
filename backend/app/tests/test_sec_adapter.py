from datetime import date

import httpx

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
