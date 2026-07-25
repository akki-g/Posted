from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from app.domain.enums import DedupeReason, EventProvider, EventType
from app.domain.models import DedupePolicy, ProviderEventEnvelope, RejectedEvent, SecurityMatch
from app.events.dedupe import deduplicate_events
from app.events.normalize import normalize_event
from app.tests.user_owned.factories import canonical_event, stable_id

NOW = datetime(2026, 7, 22, 12, tzinfo=UTC)


def _envelope(**overrides: object) -> ProviderEventEnvelope:
    values = {
        "provider": EventProvider.FMP,
        "provider_event_id": None,
        "source_name": " Financial Wire ",
        "source_url": None,
        "headline": "Company reports quarterly results",
        "summary": None,
        "published_at": NOW,
        "received_at": NOW + timedelta(minutes=1),
        "symbols": ("aapl",),
        "cik": None,
        "accession_number": None,
        "form_type": None,
        "raw_category": None,
    }
    values.update(overrides)
    return ProviderEventEnvelope(**values)  # type: ignore[arg-type]


def _no_security_matches(*, symbols: object, cik: object) -> tuple[SecurityMatch, ...]:
    del symbols, cik
    return ()


def test_normalize_canonicalizes_identifiers_before_resolution() -> None:
    resolver_calls: list[tuple[tuple[str, ...], str | None]] = []

    def resolver(*, symbols: Sequence[str], cik: str | None) -> tuple[SecurityMatch, ...]:
        resolver_calls.append((tuple(symbols), cik))
        return ()

    result = normalize_event(
        _envelope(
            provider_event_id=" story-42 ",
            source_url="HTTPS://Example.COM:443?utm_source=email&b=2&a=1#fragment",
            headline="  Apple &amp; Co. files an update ",
            symbols=(" aapl ", "AAPL"),
            cik=" 320193 ",
            accession_number=" 0000320193-26-000001 ",
            form_type=" 8-K ",
        ),
        resolve_securities=resolver,
        event_id=stable_id("normalized-identifiers"),
    )

    assert not isinstance(result, RejectedEvent)
    assert resolver_calls == [(("AAPL",), "0000320193")]
    assert result.cik == "0000320193"
    assert result.accession_number == "0000320193-26-000001"
    assert result.form_type == "8-K"
    assert result.primary_source.provider_event_id == "story-42"
    assert result.primary_source.source_url is not None
    assert result.canonical_url == "https://example.com/?a=1&b=2"
    assert result.headline == "Apple & Co. files an update"


def test_structured_category_beats_conflicting_headline_keywords() -> None:
    result = normalize_event(
        _envelope(raw_category="earnings", headline="Company faces regulatory lawsuit"),
        resolve_securities=_no_security_matches,
        event_id=stable_id("structured-category"),
    )

    assert not isinstance(result, RejectedEvent)
    assert result.event_type is EventType.EARNINGS


def test_headline_classifier_handles_keyword_at_start() -> None:
    result = normalize_event(
        _envelope(headline="CEO appointed to lead next phase"),
        resolve_securities=_no_security_matches,
        event_id=stable_id("leadership-headline"),
    )

    assert not isinstance(result, RejectedEvent)
    assert result.event_type is EventType.LEADERSHIP


def test_semantic_fingerprint_uses_canonical_values() -> None:
    first = normalize_event(
        _envelope(cik="320193", headline="Apple &amp; Co. reports   results"),
        resolve_securities=_no_security_matches,
        event_id=stable_id("semantic-first"),
    )
    second = normalize_event(
        _envelope(cik="0000320193", headline="Apple & Co. reports results"),
        resolve_securities=_no_security_matches,
        event_id=stable_id("semantic-second"),
    )

    assert not isinstance(first, RejectedEvent)
    assert not isinstance(second, RejectedEvent)
    assert first.fingerprint == second.fingerprint


def test_invalid_url_is_auditable_but_not_identity_evidence() -> None:
    result = normalize_event(
        _envelope(source_url="N/A"),
        resolve_securities=_no_security_matches,
        event_id=stable_id("invalid-source-url"),
    )

    assert not isinstance(result, RejectedEvent)
    assert result.primary_source.source_url == "N/A"
    assert result.canonical_url is None


