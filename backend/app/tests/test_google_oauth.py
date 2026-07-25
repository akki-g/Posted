import httpx

from app.providers.google.oauth import GoogleOAuthClient


def test_authorization_url_includes_client_id_redirect_and_state() -> None:
    client = GoogleOAuthClient(
        client_id="test-client-id",
        client_secret="test-secret",
        redirect_uri="http://127.0.0.1:8000/api/v1/auth/google/callback",
    )
    url = client.authorization_url(state="signed-state-value")

    assert url.startswith("https://accounts.google.com/o/oauth2/v2/auth?")
    assert "client_id=test-client-id" in url
    assert "state=signed-state-value" in url
    assert "scope=openid" in url


async def test_exchange_code_returns_access_token() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/token"
        return httpx.Response(200, json={"access_token": "the-access-token", "expires_in": 3600})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        client = GoogleOAuthClient(
            client_id="id",
            client_secret="secret",
            redirect_uri="http://127.0.0.1:8000/callback",
            http=http,
        )
        token = await client.exchange_code(code="the-code")

    assert token == "the-access-token"


async def test_fetch_userinfo_returns_profile() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer the-access-token"
        return httpx.Response(
            200,
            json={
                "sub": "1234567890",
                "email": "person@example.com",
                "name": "Person Example",
                "picture": "https://example.com/pic.jpg",
                "email_verified": True,
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        client = GoogleOAuthClient(
            client_id="id", client_secret="secret", redirect_uri="http://x", http=http
        )
        info = await client.fetch_userinfo(access_token="the-access-token")

    assert info.email == "person@example.com"
    assert info.name == "Person Example"
