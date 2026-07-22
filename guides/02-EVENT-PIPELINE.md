# Guide 02 — Event Normalization and Deduplication

[← Portfolio reconciliation](01-PORTFOLIO-RECONCILIATION.md) | [Next: Impact engine →](03-IMPACT-ENGINE.md)

**You write:**

- `backend/app/events/normalize.py`
- `backend/app/events/dedupe.py`

**What exists when you finish:** Posted can combine company news, SEC filings, and other OpenBB-backed records into one canonical stream without issuing three alerts for the same underlying event.

## Before you write code

Do not start this exercise until Guide 01 passes. Open `normalize.py`, `dedupe.py`, `domain/models.py`, `domain/enums.py`, the event test file, and `tests/user_owned/factories.py` together.

Your immediate target is the five starter tests—not every production rule described later in this guide:

```bash
cd backend
uv run pytest -m user_owned app/tests/user_owned/test_event_pipeline.py -q
```

Work on one file at a time. Start with only the first normalization test:

```bash
uv run pytest -m user_owned \
  app/tests/user_owned/test_event_pipeline.py::test_normalize_sec_event_preserves_strong_identity -q
```

Trace that test's `ProviderEventEnvelope` into each `CanonicalEvent` field before coding. First make valid SEC identity survive normalization; next make naive time return `RejectedEvent`; only then open `dedupe.py`. For deduplication, draw two input events on paper and write down which strong identity proves they are the same. If no strong identity or compatible company identity exists, keep them separate.

The later “tests the agent must write” section is a hardening backlog. It is not your first-day checklist.

---

## 1. Why this is core learning

External data rarely agrees with itself.

The same earnings announcement may arrive as:

- an SEC 8-K with an accession number;
- a company press release;
- a wire-service story;
- several rewritten publisher articles;
- an OpenBB result that wraps one of those providers.

If Posted stores provider objects directly, every downstream feature needs provider-specific branches. If Posted merges too aggressively, it can hide genuinely different events. The event pipeline exists to create a conservative, auditable middle layer.

This is the financial-events version of entity resolution.

---

## 2. Separate the two jobs

Do not combine normalization and deduplication into one large function.

### Normalization asks

> How do I represent this one provider record in Posted's vocabulary?

### Deduplication asks

> Do these already-normalized records describe the same underlying event?

Keeping these separate lets you test provider-independent deduplication and add providers without rewriting business logic.

---

## 3. Agent-written input and output contracts

The provider adapters should produce an envelope similar to:

```python
@dataclass(frozen=True)
class ProviderEventEnvelope:
    provider: EventProvider
    provider_event_id: str | None
    source_name: str
    source_url: str | None
    headline: str
    summary: str | None
    published_at: datetime
    received_at: datetime
    symbols: tuple[str, ...]
    cik: str | None
    accession_number: str | None
    form_type: str | None
    raw_category: str | None
```

Your normalization function outputs:

```python
@dataclass(frozen=True)
class CanonicalEvent:
    event_id: UUID
    event_type: EventType
    headline: str
    summary: str | None
    occurred_at: datetime
    first_seen_at: datetime
    last_seen_at: datetime
    primary_source: EventSourceRef
    sources: tuple[EventSourceRef, ...]
    security_ids: tuple[UUID, ...]
    symbols: tuple[str, ...]
    cik: str | None
    accession_number: str | None
    form_type: str | None
    canonical_url: str | None
    fingerprint: str
```

For deterministic tests, do not generate event IDs inside your function. The input should include an ID factory or the provider envelope should already have a candidate UUID assigned by the service.

The security resolver is agent-written:

```python
class EventSecurityResolver(Protocol):
    def resolve(
        self,
        *,
        symbols: Sequence[str],
        cik: str | None,
    ) -> tuple[SecurityMatch, ...]: ...
```

A `SecurityMatch` includes `security_id`, canonical symbol, and match confidence.

---

## 4. File one: `normalize.py`

### Public contract

```python
def normalize_event(
    envelope: ProviderEventEnvelope,
    *,
    resolve_securities: EventSecurityResolver,
    event_id: UUID,
) -> CanonicalEvent | RejectedEvent:
    """Convert one provider-neutral envelope to Posted's canonical event model."""
```

