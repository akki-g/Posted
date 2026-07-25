"""AI-generated narrative insights (Claude) layered on top of Posted's deterministic scoring.

Best-effort only: every function here must degrade to ``None`` rather than raise,
so a missing key or a flaky API call never breaks a sync or a page load.
"""

from dataclasses import dataclass
from decimal import Decimal

import structlog
from anthropic import APIError, AsyncAnthropic

from app.config import Settings

logger = structlog.get_logger()

MODEL = "claude-opus-4-8"


@dataclass(frozen=True, slots=True)
class DebriefEventHighlight:
    headline: str
    level: str
    symbol: str | None


def _client(settings: Settings) -> AsyncAnthropic | None:
    if not settings.anthropic_api_key:
        return None
    return AsyncAnthropic(api_key=settings.anthropic_api_key)


async def generate_event_insight(
    *,
    headline: str,
    summary: str | None,
    level: str,
    score: float,
    affected_holdings: list[tuple[str, float]],
    settings: Settings,
) -> str | None:
    """Return a short, portfolio-specific note on why a story matters and what it means for
    investment decisions, or None. Primitive args so this is callable from any layer (a live
    sync, or an on-demand API request) without reconstructing domain objects."""

    client = _client(settings)
    if client is None:
        return None

    holdings_context = (
        ", ".join(f"{symbol} ({weight:.1f}% of portfolio)" for symbol, weight in affected_holdings)
        or "no currently held security"
    )

    prompt = (
        "You are a portfolio analyst writing a short note for an investor about a news story. "
        "Hard limit: 3 sentences, under 70 words total. Cover two things concisely: (1) why "
        "this story matters given the investor's specific holdings below, grounded in the "
        "numbers given, and (2) what it means for their investment decision-making — e.g. "
        "whether it changes risk concentration, warrants closer monitoring, or is routine "
        "noise. Do not recommend buying, selling, or holding any security, and do not predict "
        "price direction. Do not use hedging filler like 'it is important to note'. Do not "
        "write a title or heading — plain prose only.\n\n"
        f"Headline: {headline}\n"
        f"Summary: {summary or 'none provided'}\n"
        f"Affected holdings: {holdings_context}\n"
        f"Impact level: {level} (score {score:.0f}/100)\n"
    )

    try:
        response = await client.messages.create(
            model=MODEL,
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )
    except APIError as exc:
        logger.warning("ai_event_insight_failed", error=str(exc))
        return None

    text = "".join(
        block.text for block in response.content if getattr(block, "type", None) == "text"
    ).strip()
    return text or None


async def generate_morning_debrief(
    *,
    portfolio_value: Decimal,
    day_change: Decimal,
    day_change_percent: Decimal,
    net_cash_position: Decimal,
    weekly_spending: Decimal,
    top_events: list[DebriefEventHighlight],
    settings: Settings,
) -> str | None:
    """Return a short narrative morning debrief synthesizing portfolio + money + feed, or None."""

    client = _client(settings)
    if client is None:
        return None

    events_context = (
        "\n".join(
            f"- [{item.level}] {item.headline}"
            + (f" ({item.symbol})" if item.symbol else "")
            for item in top_events
        )
        or "No notable events since the last debrief."
    )

    prompt = (
        "Write a short morning debrief (3-5 sentences, plain prose, no headers or bullet "
        "points in your reply) for an investor's personal finance app. Cover: how the "
        "portfolio moved, cash position, and whether any of the events below deserve "
        "attention today. Be direct and factual. Do not give investment advice or predict "
        "future price direction. Do not use greeting filler like 'Good morning'.\n\n"
        f"Portfolio value: ${portfolio_value:,.2f}\n"
        f"Day change: ${day_change:,.2f} ({day_change_percent:+.2f}%)\n"
        f"Net cash position: ${net_cash_position:,.2f}\n"
        f"Spending this week: ${weekly_spending:,.2f}\n"
        f"Recent portfolio events, highest impact first:\n{events_context}\n"
    )

    try:
        response = await client.messages.create(
            model=MODEL,
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}],
        )
    except APIError as exc:
        logger.warning("ai_morning_debrief_failed", error=str(exc))
        return None

    text = "".join(
        block.text for block in response.content if getattr(block, "type", None) == "text"
    ).strip()
    return text or None
