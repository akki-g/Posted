"""Human-owned event normalization exercise.

Implementation contract: guides/02-EVENT-PIPELINE.md.
The coding agent must not implement or replace this module unless explicitly asked.
"""

from datetime import datetime
from html import unescape
from typing import Protocol, Sequence
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import UUID

from app.domain.models import (
    CanonicalEvent,
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


_TRACKING_QUERY_PARAMETERS = {"fbclid", "gclid"}


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


def _canonicalize_url(value: str | None) -> str | None:
    """Normalize a source URL and remove common click-tracking parameters."""

    if value is None or not value.strip():
        return None

    raw_url = value.strip()
    try:
        parts = urlsplit(raw_url)
        port = parts.port
    except ValueError:
        return raw_url

    scheme = parts.scheme.lower()
    hostname = (parts.hostname or "").lower()
    if not scheme or not hostname:
        return raw_url

    if ":" in hostname and not hostname.startswith("["):
        hostname = f"[{hostname}]"

    default_port = (scheme == "http" and port == 80) or (scheme == "https" and port == 443)
    netloc = hostname if port is None or default_port else f"{hostname}:{port}"

    query_items = [
        (key, item)
        for key, item in parse_qsl(parts.query, keep_blank_values=True)
        if not key.lower().startswith("utm_")
        and key.lower() not in _TRACKING_QUERY_PARAMETERS
    ]
    query = urlencode(sorted(query_items))

    return urlunsplit((scheme, netloc, parts.path, query, ""))


def normalize_event(
    envelope: ProviderEventEnvelope,
    *,
    resolve_securities: EventSecurityResolver,
    event_id: UUID,
) -> CanonicalEvent | RejectedEvent:
    """Convert one provider-neutral envelope to Posted's canonical event model."""
    raise NotImplementedError("Follow guides/02-EVENT-PIPELINE.md")
