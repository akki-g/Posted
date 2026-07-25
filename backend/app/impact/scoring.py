"""Human-owned portfolio impact scoring exercise.

Implementation contract: guides/03-IMPACT-ENGINE.md.
The coding agent must not implement or replace this module unless explicitly asked.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from math import sqrt

from app.domain.enums import EventProvider, ImpactLevel, ImpactReasonCode
from app.domain.models import (
    EventAssessmentInput,
    ImpactAssessment,
    ImpactPolicy,
    ImpactReason,
    PortfolioExposure,
    ScoreComponents,
)


def _clamp(value: float, minimum: float = 0.0, maximum: float = 100.0) -> float:
    """Restrict a numeric score to an inclusive range."""

    if minimum > maximum:
        raise ValueError("minimum cannot be greater than maximum")
    return max(minimum, min(maximum, value))


def _interpolate(
    value: float,
    *,
    input_start: float,
    input_end: float,
    output_start: float,
    output_end: float,
) -> float:
    """Linearly map a value between two input and output boundary pairs."""

    if input_start == input_end:
        raise ValueError("interpolation input boundaries must differ")
    progress = (value - input_start) / (input_end - input_start)
    return output_start + progress * (output_end - output_start)


def _is_aware(value: datetime) -> bool:
    """Return whether a datetime-like value contains a usable UTC offset."""

    return value.tzinfo is not None and value.utcoffset() is not None


def _validate_inputs(assessment: EventAssessmentInput, policy: ImpactPolicy) -> None:
    """Reject invalid facts and policies before they can produce a plausible score."""

    if not 0 <= assessment.source_confidence <= 1:
        raise ValueError("source_confidence must be between zero and one")
    if not 0 <= assessment.entity_match_confidence <= 1:
        raise ValueError("entity_match_confidence must be between zero and one")
    if not _is_aware(assessment.assessed_at) or not _is_aware(assessment.event.occurred_at):
        raise ValueError("assessment and event timestamps must be timezone-aware")
    if not (
        policy.urgent_threshold
        >= policy.important_threshold
        >= policy.notable_threshold
        >= 0
    ):
        raise ValueError("impact thresholds must be descending and non-negative")
    if policy.max_event_age <= timedelta(days=3):
        raise ValueError("max_event_age must be greater than three days")
    if policy.novelty_window < timedelta(0) or policy.immediate_alert_max_age < timedelta(0):
        raise ValueError("impact policy time windows must not be negative")
    if not 0 <= policy.minimum_alert_match_confidence <= 1:
        raise ValueError("minimum alert confidence must be between zero and one")
    if policy.future_clock_skew < timedelta(0):
        raise ValueError("future_clock_skew must not be negative")
    if assessment.previous_related_event_at is not None and not _is_aware(
        assessment.previous_related_event_at
    ):
        raise ValueError("previous related event timestamp must be timezone-aware")
    for exposure in assessment.exposures:
        if not Decimal("0") <= exposure.direct_weight <= Decimal("1"):
            raise ValueError("direct exposure weight must be between zero and one")
        if not Decimal("0") <= exposure.indirect_weight <= Decimal("1"):
            raise ValueError("indirect exposure weight must be between zero and one")
    if assessment.event.occurred_at - assessment.assessed_at > policy.future_clock_skew:
        raise ValueError("event timestamp exceeds the permitted future clock skew")


def _materiality_score(assessment: EventAssessmentInput, policy: ImpactPolicy) -> float:
    """Apply form-specific materiality before the event-type baseline."""

    event = assessment.event
    baseline = policy.base_materiality[event.event_type]
    raw = (
        policy.form_materiality[event.form_type]
        if event.form_type is not None and event.form_type in policy.form_materiality
        else baseline
    )
    return _clamp(raw)


def _affected_exposures(
    assessment: EventAssessmentInput,
) -> tuple[PortfolioExposure, ...]:
    """Keep only portfolio exposures explicitly linked to this canonical event."""

    affected_ids = set(assessment.event.security_ids)
    return tuple(
        sorted(
            (
                exposure
                for exposure in assessment.exposures
                if exposure.security_id in affected_ids
            ),
            key=lambda exposure: str(exposure.security_id),
        )
    )


def _effective_weight(exposures: tuple[PortfolioExposure, ...]) -> Decimal:
    """Combine direct and look-through exposure without exceeding the whole portfolio."""

    total = sum(
        (item.direct_weight + item.indirect_weight for item in exposures),
        Decimal("0"),
    )
    return min(total, Decimal("1"))


def _exposure_score(weight: Decimal) -> float:
    """Convert portfolio weight into the documented piecewise attention score."""

    value = float(weight)
    if value == 0:
        return 0.0
    if value <= 0.01:
        return _interpolate(
            value,
            input_start=0.0,
            input_end=0.01,
            output_start=20.0,
            output_end=30.0,
        )
    if value <= 0.05:
        return _interpolate(
            value,
            input_start=0.01,
            input_end=0.05,
            output_start=30.0,
            output_end=65.0,
        )
    if value <= 0.10:
        return _interpolate(
            value,
            input_start=0.05,
            input_end=0.10,
            output_start=65.0,
            output_end=90.0,
        )
    return _clamp(
        _interpolate(
            min(value, 1.0),
            input_start=0.10,
            input_end=1.0,
            output_start=90.0,
            output_end=100.0,
        )
    )


def _recency_score(assessment: EventAssessmentInput, policy: ImpactPolicy) -> float:
    """Score freshness using stable elapsed-time bands and the injected clock."""

    age = assessment.assessed_at - assessment.event.occurred_at
    if age < timedelta(0):
        age = timedelta(0)
    if age > policy.max_event_age:
        return 0.0
    seconds = age.total_seconds()
    hour = timedelta(hours=1).total_seconds()
    day = timedelta(days=1).total_seconds()
    three_days = timedelta(days=3).total_seconds()
    if seconds <= hour:
        return _interpolate(
            seconds,
            input_start=0.0,
            input_end=hour,
            output_start=100.0,
            output_end=95.0,
        )
    if seconds <= day:
        return _interpolate(
            seconds,
            input_start=hour,
            input_end=day,
            output_start=95.0,
            output_end=75.0,
        )
    if seconds <= three_days:
        return _interpolate(
            seconds,
            input_start=day,
            input_end=three_days,
            output_start=75.0,
            output_end=45.0,
        )
    return _clamp(
        _interpolate(
            seconds,
            input_start=three_days,
            input_end=policy.max_event_age.total_seconds(),
            output_start=45.0,
            output_end=15.0,
        )
    )


def _novelty_score(assessment: EventAssessmentInput, policy: ImpactPolicy) -> float:
    """Discount a related story only when it falls inside the configured window."""

    previous = assessment.previous_related_event_at
    if previous is None:
        return 100.0
    separation = assessment.event.occurred_at - previous
    return 25.0 if separation <= policy.novelty_window else 80.0


def _confidence_score(assessment: EventAssessmentInput) -> float:
    """Blend source and entity confidence without allowing one to hide the other."""

    return _clamp(
        100.0
        * sqrt(assessment.source_confidence * assessment.entity_match_confidence)
    )


def _final_score(components: ScoreComponents) -> float:
    """Combine components and apply confidence as a bounded multiplier."""

    base = (
        0.50 * components.materiality
        + 0.25 * components.exposure
        + 0.15 * components.recency
        + 0.10 * components.novelty
    )
    confidence_multiplier = 0.70 + 0.30 * (components.confidence / 100.0)
    return round(_clamp(base * confidence_multiplier), 2)


def _impact_level(score: float, policy: ImpactPolicy) -> ImpactLevel:
    """Map a final score to the policy's inclusive severity boundaries."""

    if score >= policy.urgent_threshold:
        return ImpactLevel.URGENT
    if score >= policy.important_threshold:
        return ImpactLevel.IMPORTANT
    if score >= policy.notable_threshold:
        return ImpactLevel.NOTABLE
    return ImpactLevel.INFORMATIONAL


