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
        app_secret="test-secret",
        schwab_client_id=None,
        schwab_client_secret=None,
        plaid_client_id=None,
        plaid_secret=None,
        plaid_environment="sandbox",
        anthropic_api_key=None,
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
