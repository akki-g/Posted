"""Human-owned event deduplication exercise.

Implementation contract: guides/02-EVENT-PIPELINE.md.
The coding agent must not implement or replace this module unless explicitly asked.
"""

import re
from dataclasses import dataclass, field, replace
from difflib import SequenceMatcher
from functools import lru_cache
from typing import Sequence

from app.domain.enums import DedupeReason, EventProvider
from app.domain.models import (
    CanonicalEvent,
    DedupePolicy,
    DedupeResult,
    DuplicateCluster,
    EventSourceRef,
)

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

    # Include primary_source defensively. Normalized events already include it in
    # sources, but retaining it here prevents evidence loss for imported records that
    # predate that invariant.
    sources = {source for event in events for source in (*event.sources, event.primary_source)}
    return tuple(sorted(sources, key=_source_sort_key))


@lru_cache(maxsize=8192)
def _normalized_title(headline: str) -> str:
    """Create and cache a deterministic comparison form while retaining numbers."""

    tokens = re.findall(r"[a-z0-9]+", headline.lower())
    return " ".join(token for token in tokens if token not in _TITLE_STOP_WORDS)


def _title_similarity(left: str, right: str) -> float:
    """Return a deterministic 0..1 similarity for two normalized headlines."""

    left_normalized = _normalized_title(left)
    right_normalized = _normalized_title(right)
    if not left_normalized or not right_normalized:
        return 0.0
    return SequenceMatcher(None, left_normalized, right_normalized, autojunk=False).ratio()


def _has_strong_conflict(left: CanonicalEvent, right: CanonicalEvent) -> bool:
    """Return whether authoritative identifiers prove these are different events."""

    conflicting_accession = bool(
        left.accession_number
        and right.accession_number
        and left.accession_number != right.accession_number
    )
    conflicting_cik = bool(left.cik and right.cik and left.cik != right.cik)

    return conflicting_accession or conflicting_cik


def _source_identities(event: CanonicalEvent) -> frozenset[tuple[EventProvider, str]]:
    """Return every usable provider identity retained on a canonical event."""

    # Looking through all merged sources is important for incremental syncs: a new
    # vendor record may match yesterday's secondary source rather than today's primary.
    return frozenset(
        (source.provider, provider_event_id)
        for source in (*event.sources, event.primary_source)
        if (provider_event_id := (source.provider_event_id or "").strip())
    )


def _candidate_index_keys(event: CanonicalEvent) -> tuple[tuple[object, ...], ...]:
    """Return keys that can possibly satisfy one branch of the matching ladder."""

    keys: list[tuple[object, ...]] = []
    if event.accession_number:
        keys.append(("accession", event.accession_number))
    keys.extend(
        ("provider", provider, provider_event_id)
        for provider, provider_event_id in sorted(
            _source_identities(event),
            key=lambda identity: (identity[0].value, identity[1]),
        )
    )
    if event.canonical_url:
        keys.append(("url", event.canonical_url))
    if event.fingerprint:
        keys.append(("fingerprint", event.fingerprint))

    # Fuzzy matching is impossible without a shared company identity and event type,
    # so these keys safely prune unrelated groups before the more expensive title test.
    keys.extend(("security", security_id, event.event_type) for security_id in event.security_ids)
    if event.cik:
        keys.append(("cik", event.cik, event.event_type))
    return tuple(keys)


def _duplicate_reason(
    left: CanonicalEvent,
    right: CanonicalEvent,
    policy: DedupePolicy,
) -> DedupeReason | None:
    """Return the strongest evidence that permits a conservative pairwise merge."""

    if _has_strong_conflict(left, right):
        return None

    # Each exact comparison must require non-empty values. Without the guard,
    # ``None == None`` would incorrectly merge unrelated events.
    if (
        left.accession_number
        and right.accession_number
        and left.accession_number == right.accession_number
    ):
        return DedupeReason.ACCESSION_NUMBER

    if not _source_identities(left).isdisjoint(_source_identities(right)):
        return DedupeReason.PROVIDER_EVENT_ID

    if left.canonical_url and left.canonical_url == right.canonical_url:
        return DedupeReason.CANONICAL_URL

    if left.fingerprint and left.fingerprint == right.fingerprint:
        return DedupeReason.STRONG_FINGERPRINT

    same_company = bool(set(left.security_ids).intersection(right.security_ids)) or bool(
        left.cik and left.cik == right.cik
    )
    compatible_type = left.event_type == right.event_type
    close_in_time = abs(left.occurred_at - right.occurred_at) <= policy.fuzzy_window
    similar_title = (
        _title_similarity(left.headline, right.headline) >= policy.title_similarity_threshold
    )

    if same_company and compatible_type and close_in_time and similar_title:
        return DedupeReason.SEMANTIC_CANDIDATE

    return None


