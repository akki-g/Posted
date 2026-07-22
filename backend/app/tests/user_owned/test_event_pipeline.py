from datetime import datetime, timedelta

import pytest

from app.domain.enums import DedupeReason, EventProvider, EventType
from app.domain.models import DedupePolicy, ProviderEventEnvelope, RejectedEvent
from app.events.dedupe import deduplicate_events
from app.events.normalize import normalize_event
from app.tests.user_owned.factories import (
    NOW,
    canonical_event,
    resolve_event_securities,
    stable_id,
)

pytestmark = pytest.mark.user_owned


def envelope(**overrides: object) -> ProviderEventEnvelope:
    values = {
        "provider": EventProvider.SEC,
        "provider_event_id": "sec-1",
        "source_name": "SEC EDGAR",
        "source_url": "https://www.sec.gov/example?utm_source=test",
        "headline": "  Apple &amp; Co. files  8-K  ",
        "summary": None,
        "published_at": NOW,
        "received_at": NOW + timedelta(minutes=1),
        "symbols": ("aapl", "AAPL"),
        "cik": "0000320193",
        "accession_number": "0000320193-26-000001",
        "form_type": "8-K",
        "raw_category": "filing",
    }
    values.update(overrides)
    return ProviderEventEnvelope(**values)  # type: ignore[arg-type]


def test_normalize_sec_event_preserves_strong_identity() -> None:
    result = normalize_event(
        envelope(),
        resolve_securities=resolve_event_securities,
        event_id=stable_id("normalized-sec"),
    )
    assert not isinstance(result, RejectedEvent)
    assert result.event_type is EventType.SEC_FILING
    assert result.accession_number == "0000320193-26-000001"
    assert result.symbols == ("AAPL",)
    assert "utm_source" not in (result.canonical_url or "")
    assert result.headline == "Apple & Co. files 8-K"


def test_normalize_rejects_naive_time() -> None:
    result = normalize_event(
        envelope(published_at=datetime(2026, 7, 22, 12)),
        resolve_securities=resolve_event_securities,
        event_id=stable_id("naive"),
    )
    assert isinstance(result, RejectedEvent)


def test_same_accession_number_merges() -> None:
    first = canonical_event("filing-1", accession_number="0001")
    second = canonical_event(
        "filing-2",
        headline="Results attached to current report",
        provider=EventProvider.SEC,
        accession_number="0001",
    )
    result = deduplicate_events([first, second], policy=DedupePolicy())
    assert len(result.events) == 1
    assert DedupeReason.ACCESSION_NUMBER in result.clusters[0].reasons


def test_similar_titles_for_different_companies_do_not_merge() -> None:
    first = canonical_event("aapl-results", symbol="AAPL")
    second = canonical_event("msft-results", symbol="MSFT")
    result = deduplicate_events([first, second], policy=DedupePolicy())
    assert len(result.events) == 2


def test_dedupe_is_order_independent_and_idempotent() -> None:
    first = canonical_event("story-1", provider_event_id="same-story")
    second = canonical_event("story-2", provider_event_id="same-story")
    policy = DedupePolicy()
    forward = deduplicate_events([first, second], policy=policy)
    reverse = deduplicate_events([second, first], policy=policy)
    assert forward == reverse
    repeated = deduplicate_events(forward.events, policy=policy)
    assert repeated.events == forward.events