def test_empty_strong_identifiers_do_not_merge_unrelated_companies() -> None:
    first = canonical_event("missing-id-aapl", symbol="AAPL")
    second = canonical_event("missing-id-msft", symbol="MSFT")

    result = deduplicate_events((first, second), policy=DedupePolicy())

    assert len(result.events) == 2
    assert result.clusters == ()


def test_same_non_empty_fingerprint_merges() -> None:
    first = canonical_event("fingerprint-first")
    second = replace(
        canonical_event("fingerprint-second"),
        fingerprint=first.fingerprint,
    )

    result = deduplicate_events((first, second), policy=DedupePolicy())

    assert len(result.events) == 1
    assert result.clusters[0].reasons == (DedupeReason.STRONG_FINGERPRINT,)


def test_conflicting_accessions_block_even_matching_fingerprints() -> None:
    first = canonical_event("filing-a", accession_number="0001")
    second = replace(
        canonical_event("filing-b", accession_number="0002"),
        fingerprint=first.fingerprint,
    )

    result = deduplicate_events((first, second), policy=DedupePolicy())

    assert len(result.events) == 2


def test_merge_preserves_timing_summary_sources_and_priority() -> None:
    earlier = replace(
        canonical_event(
            "wire-story",
            provider=EventProvider.FMP,
            provider_event_id="wire-1",
        ),
        occurred_at=NOW - timedelta(minutes=5),
        first_seen_at=NOW,
        last_seen_at=NOW,
        summary="Short summary.",
    )
    authoritative = replace(
        canonical_event(
            "sec-story",
            provider=EventProvider.SEC,
            provider_event_id="sec-1",
        ),
        occurred_at=NOW,
        first_seen_at=NOW + timedelta(minutes=1),
        last_seen_at=NOW + timedelta(minutes=10),
        summary="A longer and more informative summary of the same event.",
        fingerprint=earlier.fingerprint,
    )
    policy = DedupePolicy(provider_priority={EventProvider.SEC: 0, EventProvider.FMP: 10})

    result = deduplicate_events((earlier, authoritative), policy=policy)
    merged = result.events[0]

    assert merged.event_id == authoritative.event_id
    assert merged.primary_source.provider is EventProvider.SEC
    assert merged.occurred_at == earlier.occurred_at
    assert merged.first_seen_at == earlier.first_seen_at
    assert merged.last_seen_at == authoritative.last_seen_at
    assert merged.summary == authoritative.summary
    assert len(merged.sources) == 2


def test_incremental_sync_matches_a_previously_merged_secondary_source() -> None:
    wire = canonical_event(
        "original-wire",
        provider=EventProvider.FMP,
        provider_event_id="wire-42",
    )
    sec = replace(
        canonical_event(
            "original-sec",
            provider=EventProvider.SEC,
            provider_event_id="sec-42",
        ),
        fingerprint=wire.fingerprint,
    )
    policy = DedupePolicy(provider_priority={EventProvider.SEC: 0, EventProvider.FMP: 10})
    original = deduplicate_events((wire, sec), policy=policy).events[0]
    repeated_wire = canonical_event(
        "repeated-wire",
        provider=EventProvider.FMP,
        provider_event_id="wire-42",
    )

    result = deduplicate_events((original, repeated_wire), policy=policy)

    assert len(result.events) == 1
    assert DedupeReason.PROVIDER_EVENT_ID in result.clusters[0].reasons


def test_same_cik_can_supply_company_identity_for_semantic_match() -> None:
    first = replace(
        canonical_event("cik-first", provider_event_id=None),
        security_ids=(),
        cik="0000320193",
    )
    second = replace(
        canonical_event("cik-second", provider_event_id=None),
        security_ids=(),
        cik="0000320193",
    )

    result = deduplicate_events((first, second), policy=DedupePolicy())

    assert len(result.events) == 1
    assert result.clusters[0].reasons == (DedupeReason.SEMANTIC_CANDIDATE,)


@pytest.mark.parametrize(
    "policy",
    (
        DedupePolicy(title_similarity_threshold=-0.01),
        DedupePolicy(title_similarity_threshold=1.01),
        DedupePolicy(fuzzy_window=timedelta(seconds=-1)),
    ),
)
def test_invalid_policy_is_rejected(policy: DedupePolicy) -> None:
    with pytest.raises(ValueError):
        deduplicate_events((), policy=policy)
