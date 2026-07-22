from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_app_settings, get_current_user_id, get_db
from app.api.schemas import (
    MoneyAccountSummary,
    MoneyConnectionStatus,
    MoneyOverviewResponse,
    MoneyTransactionsResponse,
    RecurringStreamSummary,
)
from app.config import Settings
from app.services.money import (
    get_money_accounts,
    get_money_connections,
    get_money_overview,
    get_money_transactions,
    get_recurring_streams,
)

router = APIRouter(prefix="/money", tags=["money"])


@router.get("/overview", response_model=MoneyOverviewResponse)
async def money_overview(
    session: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
    settings: Settings = Depends(get_app_settings),
) -> MoneyOverviewResponse:
    return await get_money_overview(session, user_id=user_id, demo_mode=settings.demo_mode)


@router.get("/accounts", response_model=list[MoneyAccountSummary])
async def money_accounts(
    session: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
) -> list[MoneyAccountSummary]:
    return await get_money_accounts(session, user_id=user_id)


@router.get("/transactions", response_model=MoneyTransactionsResponse)
async def money_transactions(
    search: str | None = Query(default=None, max_length=100),
    category: str | None = Query(default=None, max_length=100),
    status: str | None = Query(default=None, pattern="^(pending|posted)$"),
    limit: int = Query(default=100, ge=1, le=500),
    session: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
) -> MoneyTransactionsResponse:
    return await get_money_transactions(
        session,
        user_id=user_id,
        search=search,
        category=category,
        status=status,
        limit=limit,
    )


@router.get("/subscriptions", response_model=list[RecurringStreamSummary])
async def subscriptions(
    session: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
) -> list[RecurringStreamSummary]:
    return await get_recurring_streams(session, user_id=user_id)


@router.get("/connections", response_model=list[MoneyConnectionStatus])
async def money_connections(
    session: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
) -> list[MoneyConnectionStatus]:
    return await get_money_connections(session, user_id=user_id)