def _merge_group(
    events: Sequence[CanonicalEvent],
    *,
    policy: DedupePolicy,
) -> CanonicalEvent:
    """Merge a non-empty group whose members have already passed duplicate checks."""

    if not events:
        raise ValueError("cannot merge an empty event group")

    ordered = sorted(events, key=_event_sort_key)

    canonical_base = min(ordered, key=lambda event: _preferred_event_sort_key(event, policy))

    sources = _unique_sorted_sources(ordered)
    primary_source = min(sources, key=lambda source: _preferred_source_sort_key(source, policy))

    summaries = [event.summary for event in ordered if event.summary]
    summary = max(summaries, key=lambda value: (len(value), value), default=None)

    priority_ordered = sorted(
        ordered,
        key=lambda event: _preferred_event_sort_key(event, policy),
    )

    non_empty_form_types = [event.form_type for event in priority_ordered if event.form_type]
    non_empty_urls = [event.canonical_url for event in priority_ordered if event.canonical_url]
    ciks = sorted({event.cik for event in ordered if event.cik})
    accessions = sorted({event.accession_number for event in ordered if event.accession_number})

    # Do not rely on ``assert`` for data safety: optimized Python can remove asserts.
    # Reaching this branch means a caller bypassed the conflict gate, so fail closed.
    if len(ciks) > 1 or len(accessions) > 1:
        raise ValueError("cannot merge events with conflicting strong identifiers")

    return replace(
        canonical_base,
        occurred_at=min(event.occurred_at for event in ordered),
        first_seen_at=min(event.first_seen_at for event in ordered),
        last_seen_at=max(event.last_seen_at for event in ordered),
        primary_source=primary_source,
        sources=sources,
        security_ids=tuple(
            sorted(
                {security_id for event in ordered for security_id in event.security_ids},
                key=str,
            )
        ),
        symbols=tuple(sorted({symbol for event in ordered for symbol in event.symbols})),
        summary=summary,
        cik=ciks[0] if ciks else None,
        accession_number=accessions[0] if accessions else None,
        form_type=non_empty_form_types[0] if non_empty_form_types else None,
        canonical_url=non_empty_urls[0] if non_empty_urls else None,
    )


def _validate_policy(policy: DedupePolicy) -> None:
    """Reject settings that would silently turn conservative matching into match-all."""

    if not 0.0 <= policy.title_similarity_threshold <= 1.0:
        raise ValueError("title_similarity_threshold must be between 0 and 1")
    if policy.fuzzy_window.total_seconds() < 0:
        raise ValueError("fuzzy_window must not be negative")


def deduplicate_events(
    events: Sequence[CanonicalEvent],
    *,
    policy: DedupePolicy,
) -> DedupeResult:
    """Conservatively cluster duplicate events and merge source evidence."""

    _validate_policy(policy)
    ordered = sorted(events, key=_event_sort_key)
    groups: list[_CandidateGroup] = []
    candidate_index: dict[tuple[object, ...], set[int]] = {}

    for event in ordered:
        matching_group_index: int | None = None
        matching_reasons: set[DedupeReason] = set()
        event_candidate_keys = _candidate_index_keys(event)

        # Exact identities and company/type keys reduce the normal case from scanning
        # every prior group to checking only groups that can actually match. Sorting
        # the indexes retains the original deterministic "first compatible group" rule.
        candidate_group_indexes = sorted(
            {
                group_index
                for key in event_candidate_keys
                for group_index in candidate_index.get(key, ())
            }
        )
        for group_index in candidate_group_indexes:
            group = groups[group_index]
            # One conflicting authoritative identity blocks the entire group. This
            # deliberately favors a visible duplicate over erasing a distinct filing.
            if any(_has_strong_conflict(event, member) for member in group.events):
                continue

            reasons_against_group = {
                reason
                for member in group.events
                if (reason := _duplicate_reason(event, member, policy)) is not None
            }
            if reasons_against_group:
                matching_group_index = group_index
                matching_reasons = reasons_against_group
                break

        if matching_group_index is None:
            groups.append(_CandidateGroup(events=[event]))
            matching_group_index = len(groups) - 1
        else:
            matching_group = groups[matching_group_index]
            matching_group.events.append(event)
            matching_group.reasons.update(matching_reasons)

        for key in event_candidate_keys:
            candidate_index.setdefault(key, set()).add(matching_group_index)

    output_events: list[CanonicalEvent] = []
    clusters: list[DuplicateCluster] = []

    for group in groups:
        if len(group.events) == 1:
            output_events.append(group.events[0])
            continue

        canonical = _merge_group(group.events, policy=policy)
        output_events.append(canonical)
        merged_event_ids = tuple(
            sorted(
                {event.event_id for event in group.events if event.event_id != canonical.event_id},
                key=str,
            )
        )
        clusters.append(
            DuplicateCluster(
                canonical=canonical,
                merged_event_ids=merged_event_ids,
                reasons=tuple(sorted(group.reasons, key=lambda reason: reason.value)),
            )
        )

    return DedupeResult(
        events=tuple(sorted(output_events, key=_event_sort_key)),
        clusters=tuple(sorted(clusters, key=lambda cluster: _event_sort_key(cluster.canonical))),
    )