### Required normalization rules

#### Time

- All stored datetimes must be timezone-aware UTC.
- Reject a naive datetime unless the adapter contract explicitly supplies a known source timezone.
- `occurred_at` initially uses the publication or filing acceptance time.
- `first_seen_at` and `last_seen_at` initially equal `received_at`.

#### Text

- Decode harmless HTML entities.
- Collapse repeated whitespace.
- Preserve the readable headline; do not lowercase the display headline.
- Reject empty headlines after normalization.
- Do not manufacture a summary when the provider did not supply one.

#### URLs

- Remove tracking parameters such as common `utm_*` parameters.
- Normalize host casing and default ports.
- Preserve source URLs for auditability.
- Never use a URL alone as proof that two events are identical unless it has been canonicalized.

#### Symbols and company identity

- Normalize symbol casing.
- Deduplicate symbol lists.
- Prefer CIK matches for SEC filings when available.
- Preserve unresolved symbols for audit, even when no security ID is resolved.
- Record match confidence; do not silently turn a weak text match into a definite holding match.

#### Event taxonomy

Start with a deliberately small `EventType` enum:

```text
SEC_FILING
EARNINGS
GUIDANCE
MERGER_ACQUISITION
LEADERSHIP
DIVIDEND
BUYBACK
REGULATORY_LEGAL
CYBERSECURITY
PRODUCT_OPERATIONAL
ANALYST_ACTION
INSIDER_ACTIVITY
GENERAL_NEWS
```

Use deterministic signals in this order:

1. structured provider/SEC metadata;
2. form type and filing description;
3. provider category;
4. conservative headline keywords;
5. `GENERAL_NEWS` fallback.

Do not use an LLM in this module. A later enrichment job may add an AI-generated explanation without changing the canonical event type silently.

#### Fingerprint seed

Normalization produces a stable fingerprint used for exact and near-exact matching. It should include normalized company identity, normalized headline tokens, event date bucket, and strong identifiers when present.

Use a cryptographic hash for stable storage, but remember: the quality comes from the canonical input, not the hash function.

---

## 5. Fingerprint design exercise

Design two levels of identity.

### Strong identity

These can identify the same source item directly:

- `(provider, provider_event_id)`;
- SEC accession number;
- canonical source URL;
- an explicit vendor story ID.

### Semantic candidate identity

When strong identifiers differ, create a candidate fingerprint from:

```text
primary company identity
+ normalized significant headline tokens
+ UTC calendar-day bucket
+ event type
```

Headline token normalization may:

- lowercase;
- strip punctuation;
- remove publisher suffixes;
- remove a small documented stop-word list;
- normalize common corporate suffixes;
- retain numbers because earnings figures and transaction values matter.

Do not use Python's built-in `hash()`. It is intentionally unstable across processes.

### 5.1 What has already been implemented for you

The following helpers in `normalize.py` are mechanical string and URL cleanup, so they are
provided rather than left as part of the exercise:

```python
_is_timezone_aware(datetime) -> bool
_normalize_text(str) -> str
_normalize_optional_text(str | None) -> str | None
_normalize_symbols(Sequence[str]) -> tuple[str, ...]
_canonicalize_url(str | None) -> str | None
```

Read them once so you know what they guarantee. Do not rewrite them. Your learning task is
to decide when to reject an envelope, how to classify it, what identity evidence enters its
fingerprint, and how to assemble the canonical model.

For the learner-owned normalization logic, add these names to the imports already present:

```python
from datetime import UTC
from hashlib import sha256

from app.domain.enums import EventProvider, EventType, RejectionReason
from app.domain.models import EventSourceRef
```

### 5.2 Exact normalization workflow

`resolve_securities` is supplied by the caller, just like `resolve_security` in Guide 01.
You do not implement or import the test resolver. Call it with normalized symbols and the
provider's CIK:

```python
matches = resolve_securities(symbols=symbols, cik=envelope.cik)
```

It returns zero or more `SecurityMatch` objects. Zero matches is allowed: the event remains
auditable, but `security_ids` is empty.

Write two learner-owned helpers:

