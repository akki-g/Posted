from datetime import UTC, datetime

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import BrokerageConnection
from app.providers.plaid.client import PlaidClient
from app.providers.plaid_investments.mapper import map_plaid_investment_accounts
from app.security.brokerage_credentials import BrokerageCredentialStore
from app.services.brokerage_sync import (
    BrokerageSyncError,
    BrokerageSyncSummary,
    prior_summary,
    record_failed_run,
    sync_brokerage_snapshot,
)


class PlaidInvestmentsSyncError(BrokerageSyncError):
    """A safe, user-readable Plaid Investments failure that keeps the prior portfolio."""


async def sync_plaid_investments_connection(
    session: AsyncSession,
    *,
    connection: BrokerageConnection,
    idempotency_key: str,
    credential_store: BrokerageCredentialStore,
    client: PlaidClient,
    as_of: datetime | None = None,
) -> BrokerageSyncSummary:
    if as_of is not None and (as_of.tzinfo is None or as_of.utcoffset() is None):
        raise PlaidInvestmentsSyncError("as_of must be timezone-aware")
    as_of = (as_of or datetime.now(UTC)).astimezone(UTC)
    prior = await prior_summary(
        session, connection_id=connection.id, idempotency_key=idempotency_key.strip()
    )
    if prior is not None:
        return prior
    try:
        stored = await credential_store.load(connection_id=connection.id)
        # End the implicit read transaction before the provider request.
        await session.commit()
        if stored is None:
            raise PlaidInvestmentsSyncError("Reconnect this brokerage before synchronizing")
        payload = await client.get_investment_holdings(stored.access_token)
        accounts = map_plaid_investment_accounts(payload, observed_at=as_of)
    except PlaidInvestmentsSyncError as exc:
        await record_failed_run(
            session, connection=connection, idempotency_key=idempotency_key,
            message=str(exc), as_of=datetime.now(UTC),
        )
        raise
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        await record_failed_run(
            session, connection=connection, idempotency_key=idempotency_key,
            message="Plaid investment synchronization failed", as_of=datetime.now(UTC),
        )
        raise PlaidInvestmentsSyncError(
            "Plaid investment synchronization failed; the prior portfolio was kept"
        ) from exc
    return await sync_brokerage_snapshot(
        session, connection=connection, idempotency_key=idempotency_key,
        accounts=list(accounts), as_of=as_of,
    )
