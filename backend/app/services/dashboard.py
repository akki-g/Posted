from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.schemas import (
    AccountSummary,
    ChartPoint,
    ConnectionStatus,
    DashboardResponse,
    EventReason,
    EventSecurity,
    EventSummary,
    FeedResponse,
    HoldingSummary,
    MoneyMovement,
    PortfolioSummary,
    SyncAccepted,
)
from app.db.models import (
    BrokerageAccount,
    BrokerageConnection,
    EventSecurityLink,
    MarketEvent,
    PortfolioSnapshot,
    Position,
    Security,
    SyncRun,
)

ZERO = Decimal("0")


async def get_connections(
    session: AsyncSession, *, user_id: UUID, demo_mode: bool
) -> list[ConnectionStatus]:
    result = await session.scalars(
        select(BrokerageConnection)
        .where(BrokerageConnection.user_id == user_id)
        .options(selectinload(BrokerageConnection.accounts))
        .order_by(BrokerageConnection.created_at)
    )
    return [
        ConnectionStatus(
            id=item.id,
            provider=item.provider,
            display_name=item.display_name,
            status=item.status,
            last_synced_at=item.last_synced_at,
            account_count=len(item.accounts),
            demo_mode=demo_mode,
        )
        for item in result.unique().all()
    ]


async def get_accounts(session: AsyncSession, *, user_id: UUID) -> list[AccountSummary]:
    result = await session.scalars(
        select(BrokerageAccount)
        .join(BrokerageConnection)
        .where(BrokerageConnection.user_id == user_id)
        .order_by(BrokerageAccount.balance.desc())
    )
    return [
        AccountSummary(
            id=item.id,
            name=item.display_name,
            account_type=item.account_type,
            balance=item.balance,
            day_change=item.day_change,
            total_gain=item.total_gain,
        )
        for item in result.all()
    ]


async def get_holdings(session: AsyncSession, *, user_id: UUID) -> list[HoldingSummary]:
    result = await session.execute(
        select(Position, Security)
        .join(Security, Position.security_id == Security.id)
        .join(BrokerageAccount, Position.account_id == BrokerageAccount.id)
        .join(BrokerageConnection, BrokerageAccount.connection_id == BrokerageConnection.id)
        .where(BrokerageConnection.user_id == user_id)
    )
    grouped: dict[UUID, list[tuple[Position, Security]]] = defaultdict(list)
    for position, security in result.all():
        grouped[security.id].append((position, security))

    holdings: list[HoldingSummary] = []
    for security_id, rows in grouped.items():
        security = rows[0][1]
        quantity = sum((row[0].quantity for row in rows), ZERO)
        market_value = sum((row[0].market_value for row in rows), ZERO)
        day_change = sum((row[0].day_change for row in rows), ZERO)
        total_gain = sum((row[0].total_gain for row in rows), ZERO)
        weight = sum((row[0].portfolio_weight for row in rows), ZERO)
        cost = market_value - total_gain
        average_price = (cost / quantity) if quantity else None
        last_price = (market_value / quantity) if quantity else None
        previous_value = market_value - day_change
        day_change_percent = (
            (day_change / previous_value * Decimal("100")) if previous_value else ZERO
        )
        total_gain_percent = (total_gain / cost * Decimal("100")) if cost else ZERO
        holdings.append(
            HoldingSummary(
                security_id=security_id,
                symbol=security.symbol,
                name=security.name,
                asset_type=security.asset_type,
                sector=security.sector,
                quantity=quantity,
                average_price=average_price,
                last_price=last_price,
                market_value=market_value,
                day_change=day_change,
                day_change_percent=day_change_percent,
                total_gain=total_gain,
                total_gain_percent=total_gain_percent,
                portfolio_weight=weight,
                account_count=len({row[0].account_id for row in rows}),
            )
        )
    return sorted(holdings, key=lambda item: (-item.market_value, item.symbol))


def _event_schema(event: MarketEvent) -> EventSummary:
    return EventSummary(
        id=event.id,
        event_type=event.event_type,
        headline=event.headline,
        summary=event.summary,
        occurred_at=event.occurred_at,
        source_name=event.source_name,
        source_url=event.source_url,
        score=event.score,
        level=event.level,
        confidence=event.confidence,
        unread=event.unread,
        is_demo=event.is_demo,
        reasons=[EventReason.model_validate(reason) for reason in event.reasons],
        securities=[
            EventSecurity(
                security_id=link.security.id,
                symbol=link.security.symbol,
                name=link.security.name,
                match_confidence=link.match_confidence,
                effective_weight=link.effective_weight,
            )
            for link in event.securities
        ],
    )