```python
def _classify_event(envelope: ProviderEventEnvelope) -> EventType: ...

def _fingerprint(
    envelope: ProviderEventEnvelope,
    *,
    event_type: EventType,
    headline: str,
    symbols: tuple[str, ...],
    canonical_url: str | None,
) -> str: ...
```

For `_classify_event`, use this exact first-version order:

```python
PSEUDOCODE _classify_event(envelope):
    IF envelope.provider IS EventProvider.SEC
       OR envelope.accession_number exists
       OR envelope.form_type exists:
        return EventType.SEC_FILING

    category = lowercase trimmed form of envelope.raw_category, or ""

    category_map = {
        "earnings": EventType.EARNINGS,
        "guidance": EventType.GUIDANCE,
        "merger": EventType.MERGER_ACQUISITION,
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
    }

    IF category is a key in category_map:
        return category_map[category]

    headline = normalized lowercase envelope.headline

    keyword_rules = (
        (("cybersecurity", "data breach", "ransomware"), EventType.CYBERSECURITY),
        (("guidance", "outlook", "forecast"), EventType.GUIDANCE),
        (("merger", "acquisition", "acquire"), EventType.MERGER_ACQUISITION),
        (("chief executive", " ceo ", "resigns", "appointed"), EventType.LEADERSHIP),
        (("dividend",), EventType.DIVIDEND),
        (("buyback", "share repurchase"), EventType.BUYBACK),
        (("lawsuit", "antitrust", "regulator"), EventType.REGULATORY_LEGAL),
        (("analyst", "upgrade", "downgrade"), EventType.ANALYST_ACTION),
        (("insider",), EventType.INSIDER_ACTIVITY),
        (("product launch", "launches", "unveils"), EventType.PRODUCT_OPERATIONAL),
        (("earnings", "quarterly results"), EventType.EARNINGS),
    )

    FOR keywords, event_type IN keyword_rules:
        IF any keyword occurs in headline:
            return event_type

    return EventType.GENERAL_NEWS
```

Keep the keyword table small. The point is deterministic fallback behavior, not building a
complete natural-language classifier.

For `_fingerprint`, use SHA-256 from `hashlib`, never `hash()`. Prefer a strong seed; use the
semantic seed only when no strong identifier exists:

```python
PSEUDOCODE _fingerprint(...):
    IF envelope.accession_number exists:
        seed = "accession|" + normalized accession number
    ELSE IF envelope.provider_event_id exists:
        seed = "provider|" + envelope.provider.value + "|" + provider event ID
    ELSE IF canonical_url exists:
        seed = "url|" + canonical_url
    ELSE:
        company = envelope.cik OR comma-joined symbols OR "unresolved"
        day = envelope.published_at converted to UTC, formatted as YYYY-MM-DD
        seed = "semantic|" + company + "|" + event_type.value + "|" + day
               + "|" + lowercase normalized headline

    return sha256(seed encoded as UTF-8).hexdigest()
```

Then implement `normalize_event` in this order:

```python
PSEUDOCODE normalize_event(envelope, resolve_securities, event_id):
    # Reject before doing any identity work.
    IF NOT _is_timezone_aware(envelope.published_at)
       OR NOT _is_timezone_aware(envelope.received_at):
        return RejectedEvent(
            envelope=envelope,
            reason=RejectionReason.INVALID_TIMESTAMP,
            detail="published_at and received_at must be timezone-aware",
        )

    headline = _normalize_text(envelope.headline)
    IF headline == "":
        return RejectedEvent(
            envelope=envelope,
            reason=RejectionReason.EMPTY_HEADLINE,
            detail="headline is empty after normalization",
        )

    summary = _normalize_optional_text(envelope.summary)
    symbols = _normalize_symbols(envelope.symbols)
    canonical_url = _canonicalize_url(envelope.source_url)
    event_type = _classify_event(envelope)

    matches = resolve_securities(symbols=symbols, cik=envelope.cik)
    security_ids = unique match.security_id values, sorted by str

    source = EventSourceRef(
        provider=envelope.provider,
        source_name=_normalize_text(envelope.source_name),
        source_url=envelope.source_url,
        provider_event_id=envelope.provider_event_id,
    )

    return CanonicalEvent(
        event_id=event_id,
        event_type=event_type,
        headline=headline,
        summary=summary,
        occurred_at=envelope.published_at converted to UTC,
        first_seen_at=envelope.received_at converted to UTC,
        last_seen_at=envelope.received_at converted to UTC,
        primary_source=source,
        sources=(source,),
        security_ids=security_ids,
        symbols=symbols,
        cik=envelope.cik,
        accession_number=envelope.accession_number,
        form_type=envelope.form_type,
        canonical_url=canonical_url,
        fingerprint=_fingerprint(...the normalized values above...),
    )
```

