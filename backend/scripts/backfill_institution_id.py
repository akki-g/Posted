"""Backfill institution_id on existing Plaid connections.

Existing FinancialConnection (provider="plaid") and BrokerageConnection
(provider="plaid_investments") rows predate the institution_id column and
have it set to NULL. The connection-dedup lookup added in
app/api/routes/plaid.py and app/api/routes/plaid_investments.py matches on
institution_id first, so a NULL row is invisible to that lookup and the
user's first post-deploy re-link creates a duplicate connection instead of
reusing the existing one.

This script looks up each institution_id from Plaid (via GET /item/get) and
writes it back. It is idempotent: only rows still NULL are touched, so it is
safe to re-run (e.g. after a partial failure).

Usage: uv run python scripts/backfill_institution_id.py   (from backend/)
Never prints tokens or secrets.
"""

import asyncio
import sys

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

sys.path.insert(0, ".")
from app.config import get_settings  # noqa: E402
from app.db.models import (  # noqa: E402
    BrokerageConnection,
    BrokerageCredential,
    FinancialConnection,
    FinancialCredential,
)
from app.db.session import create_engine, create_session_factory  # noqa: E402
from app.providers.plaid.client import PlaidClient  # noqa: E402
from app.security.brokerage_credentials import BrokerageCredentialStore  # noqa: E402
from app.security.vault import TokenVault  # noqa: E402

logger = structlog.get_logger()


async def _lookup_institution_id(client: PlaidClient, access_token: str) -> str | None:
    item = await client.get_item(access_token)
    return item.get("institution_id")


async def backfill_financial_connections(
    session: AsyncSession, client: PlaidClient, vault: TokenVault
) -> tuple[int, int]:
    updated = 0
    skipped = 0
    connections = (
        await session.scalars(
            select(FinancialConnection).where(
                FinancialConnection.provider == "plaid",
                FinancialConnection.institution_id.is_(None),
            )
        )
    ).all()
    for connection in connections:
        credential = await session.scalar(
            select(FinancialCredential).where(
                FinancialCredential.connection_id == connection.id
            )
        )
        if credential is None:
            logger.warning(
                "backfill_financial_no_credential", connection_id=str(connection.id)
            )
            skipped += 1
            continue
        try:
            access_token = vault.decrypt(credential.access_token_encrypted)
            institution_id = await _lookup_institution_id(client, access_token)
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            logger.warning(
                "backfill_financial_failed",
                connection_id=str(connection.id),
                error=str(exc),
            )
            skipped += 1
            continue
        if not institution_id:
            skipped += 1
            continue
        connection.institution_id = institution_id
        updated += 1
    await session.commit()
    return updated, skipped


async def backfill_brokerage_connections(
    session: AsyncSession, client: PlaidClient, vault: TokenVault
) -> tuple[int, int]:
    updated = 0
    skipped = 0
    store = BrokerageCredentialStore(session=session, vault=vault)
    connections = (
        await session.scalars(
            select(BrokerageConnection).where(
                BrokerageConnection.provider == "plaid_investments",
                BrokerageConnection.institution_id.is_(None),
            )
        )
    ).all()
    for connection in connections:
        credential = await session.scalar(
            select(BrokerageCredential).where(
                BrokerageCredential.connection_id == connection.id
            )
        )
        if credential is None:
            logger.warning(
                "backfill_brokerage_no_credential", connection_id=str(connection.id)
            )
            skipped += 1
            continue
        try:
            stored = await store.load(connection_id=connection.id)
            if stored is None:
                skipped += 1
                continue
            institution_id = await _lookup_institution_id(client, stored.access_token)
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            logger.warning(
                "backfill_brokerage_failed",
                connection_id=str(connection.id),
                error=str(exc),
            )
            skipped += 1
            continue
        if not institution_id:
            skipped += 1
            continue
        connection.institution_id = institution_id
        updated += 1
    await session.commit()
    return updated, skipped


async def main() -> None:
    settings = get_settings()
    if not settings.plaid_configured:
        print("[Plaid] SKIP -> PLAID_CLIENT_ID / PLAID_SECRET not set")
        return

    client = PlaidClient(
        client_id=settings.plaid_client_id,
        secret=settings.plaid_secret,
        environment=settings.plaid_environment,
    )
    vault = TokenVault(settings.app_secret.get_secret_value())
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)

    async with session_factory() as session:
        fin_updated, fin_skipped = await backfill_financial_connections(session, client, vault)
        brk_updated, brk_skipped = await backfill_brokerage_connections(session, client, vault)

    await engine.dispose()

    print(
        f"[financial_connections]  updated={fin_updated} skipped={fin_skipped}"
    )
    print(
        f"[brokerage_connections]  updated={brk_updated} skipped={brk_skipped}"
    )


if __name__ == "__main__":
    asyncio.run(main())
