from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

import httpx
import structlog
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_app_settings, get_current_user_id, get_db
from app.api.schemas import (
    MoneyConnectionStatus,
    MoneySyncResponse,
    PlaidExchangeRequest,
    PlaidLinkTokenResponse,
)
from app.config import Settings
from app.db.models import FinancialAccount, FinancialConnection, FinancialCredential
from app.providers.plaid.client import PlaidClient
from app.security.vault import TokenVault
from app.services.plaid_sync import PlaidSyncError, sync_plaid_transactions

router = APIRouter(prefix="/money/connections/plaid", tags=["money connections"])
logger = structlog.get_logger()


@router.get("/status")
async def plaid_status(settings: Settings = Depends(get_app_settings)) -> dict[str, object]:
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
async def create_plaid_link_token(
    user_id: UUID = Depends(get_current_user_id),
    settings: Settings = Depends(get_app_settings),
) -> PlaidLinkTokenResponse:
    client = _plaid_client(settings)
    try:
        result = await client.create_link_token(
            user_id=str(user_id),
            client_name=settings.app_name,
            webhook_url=settings.plaid_webhook_url,
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
            detail="Plaid could not create a Link token.",
        ) from exc


@router.post("/exchange", response_model=MoneyConnectionStatus)
async def exchange_plaid_public_token(
    request: PlaidExchangeRequest,
    session: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
    settings: Settings = Depends(get_app_settings),
) -> MoneyConnectionStatus:
    client = _plaid_client(settings)
    try:
        exchange = await client.exchange_public_token(request.public_token)
        institution_id = (await client.get_item(exchange.access_token)).get("institution_id")
        raw_accounts = await client.get_accounts(exchange.access_token)
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Plaid could not connect this financial institution.",
        ) from exc

    connection = None
    if institution_id:
        connection = await session.scalar(
            select(FinancialConnection).where(
                FinancialConnection.user_id == user_id,
                FinancialConnection.provider == "plaid",
                FinancialConnection.institution_id == institution_id,
            )
        )
    # This only fires when get_item returned no institution_id (rare) -- it is
    # NOT a backstop for pre-existing rows with institution_id = NULL from before
    # the backfill; those are handled by scripts/backfill_institution_id.py.
    if connection is None:  # fall back to legacy item_id match, else create
        connection = await session.scalar(
            select(FinancialConnection).where(
                FinancialConnection.user_id == user_id,
                FinancialConnection.provider == "plaid",
                FinancialConnection.provider_item_id == exchange.item_id,
            )
        )

    vault = TokenVault(settings.app_secret.get_secret_value())
    old_access_token: str | None = None
    if connection is not None:
        old_credential = await session.scalar(
            select(FinancialCredential).where(
                FinancialCredential.connection_id == connection.id
            )
        )
        if old_credential is not None:
            old_access_token = vault.decrypt(old_credential.access_token_encrypted)

    # Commit the read-only transaction before making any further Plaid network
    # call -- don't hold DB locks open while waiting on an external HTTP request.
    await session.commit()

    if connection is None:
        connection = FinancialConnection(
            user_id=user_id,
            provider="plaid",
            provider_item_id=exchange.item_id,
            institution_id=institution_id,
            display_name="Plaid connection",
            status="connected",
            last_synced_at=None,
            is_demo=False,
        )
        session.add(connection)
        await session.flush()
    else:
        # Refresh in place: drop the dead Item at Plaid, re-point the connection.
        if old_access_token is not None:
            try:
                await client.remove_item(old_access_token)
            except Exception:  # noqa: BLE001 - old Item removal is best-effort
                logger.warning(
                    "plaid_old_item_remove_failed", connection_id=str(connection.id)
                )
        connection.provider_item_id = exchange.item_id
        connection.institution_id = institution_id or connection.institution_id
        connection.status = "connected"
        connection.cursor = None  # new Item => fresh /transactions/sync
        await session.execute(
            delete(FinancialAccount).where(FinancialAccount.connection_id == connection.id)
        )  # cascades txns + snapshots
        await session.flush()

    credential = await session.scalar(
        select(FinancialCredential).where(FinancialCredential.connection_id == connection.id)
    )
    encrypted_token = vault.encrypt(exchange.access_token)
    if credential is None:
        session.add(
            FinancialCredential(
                connection_id=connection.id,
                access_token_encrypted=encrypted_token,
            )
        )
    else:
        credential.access_token_encrypted = encrypted_token

    for raw_account in raw_accounts:
        provider_account_id = str(raw_account.get("account_id") or "")
        if not provider_account_id:
            continue
        account = await session.scalar(
            select(FinancialAccount).where(
                FinancialAccount.connection_id == connection.id,
                FinancialAccount.provider_account_id == provider_account_id,
            )
        )
        values = _account_values(raw_account)
        if account is None:
            account = FinancialAccount(
                connection_id=connection.id,
                provider_account_id=provider_account_id,
                **values,
            )
            session.add(account)
        else:
            for name, value in values.items():
                setattr(account, name, value)

    await session.commit()
    return MoneyConnectionStatus(
        id=connection.id,
        provider=connection.provider,
        display_name=connection.display_name,
        status=connection.status,
        last_synced_at=connection.last_synced_at,
        account_count=len(raw_accounts),
        is_demo=False,
    )


