from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_app_settings, get_current_user_id, get_db
from app.api.schemas import (
    AssistantChatRequest,
    AssistantConversationResponse,
    AssistantMessageSummary,
)
from app.config import Settings
from app.services.assistant import clear_conversation, get_conversation, send_message

router = APIRouter(prefix="/assistant", tags=["assistant"])


@router.get("/messages", response_model=AssistantConversationResponse)
async def conversation(
    session: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
) -> AssistantConversationResponse:
    rows = await get_conversation(session, user_id=user_id)
    return AssistantConversationResponse(
        messages=[AssistantMessageSummary.model_validate(row) for row in rows]
    )


@router.post("/messages", response_model=AssistantMessageSummary)
async def send(
    request: AssistantChatRequest,
    session: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
    settings: Settings = Depends(get_app_settings),
) -> AssistantMessageSummary:
    row = await send_message(
        session,
        user_id=user_id,
        settings=settings,
        message=request.message,
        section=request.section,
    )
    return AssistantMessageSummary.model_validate(row)


@router.delete("/messages", status_code=status.HTTP_204_NO_CONTENT)
async def reset(
    session: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
) -> None:
    await clear_conversation(session, user_id=user_id)
