"""Human-owned event normalization exercise.

Implementation contract: guides/02-EVENT-PIPELINE.md.
The coding agent must not implement or replace this module unless explicitly asked.
"""

import re
from datetime import UTC, datetime
from hashlib import sha256
from html import unescape
from typing import Protocol, Sequence
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import UUID

from app.domain.enums import (
    EventProvider,
    EventType,
    RejectionReason,
)
from app.domain.models import (
    CanonicalEvent,
    EventSourceRef,
    ProviderEventEnvelope,
    RejectedEvent,
    SecurityMatch,
)


class EventSecurityResolver(Protocol):
    def __call__(
        self,
        *,
        symbols: Sequence[str],
        cik: str | None,
    ) -> tuple[SecurityMatch, ...]: ...


_TRACKING_QUERY_PARAMETERS = {
    "_hsenc",
    "_hsmi",
    "dclid",
    "fbclid",
    "gclid",
    "mc_cid",
    "mc_eid",
    "msclkid",
}

# Keep classification data at module scope. Besides avoiding a new dict and tuple for
# every event, this makes the taxonomy easy to review and test as one policy table.
_CATEGORY_MAP = {
    "earnings": EventType.EARNINGS,
    "guidance": EventType.GUIDANCE,
    "merger": EventType.MERGER_ACQUISITION,
    "mergers and acquisitions": EventType.MERGER_ACQUISITION,
    "m&a": EventType.MERGER_ACQUISITION,
    "acquisition": EventType.MERGER_ACQUISITION,
    "leadership": EventType.LEADERSHIP,
    "dividend": EventType.DIVIDEND,
    "buyback": EventType.BUYBACK,
    "regulatory": EventType.REGULATORY_LEGAL,
    "legal": EventType.REGULATORY_LEGAL,
    "cybersecurity": EventType.CYBERSECURITY,
    "analyst": EventType.ANALYST_ACTION,
    "insider": EventType.INSIDER_ACTIVITY,
    "product": EventType.PRODUCT_OPERATIONAL,
    "filing": EventType.SEC_FILING,
    "sec filing": EventType.SEC_FILING,
}

# Word boundaries avoid accidental substring matches such as "insider" inside an
# unrelated longer token. Inflections are listed explicitly so the rules stay
# deterministic and inspectable rather than behaving like an opaque classifier.
_HEADLINE_RULES = (
    (re.compile(r"\b(?:cybersecurity|data breach|ransomware)\b"), EventType.CYBERSECURITY),
    (
        re.compile(r"\b(?:guidance|outlook|forecasts?|forecasted|forecasting)\b"),
        EventType.GUIDANCE,
    ),
    (
        re.compile(r"\b(?:merger|acquisition|acquire|acquires|acquired|acquiring)\b"),
        EventType.MERGER_ACQUISITION,
    ),
    (
        re.compile(
            r"\b(?:chief executive|ceo|resigns?|resigned|appoints?|appointed|appointment)\b"
        ),
        EventType.LEADERSHIP,
    ),
    (re.compile(r"\bdividends?\b"), EventType.DIVIDEND),
    (re.compile(r"\b(?:buybacks?|share repurchases?)\b"), EventType.BUYBACK),
    (
        re.compile(r"\b(?:lawsuits?|antitrust|regulators?|regulatory)\b"),
        EventType.REGULATORY_LEGAL,
    ),
    (re.compile(r"\b(?:analysts?|upgrades?|downgrades?)\b"), EventType.ANALYST_ACTION),
    (re.compile(r"\binsider(?:s| activity| trading)?\b"), EventType.INSIDER_ACTIVITY),
    (
        re.compile(r"\b(?:product launch|launches|launched|unveils|unveiled)\b"),
        EventType.PRODUCT_OPERATIONAL,
    ),
    (re.compile(r"\b(?:earnings|quarterly results)\b"), EventType.EARNINGS),
)


def _is_timezone_aware(value: datetime) -> bool:
    """Return whether a datetime identifies an actual UTC offset."""

    return value.tzinfo is not None and value.utcoffset() is not None


def _normalize_text(value: str) -> str:
    """Decode HTML entities and collapse all runs of whitespace."""

    return " ".join(unescape(value).split())


def _normalize_optional_text(value: str | None) -> str | None:
    """Normalize optional provider text and turn an empty result into None."""

    if value is None:
        return None
    normalized = _normalize_text(value)
    return normalized or None


def _normalize_symbols(symbols: Sequence[str]) -> tuple[str, ...]:
    """Return non-empty provider symbols uppercased, deduplicated, and sorted."""

    return tuple(sorted({symbol.strip().upper() for symbol in symbols if symbol.strip()}))


def _normalize_identifier(value: str | None) -> str | None:
    """Trim a provider identifier without changing its potentially case-sensitive value."""

    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _normalize_cik(value: str | None) -> str | None:
    """Canonicalize numeric SEC CIKs to the SEC's ten-digit representation."""

    normalized = _normalize_identifier(value)
    if normalized is None:
        return None
    compact = "".join(normalized.split())
    return compact.zfill(10) if compact.isdigit() else compact


def _normalize_accession_number(value: str | None) -> str | None:
    """Remove accidental whitespace while retaining the SEC accession separators."""

    normalized = _normalize_identifier(value)
    if normalized is None:
        return None
    return "".join(normalized.split()).upper()


