from collections.abc import AsyncIterator

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

from app.config import Settings
from app.main import create_app


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    settings = Settings(
        app_env="test",
        database_url="sqlite+aiosqlite:///:memory:",
        demo_mode=True,
    )
    app = create_app(settings)
    async with (
        LifespanManager(app),
        AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as http,
    ):
        yield http
