from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_app_settings, get_current_user_id, get_db
from app.config import Settings
from app.market.schemas import (
    InsiderAnalysisResponse,
    MarketSearchResult,
    PortfolioInsiderWatchResponse,
    StockDetailResponse,
    StockHistoryResponse,
)
from app.services.insider_analysis import (
    get_insider_analysis,
    get_portfolio_insider_watch,
)
from app.services.market_data import (
    StockNotFoundError,
    get_stock_detail,
    get_stock_history,
    search_market,
)

router = APIRouter(prefix="/market", tags=["market"])


@router.get("/search", response_model=list[MarketSearchResult])
async def market_search(
    q: str = Query(min_length=1, max_length=80),
    session: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
    settings: Settings = Depends(get_app_settings),
) -> list[MarketSearchResult]:
    return await search_market(session, user_id=user_id, query=q, settings=settings)


@router.get("/insiders/portfolio", response_model=PortfolioInsiderWatchResponse)
async def portfolio_insider_watch(
    limit: int = Query(default=25, ge=1, le=25),
    session: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
    settings: Settings = Depends(get_app_settings),
) -> PortfolioInsiderWatchResponse:
    return await get_portfolio_insider_watch(
        session,
        user_id=user_id,
        settings=settings,
        limit=limit,
    )


@router.get("/stocks/{symbol}", response_model=StockDetailResponse)
async def stock_detail(
    symbol: str,
    session: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
    settings: Settings = Depends(get_app_settings),
) -> StockDetailResponse:
    try:
        return await get_stock_detail(
            session,
            user_id=user_id,
            symbol=symbol,
            settings=settings,
        )
    except ValueError as exc:
        status = 404 if isinstance(exc, StockNotFoundError) else 422
        raise HTTPException(status_code=status, detail=str(exc)) from exc


@router.get("/stocks/{symbol}/insiders", response_model=InsiderAnalysisResponse)
async def stock_insider_analysis(
    symbol: str,
    ai: bool = True,
    session: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
    settings: Settings = Depends(get_app_settings),
) -> InsiderAnalysisResponse:
    try:
        return await get_insider_analysis(
            session,
            user_id=user_id,
            symbol=symbol,
            settings=settings,
            generate_ai=ai,
        )
    except ValueError as exc:
        status = 404 if isinstance(exc, StockNotFoundError) else 422
        raise HTTPException(status_code=status, detail=str(exc)) from exc


@router.get("/stocks/{symbol}/history", response_model=StockHistoryResponse)
async def stock_history(
    symbol: str,
    period: Literal["1D", "5D", "1M", "6M", "1Y", "5Y"] = "1D",
    settings: Settings = Depends(get_app_settings),
) -> StockHistoryResponse:
    try:
        return await get_stock_history(symbol=symbol, period=period, settings=settings)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