async def get_feed(
    session: AsyncSession,
    *,
    user_id: UUID,
    level: str | None = None,
    unread_only: bool = False,
    limit: int = 50,
) -> FeedResponse:
    # The MVP database is user-seeded and events link only to the current user's securities.
    # Keep the ownership check in the route/service boundary and replace this query when
    # multi-user event subscriptions are introduced.
    query = select(MarketEvent)
    if level:
        query = query.where(MarketEvent.level == level)
    if unread_only:
        query = query.where(MarketEvent.unread.is_(True))
    query = (
        query.options(selectinload(MarketEvent.securities).selectinload(EventSecurityLink.security))
        .order_by(MarketEvent.occurred_at.desc())
        .limit(limit)
    )
    result = await session.scalars(query)
    events = result.unique().all()
    items = [_event_schema(event) for event in events]
    return FeedResponse(
        items=items,
        unread_count=sum(1 for item in items if item.unread),
        total=len(items),
    )


async def get_event(session: AsyncSession, *, event_id: UUID) -> EventSummary | None:
    event = await session.scalar(
        select(MarketEvent)
        .where(MarketEvent.id == event_id)
        .options(selectinload(MarketEvent.securities).selectinload(EventSecurityLink.security))
    )
    return _event_schema(event) if event else None


async def mark_event_read(session: AsyncSession, *, event_id: UUID) -> bool:
    event = await session.get(MarketEvent, event_id)
    if not event:
        return False
    event.unread = False
    await session.commit()
    return True


async def get_dashboard(
    session: AsyncSession, *, user_id: UUID, demo_mode: bool
) -> DashboardResponse:
    snapshot = await session.scalar(
        select(PortfolioSnapshot)
        .where(PortfolioSnapshot.user_id == user_id)
        .order_by(PortfolioSnapshot.observed_at.desc())
        .limit(1)
    )
    connection = await session.scalar(
        select(BrokerageConnection)
        .where(BrokerageConnection.user_id == user_id)
        .order_by(BrokerageConnection.created_at)
        .limit(1)
    )
    history_result = await session.scalars(
        select(PortfolioSnapshot)
        .where(PortfolioSnapshot.user_id == user_id)
        .order_by(PortfolioSnapshot.observed_at)
    )
    history = history_result.all()
    accounts = await get_accounts(session, user_id=user_id)
    holdings = await get_holdings(session, user_id=user_id)
    feed = await get_feed(session, user_id=user_id, limit=4)

    if snapshot is None:
        summary = PortfolioSummary(
            total_value=ZERO,
            day_change=MoneyMovement(amount=ZERO, percent=ZERO),
            total_gain=MoneyMovement(amount=ZERO, percent=ZERO),
            last_synced_at=connection.last_synced_at if connection else None,
            connection_status=connection.status if connection else "not_connected",
            demo_mode=demo_mode,
        )
    else:
        summary = PortfolioSummary(
            total_value=snapshot.total_value,
            day_change=MoneyMovement(
                amount=snapshot.day_change,
                percent=snapshot.day_change_percent,
            ),
            total_gain=MoneyMovement(
                amount=snapshot.total_gain,
                percent=snapshot.total_gain_percent,
            ),
            last_synced_at=connection.last_synced_at if connection else None,
            connection_status=connection.status if connection else "not_connected",
            demo_mode=demo_mode,
        )

    return DashboardResponse(
        portfolio=summary,
        history=[
            ChartPoint(timestamp=item.observed_at, value=item.total_value) for item in history
        ],
        accounts=accounts,
        top_holdings=holdings[:6],
        important_events=feed.items,
        unread_event_count=feed.unread_count,
    )


async def run_demo_sync(
    session: AsyncSession,
    *,
    connection_id: UUID,
    idempotency_key: str,
) -> SyncAccepted:
    existing = await session.scalar(
        select(SyncRun).where(
            SyncRun.connection_id == connection_id,
            SyncRun.idempotency_key == idempotency_key,
        )
    )
    if existing:
        return SyncAccepted(
            sync_run_id=existing.id,
            status=existing.status,
            message="This synchronization request was already processed.",
        )
    now = datetime.now(UTC)
    run = SyncRun(
        id=uuid4(),
        connection_id=connection_id,
        status="completed",
        idempotency_key=idempotency_key,
        trigger="manual",
        started_at=now,
        completed_at=now,
        counts={"positions_seen": 6, "events_created": 0, "alerts_created": 0},
        warnings=[],
    )
    connection = await session.get(BrokerageConnection, connection_id)
    if connection:
        connection.last_synced_at = now
    session.add(run)
    await session.commit()
    return SyncAccepted(
        sync_run_id=run.id,
        status=run.status,
        message="Demo portfolio synchronized. Live providers are not configured.",
    )
