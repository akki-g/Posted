from unittest.mock import AsyncMock, patch
from uuid import uuid4

from app.config import Settings
from app.domain.enums import EventProvider
from app.domain.models import ProviderEventEnvelope
from app.services.sec_filings import get_recent_filings


def _envelope(**overrides: object) -> ProviderEventEnvelope:
    from datetime import UTC, datetime

    defaults = dict(
        provider=EventProvider.SEC,
        provider_event_id=str(uuid4()),
        source_name="SEC EDGAR",
        source_url="https://www.sec.gov/example",
        headline="AAPL filed 8-K: Current report",
        summary=None,
        published_at=datetime(2026, 7, 21, tzinfo=UTC),
        received_at=datetime(2026, 7, 21, tzinfo=UTC),
        symbols=("AAPL",),
        form_type="8-K",
    )
    defaults.update(overrides)
    return ProviderEventEnvelope(**defaults)


async def test_get_recent_filings_returns_empty_with_a_note_when_cik_is_unresolvable() -> None:
    with patch(
        "app.services.sec_filings.SecEdgarAdapter.resolve_cik", new=AsyncMock(return_value=None)
    ):
        result = await get_recent_filings(symbol="ZZZZ", settings=Settings())

    assert result["symbol"] == "ZZZZ"
    assert result["filings"] == []
    assert "No SEC CIK found" in result["note"]


async def test_get_recent_filings_maps_envelopes_to_compact_dicts() -> None:
    with (
        patch(
            "app.services.sec_filings.SecEdgarAdapter.resolve_cik",
            new=AsyncMock(return_value="320193"),
        ),
        patch(
            "app.services.sec_filings.SecEdgarAdapter.fetch_recent_filings",
            new=AsyncMock(return_value=(_envelope(),)),
        ) as fetch,
    ):
        result = await get_recent_filings(symbol="aapl", settings=Settings())

    fetch.assert_awaited_once()
    assert fetch.await_args.kwargs["companies"] == {"AAPL": "320193"}
    assert result["symbol"] == "AAPL"
    assert result["filings"] == [
        {
            "form_type": "8-K",
            "headline": "AAPL filed 8-K: Current report",
            "source_url": "https://www.sec.gov/example",
            "filed_at": "2026-07-21T00:00:00+00:00",
        }
    ]