def _canonicalize_url(value: str | None) -> str | None:
    """Normalize a source URL and remove common click-tracking parameters."""

    if value is None or not value.strip():
        return None

    raw_url = value.strip()
    try:
        parts = urlsplit(raw_url)
        port = parts.port
    except ValueError:
        return None

    scheme = parts.scheme.lower()
    hostname = (parts.hostname or "").lower()
    # Only absolute web URLs are safe exact-match evidence. The original value still
    # remains on EventSourceRef for auditing, while malformed/relative values are kept
    # out of canonical identity so placeholders such as "N/A" cannot merge stories.
    if scheme not in {"http", "https"} or not hostname:
        return None

    if ":" in hostname and not hostname.startswith("["):
        hostname = f"[{hostname}]"

    default_port = (scheme == "http" and port == 80) or (scheme == "https" and port == 443)
    netloc = hostname if port is None or default_port else f"{hostname}:{port}"

    query_items = [
        (key, item)
        for key, item in parse_qsl(parts.query, keep_blank_values=True)
        if not key.lower().startswith("utm_") and key.lower() not in _TRACKING_QUERY_PARAMETERS
    ]
    query = urlencode(sorted(query_items))

    # Empty and slash-only paths identify the same HTTP resource in practice. Using
    # one representation prevents a tracking-free URL from missing an exact match.
    path = parts.path or "/"
    return urlunsplit((scheme, netloc, path, query, ""))


def _classify_event(envelope: ProviderEventEnvelope) -> EventType:
    """Classify from structured evidence first, then conservative headline rules."""

    if envelope.provider is EventProvider.SEC or envelope.accession_number or envelope.form_type:
        return EventType.SEC_FILING

    raw_category = _normalize_optional_text(envelope.raw_category) or ""
    category = re.sub(r"[\s_-]+", " ", raw_category.casefold())
    if category in _CATEGORY_MAP:
        return _CATEGORY_MAP[category]

    headline = _normalize_text(envelope.headline).casefold()
    for pattern, event_type in _HEADLINE_RULES:
        if pattern.search(headline):
            return event_type

    return EventType.GENERAL_NEWS


def _fingerprint(
    envelope: ProviderEventEnvelope,
    *,
    event_type: EventType,
    headline: str,
    symbols: tuple[str, ...],
    canonical_url: str | None,
) -> str:
    """Build a deterministic identity fingerprint from strongest available evidence."""

    accession_number = _normalize_accession_number(envelope.accession_number)
    provider_event_id = _normalize_identifier(envelope.provider_event_id)

    if accession_number:
        seed = f"accession|{accession_number}"
    elif provider_event_id:
        # Include the provider because two providers may reuse the same external ID.
        seed = f"provider|{envelope.provider.value}|{provider_event_id}"
    elif canonical_url:
        seed = f"url|{canonical_url}"
    else:
        # `_normalize_symbols` already sorts symbols, making the join deterministic.
        company = _normalize_cik(envelope.cik) or ",".join(symbols) or "unresolved"
        day = envelope.published_at.astimezone(UTC).date().isoformat()

        seed = "|".join(
            (
                "semantic",
                company,
                event_type.value,
                day,
                _normalize_text(headline).casefold(),
            )
        )

    return sha256(seed.encode("utf-8")).hexdigest()


def normalize_event(
    envelope: ProviderEventEnvelope,
    *,
    resolve_securities: EventSecurityResolver,
    event_id: UUID,
) -> CanonicalEvent | RejectedEvent:
    """Convert one provider-neutral envelope to Posted's canonical event model."""

    if not _is_timezone_aware(envelope.published_at) or not _is_timezone_aware(
        envelope.received_at
    ):
        return RejectedEvent(
            envelope=envelope,
            reason=RejectionReason.INVALID_TIMESTAMP,
            detail="published_at and received_at must be timezone-aware",
        )

    headline = _normalize_text(envelope.headline)
    if headline == "":
        return RejectedEvent(
            envelope=envelope,
            reason=RejectionReason.EMPTY_HEADLINE,
            detail="headline is empty after normalization",
        )

    summary = _normalize_optional_text(envelope.summary)
    symbols = _normalize_symbols(envelope.symbols)
    canonical_url = _canonicalize_url(envelope.source_url)
    event_type = _classify_event(envelope)
    cik = _normalize_cik(envelope.cik)
    accession_number = _normalize_accession_number(envelope.accession_number)
    provider_event_id = _normalize_identifier(envelope.provider_event_id)
    normalized_form_type = _normalize_optional_text(envelope.form_type)
    form_type = normalized_form_type.upper() if normalized_form_type else None

    # Resolve with canonical identifiers so "320193" and "0000320193" cannot take
    # different lookup paths merely because two providers formatted the CIK differently.
    matches = resolve_securities(symbols=symbols, cik=cik)

    security_ids = tuple(
        sorted(
            {match.security_id for match in matches},
            key=str,
        )
    )

    source = EventSourceRef(
        provider=envelope.provider,
        source_name=_normalize_text(envelope.source_name),
        source_url=envelope.source_url,
        provider_event_id=provider_event_id,
    )
    occurred_at = envelope.published_at.astimezone(UTC)
    received_at = envelope.received_at.astimezone(UTC)

    return CanonicalEvent(
        event_id=event_id,
        event_type=event_type,
        headline=headline,
        summary=summary,
        occurred_at=occurred_at,
        first_seen_at=received_at,
        last_seen_at=received_at,
        primary_source=source,
        sources=(source,),
        security_ids=security_ids,
        symbols=symbols,
        cik=cik,
        accession_number=accession_number,
        form_type=form_type,
        canonical_url=canonical_url,
        fingerprint=_fingerprint(
            envelope,
            event_type=event_type,
            headline=headline,
            symbols=symbols,
            canonical_url=canonical_url,
        ),
    )
