# Guide 03 — Portfolio Impact Engine

[← Event pipeline](02-EVENT-PIPELINE.md) | [Next: Sync orchestrator →](04-SYNC-ORCHESTRATOR.md)

**You write:** `backend/app/impact/scoring.py`

**What exists when you finish:** every canonical event can be ranked for one portfolio using transparent components for materiality, exposure, confidence, recency, and novelty.

## Before you write code

Do not begin until both event-pipeline files pass. Open `scoring.py`, the `EventAssessmentInput` through `ImpactAssessment` definitions in `domain/models.py`, and `test_impact_scoring.py` side by side.

Run only the five starter scoring tests:

```bash
cd backend
uv run pytest -m user_owned app/tests/user_owned/test_impact_scoring.py -q
```

Start with the bounded/versioned result test:

```bash
uv run pytest -m user_owned \
  app/tests/user_owned/test_impact_scoring.py::test_score_is_bounded_and_versioned -q
```

Before implementing the final weighted score, calculate one assessment by hand in a small table with columns for materiality, exposure, recency, novelty, and confidence. Keep every component on a `0..100` scale, clamp components before combining them, then map the final score to a level. The tests after that first one each constrain one property: exposure must be monotonic, recency must decay, zero exposure cannot alert, and threshold mapping must be exact.

Treat the full test list later in the guide as hardening work after these five are green.

This is Posted's central product logic. News providers can tell us what was published; this module decides why it deserves this investor's attention.

---

## 1. Product question

The module answers:

> Given a trustworthy event and a user's current exposure, how urgently should Posted surface it, and how can the score be explained without inventing financial advice?

It does not answer:

- whether the investor should buy or sell;
- whether a headline is factually true beyond source-confidence policy;
- future price direction;
- personalized suitability or investment advice.

The output is an attention-ranking score, not a trading recommendation.

---

## 2. What you are learning

1. How to turn product judgment into an explicit scoring model.
2. Why feature components should be inspectable rather than hidden in one number.
3. How direct and indirect portfolio exposures alter relevance.
4. How source/entity confidence should limit uncertain matches.
5. How to design a deterministic baseline that can later be evaluated or learned.

---

## 3. Agent-written contracts

The agent should scaffold models equivalent to:

```python
@dataclass(frozen=True)
class PortfolioExposure:
    security_id: UUID
    symbol: str
    direct_weight: Decimal
    indirect_weight: Decimal
    market_value: Decimal
    paths: tuple[ExposurePath, ...]

@dataclass(frozen=True)
class EventAssessmentInput:
    event: CanonicalEvent
    exposures: tuple[PortfolioExposure, ...]
    source_confidence: float
    entity_match_confidence: float
    assessed_at: datetime
    previous_related_event_at: datetime | None

@dataclass(frozen=True)
class ScoreComponents:
    materiality: float
    exposure: float
    recency: float
    novelty: float
    confidence: float

class ImpactLevel(StrEnum):
    URGENT = "urgent"
    IMPORTANT = "important"
    NOTABLE = "notable"
    INFORMATIONAL = "informational"

@dataclass(frozen=True)
class ImpactAssessment:
    score: float
    level: ImpactLevel
    components: ScoreComponents
    affected_security_ids: tuple[UUID, ...]
    effective_portfolio_weight: Decimal
    reasons: tuple[ImpactReason, ...]
    eligible_for_immediate_alert: bool
    policy_version: str
```

The scoring policy should be injected:

```python
@dataclass(frozen=True)
class ImpactPolicy:
    version: str
    base_materiality: Mapping[EventType, float]
    form_materiality: Mapping[str, float]
    urgent_threshold: float
    important_threshold: float
    notable_threshold: float
    max_event_age: timedelta
    novelty_window: timedelta
```

Policy data belongs in configuration or a versioned domain object. Do not hide business thresholds throughout the function.

---

## 4. Your public function

```python
def assess_impact(
    assessment: EventAssessmentInput,
    *,
    policy: ImpactPolicy,
) -> ImpactAssessment:
    """Return a deterministic, explainable attention score for one portfolio."""
```

