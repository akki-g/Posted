"""Human-owned portfolio impact scoring exercise.

Implementation contract: guides/03-IMPACT-ENGINE.md.
The coding agent must not implement or replace this module unless explicitly asked.
"""

from app.domain.models import EventAssessmentInput, ImpactAssessment, ImpactPolicy


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


def assess_impact(
    assessment: EventAssessmentInput,
    *,
    policy: ImpactPolicy,
) -> ImpactAssessment:
    """Return a deterministic, explainable attention score for one portfolio."""
    raise NotImplementedError("Follow guides/03-IMPACT-ENGINE.md")