@router.post("/{connection_id}/sync", response_model=MoneySyncResponse)
async def sync_plaid_connection(
    connection_id: UUID,
    session: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
    settings: Settings = Depends(get_app_settings),
) -> MoneySyncResponse:
    connection = await session.scalar(
        select(FinancialConnection).where(
            FinancialConnection.id == connection_id,
            FinancialConnection.user_id == user_id,
            FinancialConnection.provider == "plaid",
        )
    )
    if connection is None or connection.is_demo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Plaid connection not found"
        )

    credential = await session.scalar(
        select(FinancialCredential).where(FinancialCredential.connection_id == connection.id)
    )
    if credential is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Plaid connection has no stored credential",
        )

    client = _plaid_client(settings)
    try:
        access_token = TokenVault(settings.app_secret.get_secret_value()).decrypt(
            credential.access_token_encrypted
        )
        raw_accounts = await client.get_accounts(access_token)
        for raw_account in raw_accounts:
            provider_account_id = str(raw_account.get("account_id") or "")
            if not provider_account_id:
                continue
            account = await session.scalar(
                select(FinancialAccount).where(
                    FinancialAccount.connection_id == connection.id,
                    FinancialAccount.provider_account_id == provider_account_id,
                )
            )
            if account is None:
                account = FinancialAccount(
                    connection_id=connection.id,
                    provider_account_id=provider_account_id,
                    **_account_values(raw_account),
                )
                session.add(account)
            else:
                for name, value in _account_values(raw_account).items():
                    setattr(account, name, value)
        await session.flush()

        result = await sync_plaid_transactions(
            session,
            connection=connection,
            access_token=access_token,
            client=client,
        )
    except PlaidSyncError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Plaid transaction synchronization failed.",
        ) from exc

    return MoneySyncResponse(
        connection_id=connection.id,
        status="completed",
        inserted=result.inserted,
        updated=result.updated,
        deleted=result.deleted,
        unchanged=result.unchanged,
        replaced_pending=result.replaced_pending,
        normalized=result.normalized,
        rejected=result.rejected,
        synced_at=result.synced_at,
    )


@router.delete("/{connection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unlink_plaid_connection(
    connection_id: UUID,
    session: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
    settings: Settings = Depends(get_app_settings),
) -> Response:
    connection = await session.scalar(
        select(FinancialConnection).where(
            FinancialConnection.id == connection_id,
            FinancialConnection.user_id == user_id,
            FinancialConnection.provider == "plaid",
        )
    )
    if connection is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found")

    credential = await session.scalar(
        select(FinancialCredential).where(FinancialCredential.connection_id == connection.id)
    )
    access_token: str | None = None
    if credential is not None:
        access_token = TokenVault(settings.app_secret.get_secret_value()).decrypt(
            credential.access_token_encrypted
        )

    # Commit the read-only transaction before making any Plaid network call --
    # don't hold DB locks open while waiting on an external HTTP request.
    await session.commit()

    if access_token is not None:
        try:
            await _plaid_client(settings).remove_item(access_token)
        except Exception:  # noqa: BLE001 - local delete proceeds regardless
            logger.warning("plaid_item_remove_failed", connection_id=str(connection.id))

    await session.delete(connection)  # cascades accounts -> txns + balance snapshots + credential
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _plaid_client(settings: Settings) -> PlaidClient:
    if not settings.plaid_client_id or not settings.plaid_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Add Plaid Sandbox credentials before connecting an account.",
        )
    return PlaidClient(
        client_id=settings.plaid_client_id,
        secret=settings.plaid_secret,
        environment=settings.plaid_environment,
    )


def _decimal(value: object) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _account_values(raw: dict[str, Any]) -> dict[str, object]:
    plaid_type = str(raw.get("type") or "other")
    subtype = str(raw.get("subtype") or "") or None
    if plaid_type == "depository" and subtype in {"checking", "savings"}:
        account_type = subtype
    elif plaid_type == "credit":
        account_type = "credit_card"
    elif plaid_type == "loan":
        account_type = "loan"
    else:
        account_type = "other"
    balances = raw.get("balances") or {}
    current = _decimal(balances.get("current")) or Decimal("0")
    currency = balances.get("iso_currency_code") or balances.get("unofficial_currency_code")
    return {
        "display_name": str(raw.get("official_name") or raw.get("name") or "Account"),
        "mask": str(raw["mask"]) if raw.get("mask") else None,
        "account_type": account_type,
        "subtype": subtype,
        "currency": str(currency or "USD").upper(),
        "current_balance": current,
        "available_balance": _decimal(balances.get("available")),
        "credit_limit": _decimal(balances.get("limit")),
        "is_active": True,
    }
