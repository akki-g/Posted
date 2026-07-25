# Google Login + User Menu Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an optional Google OAuth login flow (web only) and move Settings into a dropdown user menu on the topbar avatar.

**Architecture:** Backend mirrors the existing Schwab OAuth pattern (`connections.py` / `providers/schwab/oauth.py`) — an `/authorize` endpoint builds a signed-state Google auth URL, a `/callback` endpoint exchanges the code server-side, upserts a `User` row, and issues a signed session token, redirecting the browser to a frontend callback page with the token in the query string. `get_current_user_id` (used by every existing route) is extended to prefer a valid `Authorization: Bearer` session token over its current `X-Posted-User-Id` / `dev_user_id` fallback, which is what makes login optional — nothing breaks if no one has signed in. Frontend adds a login page, a callback page, a small `AuthContext`, and turns the static avatar in `AppShell.tsx` into a dropdown with Settings/Sign in/Sign out.

**Tech Stack:** FastAPI + SQLAlchemy async (backend), Expo Router + React Query + React Native (frontend). No new dependencies on either side — the Google token exchange uses plain `httpx` (already a dependency), and session tokens are a small HMAC scheme matching the existing Schwab OAuth `state` implementation.

## Global Constraints

- Web only — no `expo-auth-session` / native OAuth flow this pass. Native keeps using the dev user.
- Auth is optional — every existing route must keep working unauthenticated exactly as it does today (dev user fallback).
- No new pip or npm dependencies.
- Follow existing patterns: `providers/schwab/oauth.py` for the OAuth client shape, `connections.py` for the authorize/callback route shape, `conftest.py`'s `client` fixture for backend tests, `httpx.MockTransport` (see `test_sec_adapter.py`) for mocking external HTTP calls in tests.
- Spec: `docs/superpowers/specs/2026-07-24-google-login-user-menu-design.md`

---

### Task 1: Backend config for Google OAuth

**Files:**
- Modify: `backend/app/config.py`
- Modify: `.env.example`
- Test: `backend/app/tests/test_api.py` (add one assertion, no new file)

**Interfaces:**
- Produces: `Settings.google_client_id: str | None`, `Settings.google_client_secret: str | None`, `Settings.google_redirect_uri: str`, `Settings.frontend_login_callback_url: str`, `Settings.google_configured: bool` property — consumed by Task 3 (`GoogleOAuthClient` construction) and Task 5 (route handlers).

- [ ] **Step 1: Add the new settings fields**