The function must be pure. It receives the assessment time explicitly and performs no database, provider, LLM, or clock calls.

---

## 5. Scoring model for version 1

Implement the initial model exactly enough that tests can pin its behavior, but keep every component independently visible.

### 5.1 Component ranges

Each component is clamped to `[0, 100]`:

- `materiality` — intrinsic seriousness of the event;
- `exposure` — how much of the portfolio is affected;
- `recency` — how recently it occurred;
- `novelty` — whether it adds a new development rather than repeating an existing story;
- `confidence` — confidence in the source and security match.

### 5.2 Weighted score

Use this first-version structure:

```text
base =
    0.50 * materiality
  + 0.25 * exposure
  + 0.15 * recency
  + 0.10 * novelty

final_score = base * (0.70 + 0.30 * confidence/100)
```

Clamp and round the final score to a documented precision.

Why confidence is a multiplier: an uncertain company match should reduce the whole assessment. Why the floor is `0.70`: low confidence should demote rather than completely erase an intrinsically material event, allowing it to remain visible as informational with an uncertainty reason.

Do not tune these weights casually. Version the policy and change it only with fixture-based evaluation.

---

## 6. Materiality component

The policy provides a baseline by event type. A reasonable fixture policy might rank events approximately like this:

| Event | Baseline range |
|---|---:|
| Bankruptcy, definitive acquisition, severe cybersecurity incident | 90–100 |
| Earnings, guidance change, major regulatory action | 75–90 |
| Leadership change, dividend cut, major buyback | 60–80 |
| Analyst action, insider activity, ordinary product news | 35–60 |
| General news | 15–40 |

SEC forms may modify or override the baseline:

- 10-K / 10-Q: important scheduled disclosure;
- 8-K: materiality depends on item/description when available;
- Form 4: insider activity, usually lower unless a later rule detects unusual size;
- 13D / 13G: meaningful ownership event;
- routine amendments should not automatically inherit maximum materiality.

Your algorithm should prefer structured subtype evidence over headline keywords.

The exact test fixture policy is the source of truth; the table explains intent, not financial advice.

---

## 7. Exposure component

### 7.1 Effective exposure

For each affected security:

```text
effective weight = direct weight + indirect weight
```

Sum affected effective weights, then cap at `1.0`. Avoid double counting the same economic path. The agent-written exposure builder should already provide deduplicated paths, but your function still validates the range.

Example:

```text
NVDA direct holding                 6.0%
NVDA through an ETF position       0.8%
effective NVDA exposure            6.8%
```

ETF look-through can be deferred. The contract supports it now so the score does not need redesign later.

### 7.2 Convert weight to a score

A linear mapping makes tiny holdings almost invisible and giant holdings dominate too abruptly. Use a documented piecewise mapping in v1:

| Effective portfolio weight | Exposure score |
|---:|---:|
| 0% | 0 |
| >0% to 1% | interpolate 20 → 30 |
| 1% to 5% | interpolate 30 → 65 |
| 5% to 10% | interpolate 65 → 90 |
| 10% or more | interpolate/cap 90 → 100 |

Write a small private interpolation helper and test boundary continuity.

Why a nonzero small-position score exists: an event can still matter even when the holding is small. Why it remains low: portfolio attention should reflect economic exposure.

### 7.3 No current exposure

An event for a watchlist security with no holding may still appear in a watchlist feed, but the portfolio impact assessment gets exposure `0`. Alert rules may treat watchlists separately later.

---

## 8. Recency component

Use `occurred_at` relative to the explicit `assessed_at`.

The initial decay should be simple and inspectable:

| Age | Recency score |
|---:|---:|
| Future beyond clock-skew tolerance | invalid input |
| 0–1 hour | 100 → 95 |
| 1–24 hours | 95 → 75 |
| 1–3 days | 75 → 45 |
| 3–7 days | 45 → 15 |
| Beyond policy max age | 0 |

Use linear interpolation within bands. Do not call `datetime.now()`.

Allow a small configured future-time tolerance for provider clock skew, then clamp to zero age. Larger future timestamps should raise or return a typed invalid assessment according to the scaffolded contract.

---

## 9. Novelty component

