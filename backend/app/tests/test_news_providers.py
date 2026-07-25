from datetime import UTC, datetime

from httpx import AsyncClient

from app.domain.enums import EventProvider
from app.domain.models import ProviderEventEnvelope
from app.providers.news.alpaca import _to_envelope as alpaca_envelope
from app.providers.news.finnhub import _to_envelope as finnhub_envelope
from app.providers.news.multi import MultiSourceNewsAdapter, NewsFetchResult


def test_alpaca_news_payload_maps_to_provider_envelope() -> None:
    received_at = datetime(2026, 7, 24, 18, tzinfo=UTC)
    envelope = alpaca_envelope(
        {
            "id": 42,
            "headline": "Apple announces quarterly results",
            "summary": "Revenue increased year over year.",
            "source": "Business Wire",
            "url": "https://example.com/apple-results",
            "created_at": "2026-07-24T17:30:00Z",
            "symbols": ["AAPL"],
        },
        requested_symbols=["AAPL"],
        received_at=received_at,
    )

    assert envelope is not None
    assert envelope.provider is EventProvider.ALPACA
    assert envelope.provider_event_id == "42"
    assert envelope.symbols == ("AAPL",)
    assert envelope.published_at == datetime(2026, 7, 24, 17, 30, tzinfo=UTC)


def test_finnhub_news_payload_keeps_requested_and_related_symbols() -> None:
    received_at = datetime(2026, 7, 24, 18, tzinfo=UTC)
    envelope = finnhub_envelope(
        {
            "id": 99,
            "headline": "Chipmakers respond to new product launch",
            "summary": "The update mentioned multiple semiconductor companies.",
            "source": "Reuters",
            "url": "https://example.com/chips",
            "datetime": 1784914200,
            "related": "AMD,NVDA",
            "category": "company",
        },
        symbol="NVDA",
        received_at=received_at,
    )

    assert envelope is not None
    assert envelope.provider is EventProvider.FINNHUB
    assert envelope.symbols == ("AMD", "NVDA")
    assert envelope.source_name == "Reuters"


async def test_refresh_news_normalizes_scores_and_persists_both_providers(
    client: AsyncClient,
    monkeypatch,
) -> None:
    now = datetime.now(UTC)
    envelopes = (
        ProviderEventEnvelope(
            provider=EventProvider.ALPACA,
            provider_event_id="alpaca-live-1",
            source_name="Business Wire",
            source_url="https://example.com/aapl-live",
            headline="Apple raises guidance after quarterly results",
            summary="Management increased its full-year outlook.",
            published_at=now,
            received_at=now,
            symbols=("AAPL",),
            raw_category="guidance",
        ),
        ProviderEventEnvelope(
            provider=EventProvider.FINNHUB,
            provider_event_id="finnhub-live-1",
            source_name="Reuters",
            source_url="https://example.com/msft-live",
            headline="Microsoft announces a new product launch",
            summary="The company introduced a new enterprise product.",
            published_at=now,
            received_at=now,
            symbols=("MSFT",),
            raw_category="product",
        ),
    )

    async def fake_fetch(self, **kwargs) -> NewsFetchResult:
        assert set(kwargs["symbols"]) >= {"AAPL", "MSFT"}
        return NewsFetchResult(
            envelopes=envelopes,
            providers=("alpaca", "finnhub"),
        )

    monkeypatch.setattr(MultiSourceNewsAdapter, "fetch_company_news", fake_fetch)

    first = await client.post("/api/v1/feed/refresh")
    second = await client.post("/api/v1/feed/refresh")

    assert first.status_code == 200
    assert first.json()["providers"] == ["alpaca", "finnhub"]
    assert first.json()["fetched"] == 2
    assert first.json()["inserted"] == 2
    assert second.json()["inserted"] == 0
    assert second.json()["duplicates_skipped"] == 2

    feed = await client.get("/api/v1/feed", params={"limit": 100})
    headlines = {item["headline"] for item in feed.json()["items"]}
    assert "Apple raises guidance after quarterly results" in headlines
    assert "Microsoft announces a new product launch" in headlines