Notice that `source.source_url` retains the provider's original evidence while
`canonical_url` holds the comparison-friendly URL.

---

## 6. File two: `dedupe.py`

### Public contract

```python
def deduplicate_events(
    events: Sequence[CanonicalEvent],
    *,
    policy: DedupePolicy,
) -> DedupeResult:
    """Conservatively cluster duplicate events and merge their source evidence."""
```

Suggested result types:

```python
@dataclass(frozen=True)
class DuplicateCluster:
    canonical: CanonicalEvent
    merged_event_ids: tuple[UUID, ...]
    reasons: tuple[DedupeReason, ...]

@dataclass(frozen=True)
class DedupeResult:
    events: tuple[CanonicalEvent, ...]
    clusters: tuple[DuplicateCluster, ...]
```

### Conservative matching ladder

Evaluate potential duplicates in order:

1. Same SEC accession number → merge.
2. Same provider and provider event ID → merge.
3. Same canonical URL → merge.
4. Same strong fingerprint → merge.
5. Same company + compatible event type + close time window + title similarity above policy threshold → merge candidate.
6. Otherwise keep separate.

Never perform fuzzy matching across unrelated companies merely because headlines are similar.

### Compatibility rules

- `EARNINGS` may be compatible with an `SEC_FILING` only when metadata links the filing to results of operations.
- `GUIDANCE` and `EARNINGS` may be kept as distinct events if one story describes results and another describes a later guidance revision.
- `GENERAL_NEWS` should not absorb a more specific event unless evidence is strong.
- Separate SEC accession numbers are separate filings even when the headlines look identical.

### Canonical-source selection

When merging, retain every `EventSourceRef` and choose a primary source using a documented priority:

```text
SEC filing
> company investor-relations release
> licensed wire / high-confidence provider
> established publication
> aggregator
```

Provider priority must be configuration or policy data, not scattered `if` statements.

### Merge rules

The merged canonical event should:

- keep the earliest `occurred_at` consistent with the event;
- keep the earliest `first_seen_at`;
- keep the latest `last_seen_at`;
- union and deterministically sort sources;
- union security IDs and symbols;
- preserve accession number and CIK when non-conflicting;
- select the most informative non-empty summary according to policy;
- record why records were merged.

If strong fields conflict, keep the events separate and surface a conflict rather than guessing.

### 6.1 What has already been implemented for you

These mechanical helpers are provided in `dedupe.py`:

```python
_event_sort_key(event)                 # stable event ordering
_source_sort_key(source)               # stable source ordering
_provider_rank(provider, policy)       # configured priority with stable fallback
_preferred_event_sort_key(event, policy)
_preferred_source_sort_key(source, policy)
_unique_sorted_sources(events)         # exact source union
_normalized_title(headline)            # comparison-only title form
_title_similarity(left, right)         # deterministic 0..1 ratio
_CandidateGroup                        # mutable events/reasons workspace
```

You still own the important decisions: which evidence proves duplication, when conflicts
block a merge, which event supplies canonical display fields, and how clusters are built.

When implementing that learner-owned logic, add:

```python
from dataclasses import replace

from app.domain.models import DuplicateCluster
```

`DedupeReason` is already imported because `_CandidateGroup` uses it.

### 6.2 Decide whether one pair is duplicative

Implement this helper first:

```python
def _has_strong_conflict(left: CanonicalEvent, right: CanonicalEvent) -> bool: ...

def _duplicate_reason(
    left: CanonicalEvent,
    right: CanonicalEvent,
    policy: DedupePolicy,
) -> DedupeReason | None: ...
```

Use the following exact ladder:

```python
PSEUDOCODE _has_strong_conflict(left, right):
    conflicting_accession = (
        both accession numbers exist AND they differ
    )
    conflicting_cik = both CIKs exist AND they differ
    return conflicting_accession OR conflicting_cik


PSEUDOCODE _duplicate_reason(left, right, policy):
    IF _has_strong_conflict(left, right):
        return None

    IF same non-empty accession number:
        return DedupeReason.ACCESSION_NUMBER

    left_source = left.primary_source
    right_source = right.primary_source

    IF providers match AND same non-empty provider_event_id:
        return DedupeReason.PROVIDER_EVENT_ID

    IF same non-empty canonical_url:
        return DedupeReason.CANONICAL_URL

    IF same non-empty fingerprint:
        return DedupeReason.STRONG_FINGERPRINT

    same_company = intersection of security_ids is not empty
    compatible_type = left.event_type == right.event_type
    close_in_time = absolute occurred_at difference <= policy.fuzzy_window
    similar_title = _title_similarity(left.headline, right.headline)
                    >= policy.title_similarity_threshold

    IF same_company AND compatible_type AND close_in_time AND similar_title:
        return DedupeReason.SEMANTIC_CANDIDATE

    return None
```

For the first implementation, “compatible type” means equal type. Add special compatibility
rules only when a hardening test states exactly which cross-type pair is safe.

### 6.3 Merge one proven group

Implement:

```python
def _merge_group(
    events: Sequence[CanonicalEvent],
    *,
    policy: DedupePolicy,
) -> CanonicalEvent: ...
```

Its input must already be proven duplicative. Do not perform matching inside this helper.
Use these exact field rules:

```python
PSEUDOCODE _merge_group(events, policy):
    ordered = sorted(events, key=_event_sort_key)

    canonical_base = min(
        ordered,
        key=lambda event: _preferred_event_sort_key(event, policy),
    )

    sources = _unique_sorted_sources(ordered)
    primary_source = min(
        sources,
        key=lambda source: _preferred_source_sort_key(source, policy),
    )

    summaries = all non-empty event summaries
    summary = max(summaries, key=lambda value: (len(value), value)) if any, else None

    priority_ordered = sorted(
        events,
        key=lambda event: _preferred_event_sort_key(event, policy),
    )
    non_empty_form_types = form types from priority_ordered
    non_empty_urls = canonical URLs from priority_ordered
    ciks = sorted set of non-empty CIKs
    accessions = sorted set of non-empty accession numbers

    assert len(ciks) <= 1 and len(accessions) <= 1

    return a dataclasses.replace copy of canonical_base with:
        occurred_at = minimum event.occurred_at
        first_seen_at = minimum event.first_seen_at
        last_seen_at = maximum event.last_seen_at
        primary_source = primary_source
        sources = sources
        security_ids = sorted union of all security IDs, using str as key
        symbols = alphabetically sorted union of all symbols
        summary = summary
        cik = ciks[0] if ciks is non-empty, otherwise None
        accession_number = accessions[0] if accessions is non-empty, otherwise None
        form_type = first value in non_empty_form_types, otherwise None
        canonical_url = first value in non_empty_urls, otherwise None
```

`dataclasses.replace` is appropriate because `CanonicalEvent` is frozen. The canonical
event keeps `canonical_base.event_id`; the cluster records the other input IDs for audit.

### 6.4 Build clusters without depending on input order

Use this concrete first-version algorithm:

```python
PSEUDOCODE deduplicate_events(events, policy):
    ordered = sorted(events, key=_event_sort_key)
    groups = empty list of _CandidateGroup objects

    FOR event IN ordered:
        matching_group = None
        matching_reasons = empty set

        FOR group IN groups:
            IF any(_has_strong_conflict(event, member) FOR member IN group.events):
                CONTINUE to the next group

            reasons_against_group = {
                _duplicate_reason(event, member, policy)
                FOR member IN group.events
                where the returned reason is not None
            }

            IF reasons_against_group is not empty:
                matching_group = group
                matching_reasons = reasons_against_group
                BREAK

        IF matching_group IS None:
            groups.append(_CandidateGroup(events=[event]))
        ELSE:
            append event to matching_group.events
            add matching_reasons to matching_group.reasons

    output_events = []
    clusters = []

    FOR group IN groups:
        IF group has exactly one event:
            output_events.append(that event unchanged)
            CONTINUE

        canonical = _merge_group(group.events, policy=policy)
        output_events.append(canonical)
        clusters.append(
            DuplicateCluster(
                canonical=canonical,
                merged_event_ids=all non-canonical event IDs sorted by str,
                reasons=group reasons sorted by reason.value,
            )
        )

    return DedupeResult(
        events=tuple(sorted(output_events, key=_event_sort_key)),
        clusters=tuple(sorted(clusters, key=lambda cluster: _event_sort_key(cluster.canonical))),
    )
```