This is not fuzzy deduplication. Deduplication determines whether records are the same event; novelty determines whether a distinct event is a new development in an ongoing story.

For v1:

- no prior related event → `100`;
- prior related event outside novelty window → `80`;
- recent related event but this event has a distinct strong identifier → `60`;
- recent follow-up/repetition → `25`;

The service layer decides which previous event is related and passes its timestamp. Keep this function focused on scoring the supplied fact.

---

## 10. Confidence component

Combine two `[0, 1]` inputs:

```text
confidence = 100 * geometric_mean(source_confidence, entity_match_confidence)
```

The geometric mean penalizes one weak dimension more than an arithmetic average without reducing everything to the minimum.

Validate ranges. Do not silently accept `1.4` or `-0.2`.

Examples:

- SEC filing + exact CIK match → very high confidence;
- licensed article + exact ticker metadata → high confidence;
- aggregator + headline-only company inference → lower confidence.

---

## 11. Levels and immediate alerts

Map score to levels using policy thresholds:

```text
score >= urgent_threshold       -> URGENT
score >= important_threshold    -> IMPORTANT
score >= notable_threshold      -> NOTABLE
otherwise                       -> INFORMATIONAL
```

Immediate alert eligibility should require more than a score:

```text
level is URGENT or IMPORTANT
AND effective exposure > 0
AND entity-match confidence meets policy minimum
AND event is within the immediate-alert age window
```

This prevents a high-materiality but weakly matched old article from waking the user.

The user's notification preferences are evaluated later by `impact/rules.py`; this file only says whether the assessment is generally eligible.

---

## 12. Explainability requirements

Return structured reasons, not one generated sentence. Examples:

```text
MATERIAL_EVENT: "Guidance events have base materiality 85 under policy v1."
DIRECT_EXPOSURE: "This security represents 6.0% of the portfolio."
INDIRECT_EXPOSURE: "An additional 0.8% is held through 2 ETFs."
AUTHORITATIVE_SOURCE: "The primary source is an SEC filing."
LOW_MATCH_CONFIDENCE: "The company match was inferred with 0.62 confidence."
RECENT_EVENT: "The event was published 18 minutes before assessment."
REPEATED_STORY: "A related event was seen within the novelty window."
```

Reason values come from calculated facts. An LLM may later turn them into prose but must not replace the underlying evidence.

---

## 13. Exact implementation walkthrough

The scoring file already provides two mechanical math helpers:

```python
_clamp(value, minimum=0.0, maximum=100.0)
_interpolate(
    value,
    input_start=...,
    input_end=...,
    output_start=...,
    output_end=...,
)
```

Read them, but do not rewrite them. You own the financial-product decisions: which exposure
counts, how each component is calculated, how components combine, and why an alert is eligible.

Add these imports to the starter file as you need them:

```python
from datetime import timedelta
from decimal import Decimal
from math import sqrt

from app.domain.enums import EventProvider, ImpactLevel, ImpactReasonCode
from app.domain.models import ImpactReason, ScoreComponents
```

### 13.1 Validate the supplied facts

Validation here means ordinary `if` statements. Raise `ValueError` for a programmer/service
contract violation; there is no rejected-assessment model in the current contract.

```python
PSEUDOCODE _validate_inputs(assessment, policy):
    IF source_confidence is outside 0.0 through 1.0:
        raise ValueError

    IF entity_match_confidence is outside 0.0 through 1.0:
        raise ValueError

    IF assessed_at or event.occurred_at has no usable timezone:
        raise ValueError

    IF NOT (
        urgent_threshold >= important_threshold >= notable_threshold
    ):
        raise ValueError

    IF policy.max_event_age <= timedelta(days=3):
        raise ValueError because the final recency band requires a later endpoint

    IF previous_related_event_at exists AND has no usable timezone:
        raise ValueError

    FOR exposure IN assessment.exposures:
        IF direct_weight is outside Decimal("0") through Decimal("1"):
            raise ValueError
        IF indirect_weight is outside Decimal("0") through Decimal("1"):
            raise ValueError

    future_amount = event.occurred_at - assessed_at
    IF future_amount > policy.future_clock_skew:
        raise ValueError
```

