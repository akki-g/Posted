from fastapi import APIRouter, Depends

from app.api.deps import get_app_settings
from app.api.schemas import HealthResponse
from app.config import Settings

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse)
async def health(settings: Settings = Depends(get_app_settings)) -> HealthResponse:
    return HealthResponse(
        status="ok",
        app=settings.app_name,
        environment=settings.app_env,
        demo_mode=settings.demo_mode,
    )
