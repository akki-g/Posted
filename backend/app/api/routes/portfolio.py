from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_app_settings, get_current_user_id, get_db
from app.api.schemas import AccountSummary, DashboardResponse, HoldingSummary
from app.config import Settings
from app.services.dashboard import get_accounts, get_dashboard, get_holdings

router = APIRouter(tags=["portfolio"])


@router.get("/dashboard", response_model=DashboardResponse)
async def dashboard(
    session: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
    settings: Settings = Depends(get_app_settings),
) -> DashboardResponse:
    return await get_dashboard(session, user_id=user_id, demo_mode=settings.demo_mode)


@router.get("/accounts", response_model=list[AccountSummary])
async def accounts(
    session: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
) -> list[AccountSummary]:
    return await get_accounts(session, user_id=user_id)


@router.get("/holdings", response_model=list[HoldingSummary])
async def holdings(
    session: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
) -> list[HoldingSummary]:
    return await get_holdings(session, user_id=user_id)
