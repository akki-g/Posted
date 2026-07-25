from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_app_settings, get_current_user_id, get_db
from app.api.schemas import EventSummary, FeedResponse, MorningDebriefResponse
from app.config import Settings
from app.services.dashboard import get_event, get_feed, mark_event_read
from app.services.debrief import build_morning_debrief

router = APIRouter(prefix="/feed", tags=["feed"])


@router.get("", response_model=FeedResponse)
async def feed(
    level: Literal["urgent", "important", "notable", "informational"] | None = None,
    unread_only: bool = False,
    limit: int = Query(default=50, ge=1, le=100),
    session: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
    settings: Settings = Depends(get_app_settings),
) -> FeedResponse:
    return await get_feed(
        session,
        user_id=user_id,
        level=level,
        unread_only=unread_only,
        limit=limit,
        include_demo=settings.demo_mode,
    )


@router.get("/debrief", response_model=MorningDebriefResponse)
async def morning_debrief(
    session: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
    settings: Settings = Depends(get_app_settings),
) -> MorningDebriefResponse:
    summary, generated_at = await build_morning_debrief(
        session, user_id=user_id, settings=settings
    )
    return MorningDebriefResponse(
        generated_at=generated_at,
        available=summary is not None,
        summary=summary,
    )


@router.get("/{event_id}", response_model=EventSummary)
async def event_detail(
    event_id: UUID,
    session: AsyncSession = Depends(get_db),
    _user_id: UUID = Depends(get_current_user_id),
    settings: Settings = Depends(get_app_settings),
) -> EventSummary:
    event = await get_event(session, event_id=event_id, settings=settings)
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    return event


@router.post("/{event_id}/read", status_code=status.HTTP_204_NO_CONTENT)
async def read_event(
    event_id: UUID,
    session: AsyncSession = Depends(get_db),
    _user_id: UUID = Depends(get_current_user_id),
) -> None:
    if not await mark_event_read(session, event_id=event_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