The small permitted future skew is handled as age zero during recency calculation.

### 13.2 Materiality

Structured form policy wins when a matching form exists; otherwise use the event-type table:

```python
PSEUDOCODE _materiality_score(event, policy):
    event_baseline = policy.base_materiality[event.event_type]

    IF event.form_type exists AND event.form_type is in policy.form_materiality:
        raw_score = policy.form_materiality[event.form_type]
    ELSE:
        raw_score = event_baseline

    return _clamp(raw_score)
```

Using `[...]` for `base_materiality` intentionally fails if policy forgot an event type. A
silent default would hide an incomplete policy.

### 13.3 Effective exposure and exposure score

Only include exposures whose `security_id` appears in `assessment.event.security_ids`:

```python
PSEUDOCODE _affected_exposures(assessment):
    affected_ids = set(assessment.event.security_ids)
    return tuple(
        exposure
        FOR exposure IN assessment.exposures
        IF exposure.security_id IN affected_ids
    )
```

Then calculate one capped weight:

```python
PSEUDOCODE _effective_weight(exposures):
    total = sum(
        (item.direct_weight + item.indirect_weight FOR item IN exposures),
        Decimal("0"),
    )
    return min(total, Decimal("1"))
```

Use the piecewise table through explicit branches:

```python
PSEUDOCODE _exposure_score(weight: Decimal):
    value = float(weight)

    IF value == 0:
        return 0.0

    IF value <= 0.01:
        return _interpolate(
            value,
            input_start=0.0, input_end=0.01,
            output_start=20.0, output_end=30.0,
        )

    IF value <= 0.05:
        return _interpolate(
            value,
            input_start=0.01, input_end=0.05,
            output_start=30.0, output_end=65.0,
        )

    IF value <= 0.10:
        return _interpolate(
            value,
            input_start=0.05, input_end=0.10,
            output_start=65.0, output_end=90.0,
        )

    return _clamp(
        _interpolate(
            min(value, 1.0),
            input_start=0.10, input_end=1.0,
            output_start=90.0, output_end=100.0,
        )
    )
```

The deliberate jump from exactly zero to a small positive score represents “a tiny real
holding still matters somewhat.”

### 13.4 Recency

Calculate age from the injected assessment time, never the system clock:

```python
PSEUDOCODE _recency_score(occurred_at, assessed_at, policy):
    age = assessed_at - occurred_at

    IF age is negative but within policy.future_clock_skew:
        age = timedelta(0)

    IF age > policy.max_event_age:
        return 0.0

    IF age <= 1 hour:
        return _interpolate(
            age.total_seconds(),
            input_start=0.0,
            input_end=timedelta(hours=1).total_seconds(),
            output_start=100.0,
            output_end=95.0,
        )

    IF age <= 24 hours:
        return _interpolate(
            age.total_seconds(),
            input_start=timedelta(hours=1).total_seconds(),
            input_end=timedelta(hours=24).total_seconds(),
            output_start=95.0,
            output_end=75.0,
        )

    IF age <= 3 days:
        return _interpolate(
            age.total_seconds(),
            input_start=timedelta(days=1).total_seconds(),
            input_end=timedelta(days=3).total_seconds(),
            output_start=75.0,
            output_end=45.0,
        )

    return _interpolate(
        age.total_seconds(),
        input_start=timedelta(days=3).total_seconds(),
        input_end=policy.max_event_age.total_seconds(),
        output_start=45.0,
        output_end=15.0,
    )
```

Call `_interpolate` with `timedelta.total_seconds()` values. This keeps every band calculation
in the same unit.

### 13.5 Novelty and the current contract limitation

The original design mentioned assigning `60` when a recent related event has a distinct strong
identifier. The current `EventAssessmentInput` contains only
`previous_related_event_at: datetime | None`; it does not contain the previous event or its
identifier. Therefore, the code cannot honestly detect that case yet.

Use the behavior the current contract can support:

```python
PSEUDOCODE _novelty_score(assessment, policy):
    previous = assessment.previous_related_event_at

    IF previous IS None:
        return 100.0

    separation = assessment.event.occurred_at - previous

    IF separation <= policy.novelty_window:
        return 25.0

    return 80.0
```

