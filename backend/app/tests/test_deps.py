from uuid import uuid4

from httpx import AsyncClient

from app.security.session_token import create_session_token


async def test_current_user_falls_back_to_dev_user_without_a_token(client: AsyncClient) -> None:
    response = await client.get("/api/v1/holdings")
    assert response.status_code == 200


async def test_bearer_token_overrides_dev_user(client: AsyncClient) -> None:
    other_user_id = uuid4()
    token = create_session_token(other_user_id, "test-secret")

    response = await client.get(
        "/api/v1/holdings", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    assert response.json() == []  # a brand-new user has no holdings yet


async def test_me_requires_a_valid_bearer_token(client: AsyncClient) -> None:
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401

    response = await client.get(
        "/api/v1/auth/me", headers={"Authorization": "Bearer not-a-real-token"}
    )
    assert response.status_code == 401


async def test_production_mode_requires_a_bearer_token_and_ignores_dev_header() -> None:
    from asgi_lifespan import LifespanManager
    from httpx import ASGITransport

    from app.config import Settings
    from app.main import create_app

    settings = Settings(
        app_env="production",
        database_url="sqlite+aiosqlite:///:memory:",
        demo_mode=False,
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
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http,
    ):
        no_auth = await http.get("/api/v1/holdings")
        assert no_auth.status_code == 401

        spoofed = await http.get(
            "/api/v1/holdings", headers={"X-Posted-User-Id": str(uuid4())}
        )
        assert spoofed.status_code == 401

        token = create_session_token(uuid4(), "test-secret")
        authed = await http.get(
            "/api/v1/holdings", headers={"Authorization": f"Bearer {token}"}
        )
        assert authed.status_code == 200
