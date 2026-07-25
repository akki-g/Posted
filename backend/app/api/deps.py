from collections.abc import AsyncIterator
from uuid import UUID

from fastapi import Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.security.session_token import verify_session_token


async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.session_factory() as session:
        yield session


def get_app_settings(request: Request) -> Settings:
    return request.app.state.settings


def _resolve_bearer_user_id(authorization: str | None, settings: Settings) -> UUID | None:
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    token = authorization[len("bearer "):]
    return verify_session_token(token, settings.app_secret.get_secret_value())


def get_current_user_id(
    request: Request,
    authorization: str | None = Header(default=None),
    x_posted_user_id: UUID | None = Header(default=None),
) -> UUID:
    """Resolve the request's user.

    In demo mode this falls back to a shared dev user so the app works with
    zero setup. Outside demo mode, only a signed session token is trusted --
    the client-supplied X-Posted-User-Id header is not, since anyone could
    set it to impersonate any account.
    """

    settings: Settings = request.app.state.settings
    bearer_user_id = _resolve_bearer_user_id(authorization, settings)
    if not settings.demo_mode:
        if bearer_user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
            )
        return bearer_user_id
    return bearer_user_id or x_posted_user_id or settings.dev_user_id


def require_current_user_id(
    request: Request,
    authorization: str | None = Header(default=None),
) -> UUID:
    settings: Settings = request.app.state.settings
    user_id = _resolve_bearer_user_id(authorization, settings)
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user_id
