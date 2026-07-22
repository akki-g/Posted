from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_app_settings, get_current_user_id, get_db
from app.api.schemas import (
    ConnectionStatus,
    OAuthAuthorizeResponse,
    SyncAccepted,
    SyncRequest,
)
from app.config import Settings
from app.db.models import BrokerageConnection
from app.providers.schwab.credentials import SchwabCredentialStore, TokenVault
from app.providers.schwab.oauth import (
    SchwabOAuthClient,
    create_oauth_state,
    verify_oauth_state,
)
from app.services.dashboard import get_connections, run_demo_sync

router = APIRouter(prefix="/connections", tags=["connections"])


@router.get("", response_model=list[ConnectionStatus])
async def connections(
    session: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
    settings: Settings = Depends(get_app_settings),
) -> list[ConnectionStatus]:
    return await get_connections(session, user_id=user_id, demo_mode=settings.demo_mode)


@router.get("/schwab/status")
async def schwab_status(settings: Settings = Depends(get_app_settings)) -> dict[str, object]:
    return {
        "configured": settings.schwab_configured,
        "demo_mode": settings.demo_mode,
        "redirect_uri": settings.schwab_redirect_uri,
        "message": (
            "Schwab credentials are configured."
            if settings.schwab_configured
            else "Add Schwab developer credentials to enable the OAuth connection flow."
        ),
    }


@router.get("/schwab/authorize", response_model=OAuthAuthorizeResponse)
async def schwab_authorize(
    user_id: UUID = Depends(get_current_user_id),
    settings: Settings = Depends(get_app_settings),
) -> OAuthAuthorizeResponse:
    client = _schwab_client(settings)
    oauth_state = create_oauth_state(
        user_id=user_id,
        secret=settings.app_secret.get_secret_value(),
    )
    return OAuthAuthorizeResponse(authorization_url=client.authorization_url(state=oauth_state))


@router.get("/schwab/callback", include_in_schema=False)
async def schwab_callback(
    code: str = Query(min_length=1),
    state_value: str = Query(alias="state", min_length=1),
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
) -> RedirectResponse:
    try:
        user_id = verify_oauth_state(
            state_value,
            secret=settings.app_secret.get_secret_value(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    client = _schwab_client(settings)
    try:
        tokens = await client.exchange_code(code=code)
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Schwab rejected the authorization exchange.",
        ) from exc

    connection = await session.scalar(
        select(BrokerageConnection).where(
            BrokerageConnection.user_id == user_id,
            BrokerageConnection.provider == "schwab",
        )
    )
    if connection is None:
        connection = BrokerageConnection(
            user_id=user_id,
            provider="schwab",
            display_name="Charles Schwab",
            status="connected",
        )
        session.add(connection)
        await session.flush()
    else:
        connection.status = "connected"

    store = SchwabCredentialStore(
        session=session,
        vault=TokenVault(settings.app_secret.get_secret_value()),
    )
    await store.save(connection_id=connection.id, tokens=tokens)
    await session.commit()
    return RedirectResponse(_with_query(settings.frontend_app_url, schwab="connected"))


@router.post("/{connection_id}/sync", response_model=SyncAccepted)
async def sync_connection(
    connection_id: UUID,
    request: SyncRequest,
    session: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
    settings: Settings = Depends(get_app_settings),
) -> SyncAccepted:
    connections = await get_connections(session, user_id=user_id, demo_mode=settings.demo_mode)
    if not any(item.id == connection_id for item in connections):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found")
    if not settings.demo_mode:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Live sync is activated after the human-owned orchestrator is complete.",
        )
    return await run_demo_sync(
        session,
        connection_id=connection_id,
        idempotency_key=request.idempotency_key,
    )


def _schwab_client(settings: Settings) -> SchwabOAuthClient:
    if not settings.schwab_client_id or not settings.schwab_client_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Add Schwab developer credentials before connecting an account.",
        )
    return SchwabOAuthClient(
        client_id=settings.schwab_client_id,
        client_secret=settings.schwab_client_secret,
        redirect_uri=settings.schwab_redirect_uri,
    )


def _with_query(url: str, **values: str) -> str:
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query))
    query.update(values)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))
