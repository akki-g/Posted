from dataclasses import astuple, replace
from datetime import timedelta
from decimal import Decimal

import pytest

from app.domain.enums import EventType, ImpactLevel
from app.domain.models import (
    EventAssessmentInput,
    ImpactPolicy,
    PortfolioExposure,
)
from app.impact.scoring import assess_impact
from app.tests.user_owned.factories import NOW, SECURITIES, canonical_event

pytestmark = pytest.mark.user_owned


POLICY = ImpactPolicy(
    version="v1-test",
    base_materiality={event_type: 40.0 for event_type in EventType}
    | {EventType.GUIDANCE: 90.0, EventType.EARNINGS: 80.0},
    form_materiality={"8-K": 75.0},
)


def assessment(
    *, weight: str = "0.05", age: timedelta = timedelta(minutes=10)
) -> EventAssessmentInput:
    event = replace(canonical_event("impact"), occurred_at=NOW - age)
    exposure = PortfolioExposure(
        security_id=SECURITIES["AAPL"].security_id,
        symbol="AAPL",
        direct_weight=Decimal(weight),
        indirect_weight=Decimal("0"),
        market_value=Decimal("10000"),
    )
    return EventAssessmentInput(
        event=event,
        exposures=(exposure,),
        source_confidence=0.95,
        entity_match_confidence=0.98,
        assessed_at=NOW,
    )


def test_score_is_bounded_and_versioned() -> None:
    result = assess_impact(assessment(), policy=POLICY)
    assert 0 <= result.score <= 100
    assert result.policy_version == "v1-test"
    assert all(0 <= value <= 100 for value in astuple(result.components))


def test_more_exposure_never_lowers_score() -> None:
    small = assess_impact(assessment(weight="0.01"), policy=POLICY)
    large = assess_impact(assessment(weight="0.10"), policy=POLICY)
    assert large.components.exposure > small.components.exposure
    assert large.score >= small.score


def test_older_event_has_lower_recency() -> None:
    recent = assess_impact(assessment(age=timedelta(hours=1)), policy=POLICY)
    old = assess_impact(assessment(age=timedelta(days=5)), policy=POLICY)
    assert old.components.recency < recent.components.recency


def test_zero_exposure_is_not_immediately_alertable() -> None:
    result = assess_impact(assessment(weight="0"), policy=POLICY)
    assert result.components.exposure == 0
    assert result.eligible_for_immediate_alert is False


def test_threshold_boundaries_map_to_level() -> None:
    result = assess_impact(assessment(weight="0.10"), policy=POLICY)
    expected = (
        ImpactLevel.URGENT
        if result.score >= POLICY.urgent_threshold
        else ImpactLevel.IMPORTANT
        if result.score >= POLICY.important_threshold
        else ImpactLevel.NOTABLE
        if result.score >= POLICY.notable_threshold
        else ImpactLevel.INFORMATIONAL
    )
    assert result.level is expected
