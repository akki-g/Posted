from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import UUID

import httpx
import structlog
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
from app.providers.schwab.client import SchwabTraderClient
from app.providers.schwab.credentials import SchwabCredentialStore, TokenVault
from app.providers.schwab.oauth import (
    SchwabOAuthClient,
    create_oauth_state,
    verify_oauth_state,
)
from app.services.dashboard import get_connections, run_demo_sync
from app.services.news_sync import sync_portfolio_news
from app.services.schwab_sync import SchwabSyncError, sync_schwab_connection

router = APIRouter(prefix="/connections", tags=["connections"])
logger = structlog.get_logger()


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
    code: str | None = Query(default=None, min_length=1),
    state_value: str = Query(alias="state", min_length=1),
    error: str | None = Query(default=None),
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

    if error:
        return RedirectResponse(
            _with_query(settings.frontend_app_url, schwab="error")
        )
    if code is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Schwab callback did not include an authorization code.",
        )

    client = _schwab_client(settings)
    try:
        tokens = await client.exchange_code(code=code)
    except (httpx.HTTPError, ValueError) as exc:
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
    connection = await session.scalar(
        select(BrokerageConnection).where(
            BrokerageConnection.id == connection_id,
            BrokerageConnection.user_id == user_id,
        )
    )
    if connection is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found")
    if settings.demo_mode and connection.status == "demo":
        result = await run_demo_sync(
            session,
            connection_id=connection_id,
            idempotency_key=request.idempotency_key,
        )
        await _sync_news_best_effort(session, user_id=user_id, settings=settings)
        return result

    oauth_client = _schwab_client(settings)
    credential_store = SchwabCredentialStore(
        session=session,
        vault=TokenVault(settings.app_secret.get_secret_value()),
    )
    try:
        result = await sync_schwab_connection(
            session,
            connection=connection,
            idempotency_key=request.idempotency_key,
            credential_store=credential_store,
            oauth_client=oauth_client,
            trader_factory=lambda access_token: SchwabTraderClient(
                access_token=access_token
            ),
        )
    except SchwabSyncError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    await _sync_news_best_effort(session, user_id=user_id, settings=settings)

    action = "already synchronized" if result.repeated else "synchronized"
    return SyncAccepted(
        sync_run_id=result.sync_run_id,
        status=result.status,
        message=(
            f"Schwab portfolio {action}: {result.accounts_seen} accounts and "
            f"{result.positions_seen} positions."
        ),
    )


async def _sync_news_best_effort(
    session: AsyncSession, *, user_id: UUID, settings: Settings
) -> None:
    """Refresh the impact feed after a portfolio sync. Never fails the sync response."""

    try:
        summary = await sync_portfolio_news(session, user_id=user_id, settings=settings)
        logger.info(
            "news_sync_completed",
            held_symbols=summary.held_symbols,
            fetched=summary.fetched,
            inserted=summary.inserted,
            duplicates_skipped=summary.duplicates_skipped,
            warnings=summary.warnings,
        )
    except Exception as exc:  # noqa: BLE001 - news refresh must never break a portfolio sync
        logger.warning("news_sync_failed", error=str(exc))


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