Add the `60` branch only after extending the input model and adding a test containing the
previous strong identifier.

### 13.6 Confidence, final score, and level

```python
PSEUDOCODE _confidence_score(assessment):
    return 100.0 * sqrt(
        assessment.source_confidence
        * assessment.entity_match_confidence
    )


PSEUDOCODE _final_score(components):
    base = (
        0.50 * components.materiality
        + 0.25 * components.exposure
        + 0.15 * components.recency
        + 0.10 * components.novelty
    )

    confidence_multiplier = 0.70 + 0.30 * (components.confidence / 100.0)
    return round(_clamp(base * confidence_multiplier), 2)


PSEUDOCODE _impact_level(score, policy):
    IF score >= policy.urgent_threshold:
        return ImpactLevel.URGENT
    IF score >= policy.important_threshold:
        return ImpactLevel.IMPORTANT
    IF score >= policy.notable_threshold:
        return ImpactLevel.NOTABLE
    return ImpactLevel.INFORMATIONAL
```

### 13.7 Reasons and immediate-alert eligibility

Build reasons from facts you already calculated. Use this first-version helper rather than
inventing message text throughout `assess_impact`:

```python
PSEUDOCODE _impact_reasons(assessment, exposures, components, effective_weight, policy):
    direct_weight = sum(
        (item.direct_weight FOR item IN exposures),
        Decimal("0"),
    )
    indirect_weight = sum(
        (item.indirect_weight FOR item IN exposures),
        Decimal("0"),
    )

    reasons = [
        ImpactReason(
            code=ImpactReasonCode.MATERIAL_EVENT,
            message="Event materiality under policy " + policy.version,
            value=components.materiality,
        )
    ]

    IF direct_weight > Decimal("0"):
        append ImpactReason(
            code=ImpactReasonCode.DIRECT_EXPOSURE,
            message="Portfolio has direct exposure to an affected security",
            value=str(direct_weight),
        )

    IF indirect_weight > Decimal("0"):
        append ImpactReason(
            code=ImpactReasonCode.INDIRECT_EXPOSURE,
            message="Portfolio has indirect exposure to an affected security",
            value=str(indirect_weight),
        )

    IF effective_weight == Decimal("0"):
        append ImpactReason(
            code=ImpactReasonCode.NO_CURRENT_EXPOSURE,
            message="No current portfolio exposure matches this event",
            value="0",
        )

    IF assessment.event.primary_source.provider IS EventProvider.SEC:
        append ImpactReason(
            code=ImpactReasonCode.AUTHORITATIVE_SOURCE,
            message="Primary source is an SEC filing",
            value=assessment.event.primary_source.provider.value,
        )

    IF assessment.entity_match_confidence < policy.minimum_alert_match_confidence:
        append ImpactReason(
            code=ImpactReasonCode.LOW_MATCH_CONFIDENCE,
            message="Entity match confidence is below the alert threshold",
            value=assessment.entity_match_confidence,
        )

    age = max(assessment.assessed_at - assessment.event.occurred_at, timedelta(0))
    IF age <= policy.immediate_alert_max_age:
        append ImpactReason(
            code=ImpactReasonCode.RECENT_EVENT,
            message="Event is inside the immediate-alert age window",
            value=age.total_seconds(),
        )

    previous = assessment.previous_related_event_at
    IF previous exists
       AND assessment.event.occurred_at - previous <= policy.novelty_window:
        append ImpactReason(
            code=ImpactReasonCode.REPEATED_STORY,
            message="A related event occurred inside the novelty window",
            value=components.novelty,
        )

    return tuple(sorted(reasons, key=lambda reason: reason.code.value))
```

Immediate eligibility is a Boolean expression, not another score:

```python
PSEUDOCODE:
    age = max(assessment.assessed_at - assessment.event.occurred_at, timedelta(0))

    eligible = (
        level IN {ImpactLevel.URGENT, ImpactLevel.IMPORTANT}
        AND effective_weight > Decimal("0")
        AND assessment.entity_match_confidence
            >= policy.minimum_alert_match_confidence
        AND age <= policy.immediate_alert_max_age
    )
```

