from collections.abc import AsyncIterator
from uuid import UUID

from fastapi import Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings


async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.session_factory() as session:
        yield session


def get_app_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_current_user_id(
    request: Request,
    x_posted_user_id: UUID | None = Header(default=None),
) -> UUID:
    settings: Settings = request.app.state.settings
    return x_posted_user_id or settings.dev_user_id