def _impact_reasons(
    assessment: EventAssessmentInput,
    exposures: tuple[PortfolioExposure, ...],
    components: ScoreComponents,
    effective_weight: Decimal,
    policy: ImpactPolicy,
) -> tuple[ImpactReason, ...]:
    """Build deterministic explanations from the same facts used by the score."""

    direct_weight = sum((item.direct_weight for item in exposures), Decimal("0"))
    indirect_weight = sum((item.indirect_weight for item in exposures), Decimal("0"))
    reasons = [
        ImpactReason(
            code=ImpactReasonCode.MATERIAL_EVENT,
            message=f"Event materiality under policy {policy.version}",
            value=components.materiality,
        )
    ]
    if direct_weight > 0:
        reasons.append(
            ImpactReason(
                code=ImpactReasonCode.DIRECT_EXPOSURE,
                message="Portfolio has direct exposure to an affected security",
                value=str(direct_weight),
            )
        )
    if indirect_weight > 0:
        reasons.append(
            ImpactReason(
                code=ImpactReasonCode.INDIRECT_EXPOSURE,
                message="Portfolio has indirect exposure to an affected security",
                value=str(indirect_weight),
            )
        )
    if effective_weight == 0:
        reasons.append(
            ImpactReason(
                code=ImpactReasonCode.NO_CURRENT_EXPOSURE,
                message="No current portfolio exposure matches this event",
                value="0",
            )
        )
    if assessment.event.primary_source.provider is EventProvider.SEC:
        reasons.append(
            ImpactReason(
                code=ImpactReasonCode.AUTHORITATIVE_SOURCE,
                message="Primary source is an SEC filing",
                value=EventProvider.SEC.value,
            )
        )
    if assessment.entity_match_confidence < policy.minimum_alert_match_confidence:
        reasons.append(
            ImpactReason(
                code=ImpactReasonCode.LOW_MATCH_CONFIDENCE,
                message="Entity match confidence is below the alert threshold",
                value=assessment.entity_match_confidence,
            )
        )
    age = max(
        assessment.assessed_at - assessment.event.occurred_at,
        timedelta(0),
    )
    if age <= policy.immediate_alert_max_age:
        reasons.append(
            ImpactReason(
                code=ImpactReasonCode.RECENT_EVENT,
                message="Event is inside the immediate-alert age window",
                value=age.total_seconds(),
            )
        )
    if (
        assessment.previous_related_event_at is not None
        and assessment.event.occurred_at - assessment.previous_related_event_at
        <= policy.novelty_window
    ):
        reasons.append(
            ImpactReason(
                code=ImpactReasonCode.REPEATED_STORY,
                message="A related event occurred inside the novelty window",
                value=components.novelty,
            )
        )
    return tuple(sorted(reasons, key=lambda reason: reason.code.value))