The “compare against every member” step matters. Comparing only against the first member can
miss a transitive cluster where A matches B and B matches C.

The learner-owned functions in the finished two files are:

```python
# normalize.py
_classify_event
_fingerprint
normalize_event

# dedupe.py
_has_strong_conflict
_duplicate_reason
_merge_group
deduplicate_events
```

Everything else listed as provided helper code is already implemented so you can concentrate
on normalization boundaries and conservative entity resolution.

---

## 7. Why false merges are worse than missed merges

A missed merge may show two related feed cards. A false merge can erase an important second development and prevent an alert entirely.

Therefore:

- thresholds should be conservative;
- every merge should have reason codes;
- strong conflicts block fuzzy merging;
- source evidence is retained rather than overwritten;
- the dedupe system should be replayable when policy changes.

This principle generalizes to customer records, publications, payments, and any other entity-resolution problem.

---

## 8. Hardening tests after the five starter tests pass

### `test_event_normalize.py`

1. SEC envelope becomes `SEC_FILING` with preserved accession number.
2. Structured earnings category beats generic headline keywords.
3. Headline whitespace and HTML entities normalize correctly.
4. Display headline retains readable capitalization.
5. Tracking parameters are removed from the canonical URL.
6. Naive timestamp is rejected.
7. Symbol casing and duplicates normalize.
8. CIK resolver match is preferred over ambiguous ticker match.
9. Empty headline is rejected.
10. Identical input and ID produce identical output and fingerprint.
11. Different provider wrapper around the same canonical headline produces a compatible fingerprint seed.
12. Numbers in material headlines are retained.

### `test_event_dedupe.py`

1. Same accession number merges regardless of headline wording.
2. Same canonical URL merges.
3. Tracking-only URL differences merge after normalization.
4. Same company, nearly identical title, and close timestamps merge under policy.
5. Similar titles for different companies never merge.
6. Separate SEC accession numbers never fuzzy-merge.
7. Earnings and unrelated general news remain separate.
8. Source union is deterministic.
9. Primary source priority selects SEC over aggregator.
10. Earliest first-seen and latest last-seen are preserved.
11. Conflicting CIKs prevent a merge.
12. Input ordering does not alter clusters or canonical output.
13. Re-deduplicating already deduplicated output is idempotent.
14. Every merge cluster includes at least one reason code.

Tests use fixtures only. They do not call OpenBB, SEC, or news providers.

---

## 9. Recommended work order

1. Implement text, time, symbol, and URL normalization.
2. Implement the small event taxonomy.
3. Produce stable fingerprint inputs.
4. Pass strong-identifier dedupe tests.
5. Add conservative fuzzy candidate matching.
6. Implement deterministic merge and source selection.
7. Add conflict handling and idempotency.

Do not begin with fuzzy similarity. Strong identifiers and canonicalization eliminate most duplicates more safely.

---

## 10. Acceptance criteria

- Provider-specific models do not escape the adapter layer.
- Canonical events are timezone-aware and auditable.
- Event classification is deterministic.
- Every source survives a merge.
- Separate companies and conflicting filings do not merge.
- Results do not depend on input order.
- Re-running dedupe does not change the output.
- You can explain the difference between a strong identifier and a semantic candidate fingerprint.

---

## 11. Self-test

1. Why normalize before deduplicating?
2. Why is a hash only as good as its canonical input?
3. Why should numbers remain in normalized headlines?
4. Why do separate SEC accession numbers block fuzzy merging?
5. Why are false-positive merges more dangerous than missed duplicates?
6. What evidence would justify linking an earnings press release with an 8-K?
7. How can a policy threshold change without corrupting original source evidence?
