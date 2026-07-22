"""Human-owned event deduplication exercise.

Implementation contract: guides/02-EVENT-PIPELINE.md.
The coding agent must not implement or replace this module unless explicitly asked.
"""

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Sequence

from app.domain.enums import DedupeReason, EventProvider
from app.domain.models import CanonicalEvent, DedupePolicy, DedupeResult, EventSourceRef

_TITLE_STOP_WORDS = frozenset({"a", "an", "and", "for", "of", "the", "to"})


@dataclass(slots=True)
class _CandidateGroup:
    """Mutable working state used while building deterministic duplicate clusters."""

    events: list[CanonicalEvent] = field(default_factory=list)
    reasons: set[DedupeReason] = field(default_factory=set)


def _event_sort_key(event: CanonicalEvent) -> tuple[str, str, str]:
    """Return a stable order independent of the caller's input sequence."""

    return (event.occurred_at.isoformat(), event.event_type.value, str(event.event_id))


def _source_sort_key(source: EventSourceRef) -> tuple[str, str, str, str]:
    """Return a stable order for merged source evidence."""

    return (
        source.provider.value,
        source.provider_event_id or "",
        source.source_url or "",
        source.source_name,
    )


def _provider_rank(provider: EventProvider, policy: DedupePolicy) -> int:
    """Return configured source priority, with unconfigured providers ranked last."""

    priorities = policy.provider_priority
    if priorities is None:
        return 10_000
    return priorities.get(provider, 10_000)


def _preferred_event_sort_key(
    event: CanonicalEvent,
    policy: DedupePolicy,
) -> tuple[int, tuple[str, str, str]]:
    """Order canonical candidates by policy priority and deterministic identity."""

    return (_provider_rank(event.primary_source.provider, policy), _event_sort_key(event))


def _preferred_source_sort_key(
    source: EventSourceRef,
    policy: DedupePolicy,
) -> tuple[int, tuple[str, str, str, str]]:
    """Order primary-source candidates by policy priority and stable source fields."""

    return (_provider_rank(source.provider, policy), _source_sort_key(source))


def _unique_sorted_sources(events: Sequence[CanonicalEvent]) -> tuple[EventSourceRef, ...]:
    """Union exact source records from events and return them deterministically."""

    sources = {source for event in events for source in event.sources}
    return tuple(sorted(sources, key=_source_sort_key))


def _normalized_title(headline: str) -> str:
    """Create a small, deterministic comparison form while retaining numbers."""

    tokens = re.findall(r"[a-z0-9]+", headline.lower())
    return " ".join(token for token in tokens if token not in _TITLE_STOP_WORDS)


def _title_similarity(left: str, right: str) -> float:
    """Return a deterministic 0..1 similarity for two normalized headlines."""

    left_normalized = _normalized_title(left)
    right_normalized = _normalized_title(right)
    if not left_normalized or not right_normalized:
        return 0.0
    return SequenceMatcher(None, left_normalized, right_normalized, autojunk=False).ratio()


def deduplicate_events(
    events: Sequence[CanonicalEvent],
    *,
    policy: DedupePolicy,
) -> DedupeResult:
    """Conservatively cluster duplicate events and merge source evidence."""
    raise NotImplementedError("Follow guides/02-EVENT-PIPELINE.md")