def assess_impact(
    assessment: EventAssessmentInput,
    *,
    policy: ImpactPolicy,
) -> ImpactAssessment:
    """Return a deterministic, explainable attention score for one portfolio."""

    _validate_inputs(assessment, policy)
    exposures = _affected_exposures(assessment)
    effective_weight = _effective_weight(exposures)
    components = ScoreComponents(
        materiality=_materiality_score(assessment, policy),
        exposure=_exposure_score(effective_weight),
        recency=_recency_score(assessment, policy),
        novelty=_novelty_score(assessment, policy),
        confidence=_confidence_score(assessment),
    )
    score = _final_score(components)
    level = _impact_level(score, policy)
    age = max(
        assessment.assessed_at - assessment.event.occurred_at,
        timedelta(0),
    )
    eligible = (
        level in {ImpactLevel.URGENT, ImpactLevel.IMPORTANT}
        and effective_weight > 0
        and assessment.entity_match_confidence
        >= policy.minimum_alert_match_confidence
        and age <= policy.immediate_alert_max_age
    )
    return ImpactAssessment(
        score=score,
        level=level,
        components=components,
        affected_security_ids=tuple(
            sorted({item.security_id for item in exposures}, key=str)
        ),
        effective_portfolio_weight=effective_weight,
        reasons=_impact_reasons(
            assessment,
            exposures,
            components,
            effective_weight,
            policy,
        ),
        eligible_for_immediate_alert=eligible,
        policy_version=policy.version,
    )
