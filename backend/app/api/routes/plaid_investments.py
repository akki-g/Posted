from datetime import datetime
from uuid import UUID

import httpx
import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_app_settings, get_current_user_id, get_db
from app.api.schemas import ConnectionStatus, PlaidExchangeRequest, PlaidLinkTokenResponse
from app.config import Settings
from app.db.models import BrokerageAccount, BrokerageConnection, Position
from app.providers.plaid.client import PlaidClient
from app.security.brokerage_credentials import BrokerageCredentialStore
from app.security.vault import TokenVault

router = APIRouter(prefix="/connections/plaid-investments", tags=["connections"])
logger = structlog.get_logger()


def _plaid_client(settings: Settings) -> PlaidClient:
    if not settings.plaid_client_id or not settings.plaid_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Add Plaid Sandbox credentials before connecting a brokerage.",
        )
    return PlaidClient(
        client_id=settings.plaid_client_id,
        secret=settings.plaid_secret,
        environment=settings.plaid_environment,
    )


@router.get("/status")
async def plaid_investments_status(
    settings: Settings = Depends(get_app_settings),
) -> dict[str, object]:
    return {
        "configured": settings.plaid_configured,
        "environment": settings.plaid_environment,
        "demo_mode": settings.demo_mode,
        "message": (
            "Plaid credentials are configured."
            if settings.plaid_configured
            else "Add Plaid Sandbox credentials before opening Link."
        ),
    }


@router.post("/link-token", response_model=PlaidLinkTokenResponse)
async def create_plaid_investments_link_token(
    user_id: UUID = Depends(get_current_user_id),
    settings: Settings = Depends(get_app_settings),
) -> PlaidLinkTokenResponse:
    client = _plaid_client(settings)
    try:
        result = await client.create_link_token(
            user_id=str(user_id),
            client_name=settings.app_name,
            products=["investments"],
            redirect_uri=settings.plaid_redirect_uri,
            android_package_name=settings.plaid_android_package_name,
        )
        return PlaidLinkTokenResponse(
            link_token=str(result["link_token"]),
            expiration=datetime.fromisoformat(str(result["expiration"]).replace("Z", "+00:00")),
            request_id=str(result["request_id"]) if result.get("request_id") else None,
        )
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Plaid could not create an investments Link token.",
        ) from exc


@router.post("/exchange", response_model=ConnectionStatus)
async def exchange_plaid_investments_token(
    request: PlaidExchangeRequest,
    session: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
    settings: Settings = Depends(get_app_settings),
) -> ConnectionStatus:
    client = _plaid_client(settings)
    try:
        exchange = await client.exchange_public_token(request.public_token)
        raw_accounts = await client.get_accounts(exchange.access_token)
        institution_id = (await client.get_item(exchange.access_token)).get("institution_id")
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Plaid could not connect this brokerage.",
        ) from exc

    connection = (
        await session.scalar(
            select(BrokerageConnection).where(
                BrokerageConnection.user_id == user_id,
                BrokerageConnection.provider == "plaid_investments",
                BrokerageConnection.institution_id == institution_id,
            )
        )
        if institution_id
        else None
    )
    store = BrokerageCredentialStore(
        session=session, vault=TokenVault(settings.app_secret.get_secret_value())
    )
    if connection is None:
        connection = BrokerageConnection(
            user_id=user_id, provider="plaid_investments",
            institution_id=institution_id,
            display_name="Plaid brokerage", status="connected",
        )
        session.add(connection)
        await session.flush()
    else:
        prev = await store.load(connection_id=connection.id)
        await session.commit()  # end the implicit read txn before the provider call
        if prev is not None:
            try:
                await client.remove_item(prev.access_token)
            except Exception:  # noqa: BLE001 - refresh proceeds regardless
                logger.warning("plaid_inv_old_item_remove_failed", connection_id=str(connection.id))
        connection.status = "connected"
        # A Core bulk delete does not fire the ORM cascade, and Position.account_id has
        # no DB-level ON DELETE CASCADE -- delete positions first to avoid an FK violation
        # on Postgres. Next sync repopulates both accounts and positions.
        await session.execute(
            delete(Position).where(
                Position.account_id.in_(
                    select(BrokerageAccount.id).where(
                        BrokerageAccount.connection_id == connection.id
                    )
                )
            )
        )
        await session.execute(
            delete(BrokerageAccount).where(BrokerageAccount.connection_id == connection.id)
        )
        await session.flush()

    await store.save(connection_id=connection.id, access_token=exchange.access_token)
    await session.commit()

    return ConnectionStatus(
        id=connection.id, provider=connection.provider,
        display_name=connection.display_name, status=connection.status,
        last_synced_at=connection.last_synced_at,
        account_count=len(raw_accounts), demo_mode=False,
    )