### 13.8 Assemble `assess_impact`

The public function should now be straightforward composition:

```python
PSEUDOCODE assess_impact(assessment, policy):
    _validate_inputs(assessment, policy)

    exposures = _affected_exposures(assessment)
    effective_weight = _effective_weight(exposures)

    components = ScoreComponents(
        materiality=_materiality_score(assessment.event, policy),
        exposure=_exposure_score(effective_weight),
        recency=_recency_score(
            assessment.event.occurred_at,
            assessment.assessed_at,
            policy,
        ),
        novelty=_novelty_score(assessment, policy),
        confidence=_confidence_score(assessment),
    )

    score = _final_score(components)
    level = _impact_level(score, policy)
    reasons = _impact_reasons(
        assessment,
        exposures,
        components,
        effective_weight,
        policy,
    )
    eligible = evaluate the Boolean gates from section 13.7

    return ImpactAssessment(
        score=score,
        level=level,
        components=components,
        affected_security_ids=tuple(
            sorted({item.security_id FOR item IN exposures}, key=str)
        ),
        effective_portfolio_weight=effective_weight,
        reasons=reasons,
        eligible_for_immediate_alert=eligible,
        policy_version=policy.version,
    )
```

The learner-owned functions in the finished file should be:

```python
_validate_inputs
_materiality_score
_affected_exposures
_effective_weight
_exposure_score
_recency_score
_novelty_score
_confidence_score
_final_score
_impact_level
_impact_reasons
assess_impact
```

That looks like several functions, but each names one scoring rule. `_clamp` and
`_interpolate` are already written because their implementation is generic math rather than
product reasoning.

---

## 14. Hardening tests after the five starter tests pass

`test_impact_scoring.py` must cover:

1. component and final scores remain within `[0, 100]`;
2. identical inputs always produce identical output;
3. larger exposure never lowers the score when other inputs remain fixed;
4. older events never gain recency score;
5. exact source and entity confidence combine correctly;
6. one low confidence dimension meaningfully reduces the multiplier;
7. zero exposure produces exposure score zero;
8. direct and indirect exposure combine without exceeding 100%;
9. exposure interpolation is continuous at 1%, 5%, and 10%;
10. future time inside tolerance clamps safely;
11. future time outside tolerance fails explicitly;
12. authoritative high-materiality event with meaningful exposure can be urgent;
13. old weak-match event is not immediately alertable;
14. distinct recent development gets more novelty than a repetition;
15. threshold boundaries map to the correct level;
16. immediate alert requires nonzero exposure;
17. reasons include the dominant component and any low-confidence warning;
18. affected security IDs and reason ordering are deterministic;
19. policy version is preserved in output;
20. input objects are not mutated.

Add property-based tests later if useful, but begin with readable examples.

---

## 15. Recommended implementation order

1. Validate inputs and implement clamping/interpolation helpers.
2. Calculate materiality from policy.
3. Calculate effective exposure and the piecewise exposure score.
4. Implement recency bands.
5. Implement novelty and confidence.
6. Combine components and map level thresholds.
7. Add alert eligibility.
8. Generate structured reasons last.

Keep each component calculation independently testable. The public function should read like an explanation of the formula.

---

## 16. Acceptance criteria

- Scoring is deterministic, pure, and policy-versioned.
- Every component is returned separately.
- Direct and indirect exposures are visible.
- The final score can be recalculated from stored components and policy.
- No LLM chooses alert priority.
- Immediate-alert eligibility includes confidence, age, and exposure gates.
- The result contains facts that a UI can explain without guessing.
- You can defend the formula while acknowledging that its weights need evaluation data.

---

## 17. Self-test

1. Why does confidence multiply the base instead of acting only as another additive component?
2. Why use a confidence floor instead of multiplying directly by zero-to-one confidence?
3. Why is the exposure mapping piecewise rather than linear?
4. What is the difference between deduplication and novelty?
5. Why must the policy be versioned?
6. How would you evaluate and improve the weights once Posted has real usage data?
7. Why should the UI display component reasons rather than only the final score?