In `backend/app/config.py`, add these fields to `Settings` right after the existing `schwab_redirect_uri` block (so Google's OAuth settings sit next to the other OAuth provider settings):

```python
    google_client_id: str | None = None
    google_client_secret: str | None = None
    google_redirect_uri: str = "http://127.0.0.1:8000/api/v1/auth/google/callback"
    frontend_login_callback_url: str = "http://127.0.0.1:8081/login/callback"
```

And add this property next to `schwab_configured`:

```python
    @property
    def google_configured(self) -> bool:
        return bool(self.google_client_id and self.google_client_secret)
```

- [ ] **Step 2: Add a quick settings test**

In `backend/app/tests/test_api.py`, add:

```python
async def test_health_reports_environment_without_google_credentials(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
```

(This just confirms the app still boots with the new settings fields present and unset — `conftest.py`'s `client` fixture doesn't pass `google_client_id`/`google_client_secret`, so they default to `None`, exercising the "not configured" path immediately.)

- [ ] **Step 3: Run it**

Run: `cd backend && uv run pytest app/tests/test_api.py -v`
Expected: PASS (all tests in the file, including the new one)

- [ ] **Step 4: Update `.env.example`**

Add this block after the `SCHWAB_REDIRECT_URI` line in `.env.example`:

```
# Google OAuth login (web only for now). Create an OAuth client under
# "Web application" in Google Cloud Console; add GOOGLE_REDIRECT_URI to its
# authorized redirect URIs list exactly as written here.
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REDIRECT_URI=http://127.0.0.1:8000/api/v1/auth/google/callback
FRONTEND_LOGIN_CALLBACK_URL=http://127.0.0.1:8081/login/callback
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/config.py backend/app/tests/test_api.py .env.example
git commit -m "feat: add Google OAuth config settings"
```

---

### Task 2: Session token helper

**Files:**
- Create: `backend/app/security/session_token.py`
- Test: `backend/app/tests/test_session_token.py`

**Interfaces:**
- Produces: `create_session_token(user_id: UUID, secret: str, *, now: datetime | None = None) -> str`, `verify_session_token(token: str, secret: str, *, now: datetime | None = None) -> UUID | None`, `create_csrf_state(secret: str, *, now: datetime | None = None) -> str`, `verify_csrf_state(state: str, secret: str, *, now: datetime | None = None) -> bool` — consumed by Task 4 (`deps.py`) and Task 5 (`routes/auth.py`).

- [ ] **Step 1: Write the failing tests**

Create `backend/app/tests/test_session_token.py`:

```python
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.security.session_token import (
    create_csrf_state,
    create_session_token,
    verify_csrf_state,
    verify_session_token,
)


def test_session_token_round_trip_and_expiry() -> None:
    user_id = uuid4()
    issued_at = datetime(2026, 7, 24, 12, tzinfo=UTC)
    token = create_session_token(user_id, "test-secret", now=issued_at)

    assert (
        verify_session_token(token, "test-secret", now=issued_at + timedelta(days=1))
        == user_id
    )
    assert (
        verify_session_token(token, "test-secret", now=issued_at + timedelta(days=31))
        is None
    )


def test_session_token_rejects_tampering_and_wrong_secret() -> None:
    user_id = uuid4()
    token = create_session_token(user_id, "test-secret")

    assert verify_session_token(token, "different-secret") is None
    assert verify_session_token(token + "x", "test-secret") is None
    assert verify_session_token("not-a-token", "test-secret") is None


def test_csrf_state_round_trip_and_expiry() -> None:
    issued_at = datetime(2026, 7, 24, 12, tzinfo=UTC)
    state = create_csrf_state("test-secret", now=issued_at)

    assert verify_csrf_state(state, "test-secret", now=issued_at + timedelta(minutes=5))
    assert not verify_csrf_state(state, "test-secret", now=issued_at + timedelta(minutes=11))
    assert not verify_csrf_state(state, "different-secret", now=issued_at)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest app/tests/test_session_token.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.security.session_token'`

- [ ] **Step 3: Implement the helper**

Create `backend/app/security/session_token.py`:

```python
import base64
import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

SESSION_TOKEN_TTL = timedelta(days=30)
CSRF_STATE_TTL = timedelta(minutes=10)


def sign_payload(payload: str, secret: str, *, now: datetime | None = None) -> str:
    """Sign an arbitrary string payload with an embedded, verifiable issue time."""

    issued_at = int((now or datetime.now(UTC)).timestamp())
    body = f"{issued_at}:{payload}".encode()
    signature = hmac.new(secret.encode(), body, hashlib.sha256).digest()
    return f"{_encode(body)}.{_encode(signature)}"


def verify_payload(
    token: str,
    secret: str,
    *,
    ttl: timedelta,
    now: datetime | None = None,
) -> str | None:
    """Return the signed payload if the token is intact and within `ttl`, else None."""

    try:
        encoded_body, encoded_signature = token.split(".", maxsplit=1)
        body = _decode(encoded_body)
        signature = _decode(encoded_signature)
        expected = hmac.new(secret.encode(), body, hashlib.sha256).digest()
        issued_text, payload = body.decode().split(":", maxsplit=1)
        issued_at = datetime.fromtimestamp(int(issued_text), tz=UTC)
    except (ValueError, UnicodeDecodeError):
        return None

    if not hmac.compare_digest(signature, expected):
        return None
    current = now or datetime.now(UTC)
    if current - issued_at > ttl or issued_at - current > timedelta(minutes=1):
        return None
    return payload


def create_session_token(user_id: UUID, secret: str, *, now: datetime | None = None) -> str:
    return sign_payload(str(user_id), secret, now=now)


def verify_session_token(
    token: str, secret: str, *, now: datetime | None = None
) -> UUID | None:
    payload = verify_payload(token, secret, ttl=SESSION_TOKEN_TTL, now=now)
    if payload is None:
        return None
    try:
        return UUID(payload)
    except ValueError:
        return None


def create_csrf_state(secret: str, *, now: datetime | None = None) -> str:
    return sign_payload(secrets.token_urlsafe(16), secret, now=now)


def verify_csrf_state(state: str, secret: str, *, now: datetime | None = None) -> bool:
    return verify_payload(state, secret, ttl=CSRF_STATE_TTL, now=now) is not None


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
```

Note: `backend/app/security/__init__.py` already exists (it's a package), so no new `__init__.py` is needed.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest app/tests/test_session_token.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/security/session_token.py backend/app/tests/test_session_token.py
git commit -m "feat: add signed session token and CSRF state helpers"
```

---

### Task 3: Google OAuth client

**Files:**
- Create: `backend/app/providers/google/__init__.py`
- Create: `backend/app/providers/google/oauth.py`
- Test: `backend/app/tests/test_google_oauth.py`

**Interfaces:**
- Produces: `GoogleUserInfo` (pydantic model: `sub: str`, `email: str`, `name: str | None`, `picture: str | None`, `email_verified: bool`), `GoogleOAuthClient(client_id, client_secret, redirect_uri, http=None)` with `.authorization_url(*, state: str) -> str`, `async .exchange_code(*, code: str) -> str` (returns the access token), `async .fetch_userinfo(*, access_token: str) -> GoogleUserInfo` — consumed by Task 5 (`routes/auth.py`).

- [ ] **Step 1: Write the failing tests**

Create `backend/app/tests/test_google_oauth.py`:

```python
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
```

Note: `TOKEN_URL`/`USERINFO_URL` point at real Google hostnames, but `httpx.MockTransport` intercepts all requests made through that `AsyncClient` regardless of host — the handler only asserts on `request.url.path`, matching the `test_sec_adapter.py` convention.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest app/tests/test_google_oauth.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.providers.google'`

- [ ] **Step 3: Implement the client**

Create `backend/app/providers/google/__init__.py` (empty file).

Create `backend/app/providers/google/oauth.py`:

```python
from urllib.parse import urlencode

import httpx
from pydantic import BaseModel

AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"


class GoogleUserInfo(BaseModel):
    sub: str
    email: str
    name: str | None = None
    picture: str | None = None
    email_verified: bool = False


class GoogleOAuthClient:
    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        http: httpx.AsyncClient | None = None,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._redirect_uri = redirect_uri
        self._http = http

    def authorization_url(self, *, state: str) -> str:
        query = urlencode(
            {
                "response_type": "code",
                "client_id": self._client_id,
                "redirect_uri": self._redirect_uri,
                "scope": "openid email profile",
                "state": state,
                "prompt": "select_account",
            }
        )
        return f"{AUTHORIZE_URL}?{query}"

    async def exchange_code(self, *, code: str) -> str:
        response = await self._request(
            "POST",
            TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "redirect_uri": self._redirect_uri,
            },
        )
        access_token = response.json().get("access_token")
        if not access_token:
            raise ValueError("Google token response did not include an access token")
        return access_token

    async def fetch_userinfo(self, *, access_token: str) -> GoogleUserInfo:
        response = await self._request(
            "GET",
            USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        return GoogleUserInfo.model_validate(response.json())

    async def _request(self, method: str, url: str, **kwargs: object) -> httpx.Response:
        owns_client = self._http is None
        client = self._http or httpx.AsyncClient(timeout=20)
        try:
            response = await client.request(method, url, **kwargs)
            response.raise_for_status()
            return response
        finally:
            if owns_client:
                await client.aclose()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest app/tests/test_google_oauth.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/providers/google backend/app/tests/test_google_oauth.py
git commit -m "feat: add Google OAuth client (code exchange + userinfo)"
```

---

### Task 4: Extend `get_current_user_id` to accept a session token

**Files:**
- Modify: `backend/app/api/deps.py`
- Test: `backend/app/tests/test_deps.py`

**Interfaces:**
- Consumes: `verify_session_token` from Task 2 (`app/security/session_token.py`).
- Produces: `get_current_user_id` (unchanged signature/behavior for existing callers, now also accepts a Bearer token), `require_current_user_id(request, authorization=Header(default=None)) -> UUID` (raises 401 if no valid token) — consumed by Task 5 (`routes/auth.py`'s `/me` endpoint).

- [ ] **Step 1: Write the failing tests**

Create `backend/app/tests/test_deps.py`:

```python
from uuid import uuid4

from httpx import AsyncClient

from app.security.session_token import create_session_token


async def test_current_user_falls_back_to_dev_user_without_a_token(client: AsyncClient) -> None:
    response = await client.get("/api/v1/holdings")
    assert response.status_code == 200


async def test_bearer_token_overrides_dev_user(client: AsyncClient) -> None:
    other_user_id = uuid4()
    token = create_session_token(other_user_id, "dev-only-change-me")

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
```

Note: `"dev-only-change-me"` matches `Settings.app_secret`'s default (`conftest.py`'s `client` fixture doesn't override `app_secret`), and the third test targets the `/auth/me` endpoint being built in Task 5 — it's included here since it's the natural place to prove `require_current_user_id`'s 401 behavior, but it won't pass until Task 5 registers the route. Skip running it until Task 5; the first two tests should pass after this task alone.

- [ ] **Step 2: Run the first two tests to verify behavior before the change**

Run: `cd backend && uv run pytest app/tests/test_deps.py::test_current_user_falls_back_to_dev_user_without_a_token app/tests/test_deps.py::test_bearer_token_overrides_dev_user -v`
Expected: `test_current_user_falls_back_to_dev_user_without_a_token` PASSes already (no code change needed for it); `test_bearer_token_overrides_dev_user` PASSes too, since an unrecognized `Authorization` header is currently just ignored by FastAPI (no such parameter exists yet) — the real check is Step 4 confirming the header is now actually read. Run `git stash` before this step and `git stash pop` after, if you want to see it fail against `dev_user_id`-only behavior first; otherwise proceed to Step 3.

- [ ] **Step 3: Update `get_current_user_id` and add `require_current_user_id`**

Replace the full contents of `backend/app/api/deps.py`:

```python
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
    settings: Settings = request.app.state.settings
    bearer_user_id = _resolve_bearer_user_id(authorization, settings)
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
```

- [ ] **Step 4: Run the first two tests to verify they pass**

Run: `cd backend && uv run pytest app/tests/test_deps.py::test_current_user_falls_back_to_dev_user_without_a_token app/tests/test_deps.py::test_bearer_token_overrides_dev_user -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/deps.py backend/app/tests/test_deps.py
git commit -m "feat: resolve current user from a session Bearer token when present"
```

---

### Task 5: Auth routes (authorize, callback, me)

**Files:**
- Create: `backend/app/api/routes/auth.py`
- Modify: `backend/app/api/schemas.py`
- Modify: `backend/app/api/router.py`
- Test: `backend/app/tests/test_auth_routes.py` (also finishes `test_deps.py::test_me_requires_a_valid_bearer_token` from Task 4)

**Interfaces:**
- Consumes: `Settings.google_client_id/secret/redirect_uri/frontend_login_callback_url` (Task 1), `GoogleOAuthClient`/`GoogleUserInfo` (Task 3), `create_csrf_state`/`verify_csrf_state`/`create_session_token` (Task 2), `require_current_user_id` (Task 4), `get_db`/`get_app_settings` (`deps.py`), `User` model (`db/models.py`).
- Produces: `GET /api/v1/auth/google/authorize`, `GET /api/v1/auth/google/callback`, `GET /api/v1/auth/me` — the last consumed by the frontend's `AuthContext` in Task 7.

- [ ] **Step 1: Add the `AuthUser` schema**

In `backend/app/api/schemas.py`, add near `OAuthAuthorizeResponse`:

```python
class AuthUser(APIModel):
    id: UUID
    email: str
    display_name: str
```

- [ ] **Step 2: Write the failing tests**

Create `backend/app/tests/test_auth_routes.py`:

```python
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
```

The third test monkeypatches `auth_routes._google_client` (the module-level factory function, not `httpx` itself) with a fake client, following the same monkeypatch-your-own-seam convention already used in `test_market_api.py` (`monkeypatch.setattr(provider, "_get", fake_get)`). Because `_google_client` is replaced entirely, the shared `client` fixture works as-is — no need for a Google-configured `Settings`/app instance, and no network mocking required.

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd backend && uv run pytest app/tests/test_auth_routes.py -v`
Expected: FAIL with 404s (no `/api/v1/auth/*` routes registered yet)

- [ ] **Step 4: Implement `routes/auth.py`**

Create `backend/app/api/routes/auth.py`:

```python
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx
import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_app_settings, get_db, require_current_user_id
from app.api.schemas import AuthUser, OAuthAuthorizeResponse
from app.config import Settings
from app.db.models import User
from app.providers.google.oauth import GoogleOAuthClient
from app.security.session_token import create_csrf_state, create_session_token, verify_csrf_state

router = APIRouter(prefix="/auth", tags=["auth"])
logger = structlog.get_logger()


@router.get("/google/authorize", response_model=OAuthAuthorizeResponse)
async def google_authorize(
    settings: Settings = Depends(get_app_settings),
) -> OAuthAuthorizeResponse:
    client = _google_client(settings)
    state = create_csrf_state(settings.app_secret.get_secret_value())
    return OAuthAuthorizeResponse(authorization_url=client.authorization_url(state=state))


@router.get("/google/callback", include_in_schema=False)
async def google_callback(
    code: str | None = Query(default=None, min_length=1),
    state_value: str = Query(alias="state", min_length=1),
    error: str | None = Query(default=None),
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
) -> RedirectResponse:
    if not verify_csrf_state(state_value, settings.app_secret.get_secret_value()):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired Google OAuth state",
        )

    if error:
        return RedirectResponse(_with_query(settings.frontend_login_callback_url, error="1"))
    if code is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google callback did not include an authorization code.",
        )

    client = _google_client(settings)
    try:
        access_token = await client.exchange_code(code=code)
        userinfo = await client.fetch_userinfo(access_token=access_token)
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Google rejected the authorization exchange.",
        ) from exc

    user = await session.scalar(select(User).where(User.email == userinfo.email))
    if user is None:
        user = User(
            email=userinfo.email,
            display_name=userinfo.name or userinfo.email.split("@")[0],
        )
        session.add(user)
        await session.flush()
    await session.commit()

    token = create_session_token(user.id, settings.app_secret.get_secret_value())
    return RedirectResponse(_with_query(settings.frontend_login_callback_url, session=token))


@router.get("/me", response_model=AuthUser)
async def me(
    session: AsyncSession = Depends(get_db),
    user_id=Depends(require_current_user_id),
) -> AuthUser:
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return AuthUser.model_validate(user)


def _google_client(settings: Settings) -> GoogleOAuthClient:
    if not settings.google_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Add Google OAuth credentials before signing in.",
        )
    return GoogleOAuthClient(
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        redirect_uri=settings.google_redirect_uri,
    )


def _with_query(url: str, **values: str) -> str:
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query))
    query.update(values)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))
```

- [ ] **Step 5: Register the router**

In `backend/app/api/router.py`, add `auth` to the import list and register it first (auth routes should be easy to find at the top):

```python
from app.api.routes import (
    assistant,
    auth,
    connections,
    feed,
    health,
    market,
    money,
    plaid,
    portfolio,
    settings,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(health.router)
```

(Keep the remaining `include_router` calls exactly as they are today — only the `auth` import and its `include_router` line are new.)

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd backend && uv run pytest app/tests/test_auth_routes.py app/tests/test_deps.py -v`
Expected: PASS (all tests, including `test_me_requires_a_valid_bearer_token` from Task 4 now that `/auth/me` exists)

- [ ] **Step 7: Run the full backend test suite**

Run: `cd backend && uv run pytest -v`
Expected: PASS (no regressions in any existing test file)

- [ ] **Step 8: Commit**

```bash
git add backend/app/api/routes/auth.py backend/app/api/schemas.py backend/app/api/router.py backend/app/tests/test_auth_routes.py
git commit -m "feat: add Google OAuth login routes (authorize, callback, me)"
```

---

### Task 6: Frontend auth plumbing (token storage, types, api client)

**Files:**
- Create: `apps/client/src/lib/auth.ts`
- Modify: `apps/client/src/lib/types.ts`
- Modify: `apps/client/src/lib/api.ts`

**Interfaces:**
- Produces: `getToken(): string | null`, `setToken(token: string | null): void` (from `lib/auth.ts`); `AuthUser` type (from `lib/types.ts`); `api.googleAuthorize()`, `api.me()` (from `lib/api.ts`) — consumed by Task 7 (`AuthContext`).

- [ ] **Step 1: Create the token storage helper**

Create `apps/client/src/lib/auth.ts`:

```typescript
import { Platform } from 'react-native';

const STORAGE_KEY = 'posted_session_token';

export function getToken(): string | null {
  if (Platform.OS !== 'web') return null;
  return window.localStorage.getItem(STORAGE_KEY);
}

export function setToken(token: string | null): void {
  if (Platform.OS !== 'web') return;
  if (token) {
    window.localStorage.setItem(STORAGE_KEY, token);
  } else {
    window.localStorage.removeItem(STORAGE_KEY);
  }
}
```

- [ ] **Step 2: Add the `AuthUser` type**

In `apps/client/src/lib/types.ts`, add at the end of the file:

```typescript
export type AuthUser = {
  id: string;
  email: string;
  display_name: string;
};
```

- [ ] **Step 3: Wire the API client**

In `apps/client/src/lib/api.ts`:

Add the import at the top (alongside the existing `Platform` import):

```typescript
import { getToken } from './auth';
```

Update the `request` function's headers to attach the bearer token when present:

```typescript
async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const token = getToken();
  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options?.headers,
    },
  });
  if (!response.ok) {
    const body = await response.text();
    let message = body;
    try {
      const parsed = JSON.parse(body) as { detail?: string };
      message = parsed.detail ?? body;
    } catch {
      // Keep non-JSON provider and proxy errors readable.
    }
    throw new Error(message || `Posted API returned ${response.status}`);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}
```

Add two entries to the `api` object, next to `authorizeSchwab`:

```typescript
  authorizeGoogle: () =>
    request<{ authorization_url: string }>('/auth/google/authorize'),
  me: () => request<AuthUser>('/auth/me'),
```

Add `AuthUser` to the type imports at the top of the file (alphabetical, matching the existing import list style).

- [ ] **Step 4: Typecheck**

Run: `cd apps/client && npm run typecheck`
Expected: No errors

- [ ] **Step 5: Commit**

```bash
git add apps/client/src/lib/auth.ts apps/client/src/lib/types.ts apps/client/src/lib/api.ts
git commit -m "feat: add session token storage and auth API calls"
```

---

### Task 7: AuthContext and app wiring

**Files:**
- Create: `apps/client/src/lib/AuthContext.tsx`
- Modify: `apps/client/src/app/_layout.tsx`

**Interfaces:**
- Consumes: `getToken`/`setToken` (Task 6, `lib/auth.ts`), `api.me` (Task 6, `lib/api.ts`), `AuthUser` (Task 6, `lib/types.ts`).
- Produces: `AuthProvider` (React component), `useAuth(): { user: AuthUser | null; isLoading: boolean; signIn: (token: string) => void; signOut: () => void }` — consumed by Task 8 (`login.tsx`), Task 9 (`login/callback.tsx`), Task 10 (`AppShell.tsx`), Task 11 (`settings.tsx`).

- [ ] **Step 1: Create the context**

Create `apps/client/src/lib/AuthContext.tsx`:

```typescript
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { createContext, useContext, useState, type ReactNode } from 'react';

import { setToken } from '@/lib/auth';
import { api } from '@/lib/api';
import type { AuthUser } from '@/lib/types';

type AuthContextValue = {
  user: AuthUser | null;
  isLoading: boolean;
  signIn: (token: string) => void;
  signOut: () => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [hasToken, setHasToken] = useState(() => typeof window !== 'undefined');

  const me = useQuery({
    queryKey: ['auth-me'],
    queryFn: api.me,
    retry: false,
    enabled: hasToken,
  });

  const signIn = (token: string) => {
    setToken(token);
    setHasToken(true);
    void queryClient.invalidateQueries({ queryKey: ['auth-me'] });
  };

  const signOut = () => {
    setToken(null);
    queryClient.setQueryData(['auth-me'], null);
    void queryClient.invalidateQueries({ queryKey: ['auth-me'] });
  };

  const value: AuthContextValue = {
    user: me.isError ? null : (me.data ?? null),
    isLoading: hasToken && me.isLoading,
    signIn,
    signOut,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used within an AuthProvider');
  return context;
}
```

Note: `hasToken` is intentionally seeded from `typeof window !== 'undefined'` rather than reading `getToken()` directly at module scope — the query itself (`enabled: hasToken`) is what gates the network call, and `api.me()` will simply 401 (surfaced as `me.isError`) if no token is actually stored, which `signIn`/`signOut` and the `enabled` flag account for on every subsequent auth state change.

- [ ] **Step 2: Wrap the app**

In `apps/client/src/app/_layout.tsx`, add the import:

```typescript
import { AuthProvider } from '@/lib/AuthContext';
```

Wrap `QueryClientProvider`'s children in `AuthProvider`, and register the two new screens. The full updated return becomes:

```typescript
  return (
    <SafeAreaProvider>
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <StatusBar style="dark" />
          <Stack screenOptions={{ headerShown: false, animation: 'fade' }}>
            <Stack.Screen name="index" />
            <Stack.Screen name="login" />
            <Stack.Screen name="login/callback" />
            <Stack.Screen name="feed" />
            <Stack.Screen name="holdings" />
            <Stack.Screen name="settings" />
            <Stack.Screen name="money" />
            <Stack.Screen name="transactions" />
            <Stack.Screen name="subscriptions" />
            <Stack.Screen name="invest" />
            <Stack.Screen name="news" />
            <Stack.Screen name="assistant" />
            <Stack.Screen name="event/[id]" />
            <Stack.Screen name="stock/[symbol]" />
          </Stack>
        </AuthProvider>
      </QueryClientProvider>
    </SafeAreaProvider>
  );
```

- [ ] **Step 3: Typecheck**

Run: `cd apps/client && npm run typecheck`
Expected: No errors (the `login` and `login/callback` screens don't exist as files yet, but Expo Router's `Stack.Screen name=` doesn't require the file to exist for typechecking — it's just a string prop; Tasks 8 and 9 add the actual files next)

- [ ] **Step 4: Commit**

```bash
git add apps/client/src/lib/AuthContext.tsx apps/client/src/app/_layout.tsx
git commit -m "feat: add AuthContext and wire it into the root layout"
```

---

### Task 8: Login page

**Files:**
- Create: `apps/client/src/app/login.tsx`

**Interfaces:**
- Consumes: `api.authorizeGoogle()` (Task 6), `useAuth()` (Task 7).

- [ ] **Step 1: Create the page**

Create `apps/client/src/app/login.tsx`:

```typescript
import { useMutation } from '@tanstack/react-query';
import { useRouter } from 'expo-router';
import { useEffect } from 'react';
import { Platform, Pressable, StyleSheet, Text, View } from 'react-native';

import { BrandMark } from '@/components/BrandMark';
import { api } from '@/lib/api';
import { useAuth } from '@/lib/AuthContext';
import { colors, radius, spacing, type as typeTokens } from '@/theme/tokens';

export default function LoginScreen() {
  const router = useRouter();
  const { user } = useAuth();

  useEffect(() => {
    if (user) router.replace('/');
  }, [user, router]);

  const authorize = useMutation({
    mutationFn: api.authorizeGoogle,
    onSuccess: ({ authorization_url }) => {
      if (Platform.OS === 'web') window.location.href = authorization_url;
    },
  });

  return (
    <View style={styles.root}>
      <View style={styles.card}>
        <BrandMark />
        <Text style={styles.title}>Sign in to Posted</Text>
        <Text style={styles.caption}>
          Use your Google account to personalize your dashboard.
        </Text>
        {Platform.OS === 'web' ? (
          <Pressable
            accessibilityRole="button"
            disabled={authorize.isPending}
            onPress={() => authorize.mutate()}
            style={({ pressed }) => [styles.button, pressed && styles.buttonPressed]}>
            <Text style={styles.buttonText}>
              {authorize.isPending ? 'Redirecting…' : 'Continue with Google'}
            </Text>
          </Pressable>
        ) : (
          <Text style={styles.caption}>
            Sign-in is available on the web app for now.
          </Text>
        )}
        {authorize.isError ? (
          <Text style={styles.error}>{authorize.error.message}</Text>
        ) : null}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: colors.canvas,
    alignItems: 'center',
    justifyContent: 'center',
    padding: spacing.lg,
  },
  card: {
    width: '100%',
    maxWidth: 380,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: radius.lg,
    padding: spacing.xl,
    gap: spacing.sm,
    alignItems: 'flex-start',
  },
  title: {
    color: colors.ink,
    fontSize: typeTokens.title,
    fontWeight: '600',
    marginTop: spacing.md,
  },
  caption: {
    color: colors.inkMuted,
    fontSize: typeTokens.body,
    lineHeight: 20,
  },
  button: {
    marginTop: spacing.sm,
    height: 46,
    width: '100%',
    borderRadius: radius.md,
    backgroundColor: colors.teal,
    alignItems: 'center',
    justifyContent: 'center',
  },
  buttonPressed: { opacity: 0.85 },
  buttonText: { color: colors.white, fontSize: typeTokens.body, fontWeight: '700' },
  error: { color: colors.negative, fontSize: typeTokens.caption, marginTop: spacing.xs },
});
```

- [ ] **Step 2: Typecheck**

Run: `cd apps/client && npm run typecheck`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add apps/client/src/app/login.tsx
git commit -m "feat: add Google sign-in login page"
```

---

### Task 9: Login callback page

**Files:**
- Create: `apps/client/src/app/login/callback.tsx`

**Interfaces:**
- Consumes: `useAuth().signIn` (Task 7).

- [ ] **Step 1: Create the directory and page**

Create `apps/client/src/app/login/callback.tsx`:

```typescript
import { useLocalSearchParams, useRouter } from 'expo-router';
import { useEffect } from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { useAuth } from '@/lib/AuthContext';
import { colors, spacing, type as typeTokens } from '@/theme/tokens';

export default function LoginCallbackScreen() {
  const router = useRouter();
  const { signIn } = useAuth();
  const params = useLocalSearchParams<{ session?: string; error?: string }>();

  useEffect(() => {
    if (params.session) {
      signIn(params.session);
      router.replace('/');
    }
  }, [params.session, signIn, router]);

  if (params.error) {
    return (
      <View style={styles.root}>
        <Text style={styles.text}>
          Google sign-in was cancelled or rejected. Return to the login page and try again.
        </Text>
      </View>
    );
  }

  return (
    <View style={styles.root}>
      <Text style={styles.text}>Signing you in…</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: spacing.lg },
  text: { color: colors.inkMuted, fontSize: typeTokens.body, textAlign: 'center' },
});
```

Note: this file lives at `app/login/callback.tsx`, which Expo Router maps to the `/login/callback` route — matching `Stack.Screen name="login/callback"` already registered in Task 7.

- [ ] **Step 2: Typecheck**

Run: `cd apps/client && npm run typecheck`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add apps/client/src/app/login/callback.tsx
git commit -m "feat: add login callback page that stores the session token"
```

---

### Task 10: User menu in AppShell

**Files:**
- Modify: `apps/client/src/components/AppShell.tsx`

**Interfaces:**
- Consumes: `useAuth()` (Task 7).

- [ ] **Step 1: Remove Settings from the mobile bottom nav**

In `apps/client/src/components/AppShell.tsx`, remove this line from the `mobileNav` array (it's the only place `Settings` appears in either nav array today):

```typescript
  { label: 'Settings', href: '/settings', icon: Settings },
```

The `Settings` icon import from `lucide-react-native` is now unused in the icon list — leave the import itself if `AppPath` still references `/settings` (it does, for the `router.push('/settings')` call added below), but remove `Settings` specifically from the `lucide-react-native` import line since no icon usage remains. Check with `npm run typecheck` in Step 5 — if it flags an unused import, remove it there.

- [ ] **Step 2: Add menu state and the dropdown**

Add these imports at the top of the file:

```typescript
import { useState } from 'react';
import { useAuth } from '@/lib/AuthContext';
```

Inside the `AppShell` function, after the existing `const desktop = width >= 920;` line, add:

```typescript
  const { user, signOut } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);

  const initials = user
    ? user.display_name
        .split(' ')
        .map((part) => part[0])
        .slice(0, 2)
        .join('')
        .toUpperCase()
    : 'PU';
```

Replace the existing avatar block:

```typescript
            <View style={styles.avatar}>
              <Text style={styles.avatarText}>AM</Text>
            </View>
```

with a pressable version plus the dropdown, rendered as a sibling right after it (still inside `styles.topbar`):

```typescript
            <Pressable
              accessibilityRole="button"
              accessibilityLabel="Account menu"
              onPress={() => setMenuOpen((open) => !open)}
              style={styles.avatar}>
              <Text style={styles.avatarText}>{initials}</Text>
            </Pressable>
          </View>

          {menuOpen ? (
            <>
              <Pressable
                style={styles.menuBackdrop}
                onPress={() => setMenuOpen(false)}
              />
              <View style={styles.userMenu}>
                <View style={styles.userMenuHeader}>
                  <Text style={styles.userMenuName} numberOfLines={1}>
                    {user ? user.display_name : 'Not signed in'}
                  </Text>
                  {user ? (
                    <Text style={styles.userMenuEmail} numberOfLines={1}>
                      {user.email}
                    </Text>
                  ) : null}
                </View>
                <Pressable
                  style={styles.userMenuItem}
                  onPress={() => {
                    setMenuOpen(false);
                    router.push('/settings');
                  }}>
                  <Text style={styles.userMenuItemText}>Settings</Text>
                </Pressable>
                {user ? (
                  <Pressable
                    style={styles.userMenuItem}
                    onPress={() => {
                      setMenuOpen(false);
                      signOut();
                      router.replace('/');
                    }}>
                    <Text style={styles.userMenuItemText}>Sign out</Text>
                  </Pressable>
                ) : (
                  <Pressable
                    style={styles.userMenuItem}
                    onPress={() => {
                      setMenuOpen(false);
                      router.push('/login');
                    }}>
                    <Text style={styles.userMenuItemText}>Sign in with Google</Text>
                  </Pressable>
                )}
              </View>
            </>
          ) : null}
```

Note the `</View>` closing `styles.topbar` moved: it now closes right after the new `Pressable` instead of after the old avatar `View`. The `{menuOpen ? ... : null}` block is a new sibling positioned after `topbar` closes and before `{scroll ? (...) : (...)}`, so the dropdown overlays page content instead of being clipped to the topbar's bounds.

- [ ] **Step 3: Add the new styles**

Add these entries to the `StyleSheet.create` call at the bottom of the file, near the existing `avatar`/`avatarText` entries:

```typescript
  menuBackdrop: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    zIndex: 10,
  },
  userMenu: {
    position: 'absolute',
    top: 64 + 8,
    right: 20,
    width: 220,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: radius.md,
    paddingVertical: 6,
    zIndex: 11,
    shadowColor: '#000',
    shadowOpacity: 0.12,
    shadowRadius: 12,
    shadowOffset: { width: 0, height: 4 },
    elevation: 6,
  },
  userMenuHeader: {
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: colors.line,
  },
  userMenuName: { color: colors.ink, fontSize: 13, fontWeight: '700' },
  userMenuEmail: { color: colors.inkMuted, fontSize: 11, marginTop: 2 },
  userMenuItem: { paddingHorizontal: 14, height: 40, justifyContent: 'center' },
  userMenuItemText: { color: colors.ink, fontSize: 13, fontWeight: '500' },
```

Add `radius` to the existing `@/theme/tokens` import at the top of the file (alongside `colors` and `spacing`).

- [ ] **Step 4: Typecheck**

Run: `cd apps/client && npm run typecheck`
Expected: No errors

- [ ] **Step 5: Manual verification**

Run: `cd apps/client && npm run web`
Open the app in a browser. Confirm:
- The avatar in the topbar shows "PU" (no one is logged in yet) and clicking it opens a dropdown with "Not signed in", "Settings", and "Sign in with Google".
- Clicking outside the dropdown closes it.
- Clicking "Settings" navigates to `/settings` and closes the dropdown.
- The bottom nav (narrow window width) no longer shows a "Settings" tab.

- [ ] **Step 6: Commit**

```bash
git add apps/client/src/components/AppShell.tsx
git commit -m "feat: turn the topbar avatar into a user menu with Settings and sign-in/out"
```

---

### Task 11: Account panel on the Settings page

**Files:**
- Modify: `apps/client/src/app/settings.tsx`

**Interfaces:**
- Consumes: `useAuth()` (Task 7).

- [ ] **Step 1: Add the import**

In `apps/client/src/app/settings.tsx`, add:

```typescript
import { useRouter } from 'expo-router';
```

(merge into the existing `expo-router` import, which already brings in `useLocalSearchParams`)

```typescript
import { useLocalSearchParams, useRouter } from 'expo-router';
```

And add:

```typescript
import { useAuth } from '@/lib/AuthContext';
```

- [ ] **Step 2: Add the account panel**

Inside `SettingsScreen`, right after `const params = useLocalSearchParams<{ schwab?: string }>();`, add:

```typescript
  const router = useRouter();
  const { user } = useAuth();
```

Add a new panel as the first child of `styles.settingsGrid`'s `View`, immediately after the opening tag (before the "Banking connections" panel):

```typescript
        <View style={styles.panel}>
          <SectionHeader title="Account" caption="Signed-in identity for this device" />
          <View style={styles.settingRow}>
            <View style={styles.settingCopy}>
              <Text style={styles.settingTitle}>
                {user ? user.display_name : 'Using the demo account'}
              </Text>
              <Text style={styles.settingCaption}>
                {user ? user.email : 'Sign in with Google to personalize your dashboard.'}
              </Text>
            </View>
            {!user ? (
              <Pressable
                accessibilityRole="button"
                onPress={() => router.push('/login')}
                style={styles.connectButton}>
                <Text style={styles.connectButtonText}>Sign in</Text>
              </Pressable>
            ) : null}
          </View>
        </View>

```

- [ ] **Step 3: Typecheck**

Run: `cd apps/client && npm run typecheck`
Expected: No errors

- [ ] **Step 4: Manual verification**

Run: `cd apps/client && npm run web`
Navigate to `/settings`. Confirm the new "Account" panel appears at the top showing "Using the demo account" with a "Sign in" button (since no one is logged in yet — Google credentials aren't configured, so the full round-trip can't be exercised until real `GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET` values are added to `.env`).

- [ ] **Step 5: Commit**

```bash
git add apps/client/src/app/settings.tsx
git commit -m "feat: show signed-in account on the Settings page"
```

---

## After all tasks

Once real `GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET` values are added to `.env` (see Task 1's `.env.example` block) and both the backend (`uvicorn app.main:app --reload`, from `backend/`) and frontend (`npm run web`, from `apps/client/`) are running, do a full manual pass: click "Continue with Google" on `/login`, complete the Google consent screen, confirm redirect back to `/` with the user menu now showing the real name/email, refresh the page to confirm the session persists (via `localStorage`), and click "Sign out" to confirm it returns to the logged-out state without breaking any other screen.
