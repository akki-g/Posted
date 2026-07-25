"""Morning debrief: an AI-synthesized daily narrative over the dashboard, money, and feed."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.services.ai_insights import DebriefEventHighlight, generate_morning_debrief
from app.services.dashboard import get_dashboard, get_feed
from app.services.money import get_money_overview

TOP_EVENTS_LIMIT = 5


async def build_morning_debrief(
    session: AsyncSession, *, user_id: UUID, settings: Settings
) -> tuple[str | None, datetime]:
    """Return (debrief text or None, generated_at). None means AI insights aren't configured."""

    generated_at = datetime.now(UTC)
    if not settings.ai_insights_configured:
        return None, generated_at

    dashboard = await get_dashboard(session, user_id=user_id, demo_mode=settings.demo_mode)
    overview = await get_money_overview(
        session, user_id=user_id, demo_mode=settings.demo_mode, now=generated_at
    )
    feed = await get_feed(
        session,
        user_id=user_id,
        limit=TOP_EVENTS_LIMIT,
        include_demo=settings.demo_mode,
    )

    highlights = [
        DebriefEventHighlight(
            headline=item.headline,
            level=item.level,
            symbol=item.securities[0].symbol if item.securities else None,
        )
        for item in feed.items
    ]

    text = await generate_morning_debrief(
        portfolio_value=dashboard.portfolio.total_value,
        day_change=dashboard.portfolio.day_change.amount,
        day_change_percent=dashboard.portfolio.day_change.percent,
        net_cash_position=overview.net_cash_position,
        weekly_spending=overview.weekly_spending,
        top_events=highlights,
        settings=settings,
    )
    return text, generated_at
