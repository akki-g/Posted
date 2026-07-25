from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_id, get_db
from app.api.schemas import UserPreferences
from app.db.models import UserPreference

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_model=UserPreferences)
async def get_preferences(
    session: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
) -> UserPreferences:
    preference = await _get_or_create(session, user_id)
    return UserPreferences.model_validate(preference)


@router.put("", response_model=UserPreferences)
async def update_preferences(
    preferences: UserPreferences,
    session: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
) -> UserPreferences:
    preference = await _get_or_create(session, user_id)
    preference.immediate_alert_level = preferences.immediate_alert_level
    preference.push_enabled = preferences.push_enabled
    preference.email_digest_enabled = preferences.email_digest_enabled
    preference.daily_briefing_time = preferences.daily_briefing_time
    await session.commit()
    return UserPreferences.model_validate(preference)


async def _get_or_create(session: AsyncSession, user_id: UUID) -> UserPreference:
    preference = await session.scalar(
        select(UserPreference).where(UserPreference.user_id == user_id)
    )
    if preference is None:
        preference = UserPreference(user_id=user_id)
        session.add(preference)
        await session.commit()
    return preference
