import hmac
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx
import structlog
from fastapi import APIRouter, Cookie, Depends, HTTPException, Query, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_app_settings, get_db, require_current_user_id
from app.api.schemas import AuthUser, OAuthAuthorizeResponse
from app.config import Settings
from app.db.models import User
from app.providers.google.oauth import GoogleOAuthClient
from app.security.session_token import (
    CSRF_STATE_TTL,
    create_csrf_state,
    create_session_token,
    verify_csrf_state,
)

router = APIRouter(prefix="/auth", tags=["auth"])
logger = structlog.get_logger()

CSRF_COOKIE_NAME = "posted_oauth_state"


@router.get("/google/authorize", response_model=OAuthAuthorizeResponse)
async def google_authorize(
    response: Response,
    settings: Settings = Depends(get_app_settings),
) -> OAuthAuthorizeResponse:
    client = _google_client(settings)
    state = create_csrf_state(settings.app_secret.get_secret_value())
    # Bind the state to this browser so a completed OAuth handoff (code +
    # state) can't be captured and replayed against a different victim's
    # browser to log them into the wrong (e.g. attacker's) account.
    response.set_cookie(
        CSRF_COOKIE_NAME,
        state,
        max_age=int(CSRF_STATE_TTL.total_seconds()),
        httponly=True,
        # Keyed off the redirect URI's own scheme, not demo_mode -- those are
        # independent (this app is tested locally over plain HTTP with
        # demo_mode already off). A Secure cookie is silently dropped by the
        # browser on a non-HTTPS origin, which would break the CSRF check
        # entirely rather than just weaken it.
        secure=settings.google_redirect_uri.startswith("https://"),
        samesite="lax",
    )
    return OAuthAuthorizeResponse(authorization_url=client.authorization_url(state=state))


@router.get("/google/callback", include_in_schema=False)
async def google_callback(
    code: str | None = Query(default=None, min_length=1),
    state_value: str = Query(alias="state", min_length=1),
    error: str | None = Query(default=None),
    state_cookie: str | None = Cookie(default=None, alias=CSRF_COOKIE_NAME),
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
) -> RedirectResponse:
    # Mutating an injected `Response` dependency has no effect once the handler
    # returns its own Response object directly (as every branch below does), so
    # the cookie is cleared on each constructed RedirectResponse individually.
    if (
        not verify_csrf_state(state_value, settings.app_secret.get_secret_value())
        or not state_cookie
        or not hmac.compare_digest(state_cookie, state_value)
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired Google OAuth state",
        )

    if error:
        redirect = RedirectResponse(_with_query(settings.frontend_login_callback_url, error="1"))
        redirect.delete_cookie(CSRF_COOKIE_NAME)
        return redirect
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

    if not userinfo.email_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google account email is not verified.",
        )

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
    redirect = RedirectResponse(_with_query(settings.frontend_login_callback_url, session=token))
    redirect.delete_cookie(CSRF_COOKIE_NAME)
    return redirect


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
