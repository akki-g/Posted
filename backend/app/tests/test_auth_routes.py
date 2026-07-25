from urllib.parse import parse_qs, urlsplit

from httpx import AsyncClient


async def test_authorize_requires_google_credentials(client: AsyncClient) -> None:
    response = await client.get("/api/v1/auth/google/authorize")
    assert response.status_code == 503


async def test_callback_rejects_invalid_state(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/auth/google/callback",
        params={"code": "irrelevant", "state": "not-a-valid-state"},
        follow_redirects=False,
    )
    assert response.status_code == 400


async def test_callback_creates_a_new_user_and_redirects_with_a_session_token(
    client: AsyncClient, monkeypatch
) -> None:
    from app.api.routes import auth as auth_routes
    from app.providers.google.oauth import GoogleUserInfo

    class FakeGoogleClient:
        def authorization_url(self, *, state: str) -> str:
            return f"https://accounts.google.com/o/oauth2/v2/auth?state={state}"

        async def exchange_code(self, *, code: str) -> str:
            return "fake-access-token"

        async def fetch_userinfo(self, *, access_token: str) -> GoogleUserInfo:
            return GoogleUserInfo(
                sub="999",
                email="newperson@example.com",
                name="New Person",
                email_verified=True,
            )

    monkeypatch.setattr(auth_routes, "_google_client", lambda settings: FakeGoogleClient())

    authorize = await client.get("/api/v1/auth/google/authorize")
    state = parse_qs(urlsplit(authorize.json()["authorization_url"]).query)["state"][0]

    callback = await client.get(
        "/api/v1/auth/google/callback",
        params={"code": "test-code", "state": state},
        follow_redirects=False,
    )

    assert callback.status_code in (302, 307)
    location = urlsplit(callback.headers["location"])
    assert location.path == "/login/callback"
    session_token = parse_qs(location.query)["session"][0]

    me = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {session_token}"}
    )
    assert me.status_code == 200
    assert me.json()["email"] == "newperson@example.com"
    assert me.json()["display_name"] == "New Person"
