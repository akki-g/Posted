"""Sync-before-read: shared staleness/dispatch logic for the connections API and the assistant.

Both the manual "sync now" endpoints in `app.api.routes.connections`/`app.api.routes.plaid`
and the assistant's tool-use loop need the same answer to "is this connection's data stale,
and if so, how do I refresh it" -- this module is the one place that owns the staleness
threshold and the per-provider dispatch so neither caller re-derives it.
"""

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import structlog
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.db.models import BrokerageConnection, FinancialConnection, FinancialCredential
from app.providers.plaid.client import PlaidClient
from app.providers.schwab.client import SchwabTraderClient
from app.providers.schwab.oauth import SchwabOAuthClient
from app.security.brokerage_credentials import BrokerageCredentialStore
from app.security.vault import TokenVault
from app.services.brokerage_sync import BrokerageSyncSummary
from app.services.plaid_investments_sync import sync_plaid_investments_connection
from app.services.plaid_sync import sync_plaid_money_connection
from app.services.schwab_sync import sync_schwab_connection

logger = structlog.get_logger()

# Mirrors AUTO_SYNC_STALE_MS in apps/client/src/lib/useConnectionSync.ts, so "the page
# auto-synced because it was stale" and "the assistant synced because it was stale" agree.
STALE_AFTER = timedelta(minutes=5)


def is_stale(last_synced_at: datetime | None, *, now: datetime | None = None) -> bool:
    if last_synced_at is None:
        return True
    now = now or datetime.now(UTC)
    reference = last_synced_at if last_synced_at.tzinfo else last_synced_at.replace(tzinfo=UTC)
    return now - reference > STALE_AFTER


async def _run_schwab_sync(
    session: AsyncSession,
    *,
    connection: BrokerageConnection,
    idempotency_key: str,
    settings: Settings,
) -> BrokerageSyncSummary:
    if not settings.schwab_client_id or not settings.schwab_client_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Add Schwab developer credentials before syncing this brokerage.",
        )
    return await sync_schwab_connection(
        session,
        connection=connection,
        idempotency_key=idempotency_key,
        credential_store=BrokerageCredentialStore(
            session=session, vault=TokenVault(settings.app_secret.get_secret_value())
        ),
        oauth_client=SchwabOAuthClient(
            client_id=settings.schwab_client_id,
            client_secret=settings.schwab_client_secret,
            redirect_uri=settings.schwab_redirect_uri,
        ),
        trader_factory=lambda access_token: SchwabTraderClient(access_token=access_token),
    )


async def _run_plaid_investments_sync(
    session: AsyncSession,
    *,
    connection: BrokerageConnection,
    idempotency_key: str,
    settings: Settings,
) -> BrokerageSyncSummary:
    if not settings.plaid_client_id or not settings.plaid_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Add Plaid Sandbox credentials before syncing this brokerage.",
        )
    return await sync_plaid_investments_connection(
        session,
        connection=connection,
        idempotency_key=idempotency_key,
        credential_store=BrokerageCredentialStore(
            session=session, vault=TokenVault(settings.app_secret.get_secret_value())
        ),
        client=PlaidClient(
            client_id=settings.plaid_client_id,
            secret=settings.plaid_secret,
            environment=settings.plaid_environment,
        ),
    )


BROKERAGE_SYNC_ADAPTERS: dict[str, Callable[..., Awaitable[BrokerageSyncSummary]]] = {
    "schwab": _run_schwab_sync,
    "plaid_investments": _run_plaid_investments_sync,
}


async def sync_stale_brokerage_connections(
    session: AsyncSession, *, user_id: UUID, settings: Settings
) -> None:
    """Best-effort: sync every real, stale brokerage connection for a user. Never raises."""
    # A plain-column select (not ORM entities) so a rollback from an earlier connection
    # in this loop can't leave a later connection's already-fetched attributes expired
    # and unreadable outside an awaited context (sqlalchemy.exc.MissingGreenlet).
    rows = (
        await session.execute(
            select(
                BrokerageConnection.id,
                BrokerageConnection.provider,
                BrokerageConnection.status,
                BrokerageConnection.last_synced_at,
            ).where(BrokerageConnection.user_id == user_id)
        )
    ).all()
    for connection_id, provider, conn_status, last_synced_at in rows:
        if conn_status == "demo" or not is_stale(last_synced_at):
            continue
        adapter = BROKERAGE_SYNC_ADAPTERS.get(provider)
        if adapter is None:
            continue
        connection = await session.get(BrokerageConnection, connection_id)
        if connection is None:
            continue
        try:
            await adapter(
                session,
                connection=connection,
                idempotency_key=f"assistant-sync-{uuid4()}",
                settings=settings,
            )
        except Exception as exc:  # noqa: BLE001 - a failed background sync must not block a read
            # A flush inside the adapter may have already sent SQL; without this the
            # session is left needing a rollback, and the read this sync was meant to
            # protect would raise sqlalchemy.exc.PendingRollbackError instead of running.
            await session.rollback()
            logger.warning(
                "assistant_brokerage_sync_failed",
                connection_id=str(connection_id),
                provider=provider,
                error=str(exc),
            )


async def sync_stale_money_connections(
    session: AsyncSession, *, user_id: UUID, settings: Settings
) -> None:
    """Best-effort: sync every real, stale Plaid money connection for a user. Never raises."""
    # Plain columns, not ORM entities -- see sync_stale_brokerage_connections for why.
    rows = (
        await session.execute(
            select(FinancialConnection.id, FinancialConnection.last_synced_at).where(
                FinancialConnection.user_id == user_id,
                FinancialConnection.provider == "plaid",
                FinancialConnection.is_demo.is_(False),
            )
        )
    ).all()
    for connection_id, last_synced_at in rows:
        if not is_stale(last_synced_at):
            continue
        connection = await session.get(FinancialConnection, connection_id)
        if connection is None:
            continue
        try:
            await _sync_one_money_connection(session, connection=connection, settings=settings)
        except Exception as exc:  # noqa: BLE001 - a failed background sync must not block a read
            # Same reasoning as the brokerage path above: undo any partial flush so the
            # gated read still succeeds instead of raising PendingRollbackError.
            await session.rollback()
            logger.warning(
                "assistant_money_sync_failed",
                connection_id=str(connection_id),
                error=str(exc),
            )


async def _sync_one_money_connection(
    session: AsyncSession, *, connection: FinancialConnection, settings: Settings
) -> None:
    credential = await session.scalar(
        select(FinancialCredential).where(FinancialCredential.connection_id == connection.id)
    )
    if credential is None or not settings.plaid_client_id or not settings.plaid_secret:
        return
    access_token = TokenVault(settings.app_secret.get_secret_value()).decrypt(
        credential.access_token_encrypted
    )
    client = PlaidClient(
        client_id=settings.plaid_client_id,
        secret=settings.plaid_secret,
        environment=settings.plaid_environment,
    )
    await sync_plaid_money_connection(
        session, connection=connection, access_token=access_token, client=client
    )
