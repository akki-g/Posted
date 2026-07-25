"""Fetch real portfolio news, score it, and persist it into the impact feed.

Agent-owned adapter/orchestration code (not a learning file): it wires together
the already-implemented, protected pipeline (events/normalize.py, events/dedupe.py,
impact/scoring.py) around a live OpenBB news fetch, using the same SQLAlchemy-direct
style as services/schwab_sync.py rather than the unused ports/UoW orchestrator.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import Settings
from app.db.models import (
    BrokerageAccount,
    BrokerageConnection,
    EventSecurityLink,
    MarketEvent,
    Position,
    Security,
)
from app.domain.enums import EventType
from app.domain.errors import ProviderNotConfiguredError
from app.domain.models import (
    CanonicalEvent,
    DedupePolicy,
    EventAssessmentInput,
    ImpactPolicy,
    PortfolioExposure,
    RejectedEvent,
    SecurityMatch,
)
from app.events.dedupe import deduplicate_events
from app.events.normalize import normalize_event
from app.impact.scoring import assess_impact
from app.providers.openbb.news import OpenBBNewsAdapter
from app.services.ai_insights import generate_event_insight

logger = structlog.get_logger()

# Materiality baselines for a personal single-portfolio feed. Distinct from any
# "learning file" policy — this module is allowed to own its own scoring inputs,
# it just may never edit app/impact/scoring.py itself.
IMPACT_POLICY = ImpactPolicy(
    version="posted-news-v1",
    base_materiality={
        EventType.SEC_FILING: 55.0,
        EventType.EARNINGS: 80.0,
        EventType.GUIDANCE: 90.0,
        EventType.MERGER_ACQUISITION: 95.0,
        EventType.LEADERSHIP: 60.0,
        EventType.DIVIDEND: 30.0,
        EventType.BUYBACK: 45.0,
        EventType.REGULATORY_LEGAL: 65.0,
        EventType.CYBERSECURITY: 85.0,
        EventType.PRODUCT_OPERATIONAL: 50.0,
        EventType.ANALYST_ACTION: 40.0,
        EventType.INSIDER_ACTIVITY: 45.0,
        EventType.GENERAL_NEWS: 25.0,
    },
    form_materiality={"8-K": 75.0, "10-Q": 60.0, "10-K": 65.0},
)
DEDUPE_POLICY = DedupePolicy()

# AI insight generation is a per-call cost; only spend it on events worth surfacing.
_AI_INSIGHT_LEVELS = {"urgent", "important"}


def _aware_utc(value: datetime) -> datetime:
    # SQLite (including via aiosqlite) returns naive datetimes even from
    # DateTime(timezone=True) columns; impact/scoring.py requires tz-aware input.
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


@dataclass(frozen=True, slots=True)
class NewsSyncSummary:
    held_symbols: int
    fetched: int
    normalized: int
    rejected: int
    duplicates_skipped: int
    inserted: int
    warnings: list[str] = field(default_factory=list)


async def _load_holdings(
    session: AsyncSession, *, user_id: UUID
) -> tuple[dict[str, Security], dict[UUID, Decimal], dict[UUID, Decimal]]:
    accounts_result = await session.scalars(
        select(BrokerageAccount)
        .join(BrokerageConnection)
        .where(BrokerageConnection.user_id == user_id)
        .options(selectinload(BrokerageAccount.positions).selectinload(Position.security))
    )
    security_by_symbol: dict[str, Security] = {}
    weight_by_security: dict[UUID, Decimal] = {}
    market_value_by_security: dict[UUID, Decimal] = {}
    for account in accounts_result.unique().all():
        for position in account.positions:
            security = position.security
            security_by_symbol[security.symbol.upper()] = security
            weight_by_security[security.id] = (
                weight_by_security.get(security.id, Decimal("0")) + position.portfolio_weight
            )
            market_value_by_security[security.id] = (
                market_value_by_security.get(security.id, Decimal("0")) + position.market_value
            )
    return security_by_symbol, weight_by_security, market_value_by_security


async def sync_portfolio_news(
    session: AsyncSession,
    *,
    user_id: UUID,
    settings: Settings,
    as_of: datetime | None = None,
) -> NewsSyncSummary:
    """Fetch, score, and persist real news for the user's currently held securities."""

    as_of = as_of or datetime.now(UTC)
    security_by_symbol, weight_by_security, market_value_by_security = await _load_holdings(
        session, user_id=user_id
    )
    if not security_by_symbol:
        return NewsSyncSummary(
            held_symbols=0, fetched=0, normalized=0, rejected=0, duplicates_skipped=0, inserted=0
        )

    securities_by_id = {security.id: security for security in security_by_symbol.values()}
    exposures = tuple(
        PortfolioExposure(
            security_id=security_id,
            symbol=securities_by_id[security_id].symbol,
            direct_weight=weight_pct / Decimal("100"),
            indirect_weight=Decimal("0"),
            market_value=market_value_by_security[security_id],
        )
        for security_id, weight_pct in weight_by_security.items()
    )

    adapter = OpenBBNewsAdapter(provider=settings.openbb_news_provider)
    try:
        envelopes = await adapter.fetch_company_news(
            symbols=[security.symbol for security in security_by_symbol.values()],
            limit=30,
        )
    except ProviderNotConfiguredError as exc:
        logger.warning("news_provider_not_configured", error=str(exc))
        return NewsSyncSummary(
            held_symbols=len(security_by_symbol),
            fetched=0,
            normalized=0,
            rejected=0,
            duplicates_skipped=0,
            inserted=0,
            warnings=[str(exc)],
        )
    except Exception as exc:  # noqa: BLE001 - a news outage must never fail the sync
        logger.warning("news_fetch_failed", error=str(exc))
        return NewsSyncSummary(
            held_symbols=len(security_by_symbol),
            fetched=0,
            normalized=0,
            rejected=0,
            duplicates_skipped=0,
            inserted=0,
            warnings=[f"news fetch failed: {exc}"],
        )

    def resolve_securities(
        *, symbols: Sequence[str], cik: str | None
    ) -> tuple[SecurityMatch, ...]:
        matches = []
        for symbol in symbols:
            security = security_by_symbol.get(symbol.upper())
            if security is not None:
                matches.append(
                    SecurityMatch(
                        security_id=security.id, canonical_symbol=security.symbol, confidence=1.0
                    )
                )
        return tuple(matches)

    normalized: list[CanonicalEvent] = []
    rejected_count = 0
    for envelope in envelopes:
        result = normalize_event(envelope, resolve_securities=resolve_securities, event_id=uuid4())
        if isinstance(result, RejectedEvent):
            rejected_count += 1
            continue
        if not result.security_ids:
            # Not about any security we currently hold - not feed-worthy for this portfolio.
            continue
        normalized.append(result)

    dedupe_result = (
        deduplicate_events(tuple(normalized), policy=DEDUPE_POLICY)
        if normalized
        else deduplicate_events((), policy=DEDUPE_POLICY)
    )

    inserted = 0
    duplicates_skipped = 0
    for event in dedupe_result.events:
        existing_id = await session.scalar(
            select(MarketEvent.id).where(MarketEvent.fingerprint == event.fingerprint)
        )
        if existing_id is not None:
            duplicates_skipped += 1
            continue

        previous_related_at = await session.scalar(
            select(func.max(MarketEvent.occurred_at))
            .join(EventSecurityLink, EventSecurityLink.event_id == MarketEvent.id)
            .where(EventSecurityLink.security_id.in_(event.security_ids))
        )
        if previous_related_at is not None:
            previous_related_at = _aware_utc(previous_related_at)
        source_confidence = max((source.confidence for source in event.sources), default=1.0)
        impact = assess_impact(
            EventAssessmentInput(
                event=event,
                exposures=exposures,
                source_confidence=source_confidence,
                entity_match_confidence=1.0,
                assessed_at=as_of,
                previous_related_event_at=previous_related_at,
            ),
            policy=IMPACT_POLICY,
        )

        ai_insight: str | None = None
        if impact.level.value in _AI_INSIGHT_LEVELS:
            affected_holdings = [
                (
                    securities_by_id[security_id].symbol,
                    float(weight_by_security.get(security_id, Decimal("0"))),
                )
                for security_id in event.security_ids
                if security_id in securities_by_id
            ]
            ai_insight = await generate_event_insight(
                headline=event.headline,
                summary=event.summary,
                level=impact.level.value,
                score=impact.score,
                affected_holdings=affected_holdings,
                settings=settings,
            )

        market_event = MarketEvent(
            id=event.event_id,
            event_type=event.event_type.value,
            headline=event.headline,
            summary=event.summary,
            occurred_at=event.occurred_at,
            source_name=event.primary_source.source_name,
            source_url=event.canonical_url or event.primary_source.source_url,
            fingerprint=event.fingerprint,
            score=Decimal(str(impact.score)),
            level=impact.level.value,
            confidence=Decimal("1.0"),
            unread=True,
            is_demo=False,
            reasons=[
                {"code": reason.code.value, "message": reason.message}
                for reason in impact.reasons
            ],
            ai_insight=ai_insight,
        )
        session.add(market_event)
        await session.flush()

        for security_id in event.security_ids:
            session.add(
                EventSecurityLink(
                    event_id=market_event.id,
                    security_id=security_id,
                    match_confidence=Decimal("1.0"),
                    effective_weight=weight_by_security.get(security_id, Decimal("0")),
                )
            )
        inserted += 1

    await session.commit()

    return NewsSyncSummary(
        held_symbols=len(security_by_symbol),
        fetched=len(envelopes),
        normalized=len(normalized),
        rejected=rejected_count,
        duplicates_skipped=duplicates_skipped,
        inserted=inserted,
    )
