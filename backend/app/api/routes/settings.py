from fastapi import APIRouter

from app.api.schemas import UserPreferences

router = APIRouter(prefix="/settings", tags=["settings"])

# MVP-only process-local preferences. Replace with the user_preferences table when
# authentication and multiple users are introduced.
_preferences = UserPreferences()


@router.get("", response_model=UserPreferences)
async def get_preferences() -> UserPreferences:
    return _preferences


@router.put("", response_model=UserPreferences)
async def update_preferences(preferences: UserPreferences) -> UserPreferences:
    global _preferences
    _preferences = preferences
    return _preferences
