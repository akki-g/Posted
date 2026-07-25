from datetime import UTC, datetime
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import func, select

from app.config import Settings
from app.db.base import Base
from app.db.models import BrokerageConnection, Position, SyncRun, User
from app.db.session import create_engine, create_session_factory
from app.security.brokerage_credentials import BrokerageCredentialStore
from app.security.vault import TokenVault
from app.services.plaid_investments_sync import (
    PlaidInvestmentsSyncError,
    sync_plaid_investments_connection,
)

NOW = datetime(2026, 7, 25, 15, tzinfo=UTC)
HOLDINGS = {
    "accounts": [{"account_id": "acc-1", "name": "Robinhood", "type": "investment",
                  "balances": {"current": 9500.0}}],
    "securities": [
        {"security_id": "s1", "ticker_symbol": "AAPL", "name": "Apple", "type": "equity"}
    ],
    "holdings": [{"account_id": "acc-1", "security_id": "s1", "quantity": 50,
                  "institution_price": 190.0, "institution_value": 9500.0, "cost_basis": 8000.0}],
}


class FakePlaidClient:
    def __init__(self) -> None:
        self.calls = 0

    async def get_investment_holdings(self, access_token: str) -> dict:
        assert access_token == "plaid-access"
        self.calls += 1
        return HOLDINGS


async def _factory():
    engine = create_engine(Settings(database_url="sqlite+aiosqlite:///:memory:", app_secret="k"))
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return engine, create_session_factory(engine)


async def test_sync_persists_plaid_investment_holdings() -> None:
    engine, session_factory = await _factory()
    user_id, connection_id = uuid4(), uuid4()
    async with session_factory() as session:
        session.add(User(id=user_id, email="p@example.com", display_name="P"))
        session.add(BrokerageConnection(
            id=connection_id, user_id=user_id, provider="plaid_investments",
            display_name="Robinhood", status="connected"))
        store = BrokerageCredentialStore(session=session, vault=TokenVault("k"))
        await session.flush()
        await store.save(connection_id=connection_id, access_token="plaid-access")
        await session.commit()

    client = FakePlaidClient()
    async with session_factory() as session:
        connection = await session.get(BrokerageConnection, connection_id)
        store = BrokerageCredentialStore(session=session, vault=TokenVault("k"))
        summary = await sync_plaid_investments_connection(
            session, connection=connection, idempotency_key="pi-00000001",
            credential_store=store, client=client, as_of=NOW)
    assert summary.status == "completed"
    assert summary.positions_seen == 1
    async with session_factory() as session:
        assert (await session.scalar(select(func.count()).select_from(Position))) == 1
    await engine.dispose()


async def test_replay_is_idempotent_and_does_not_refetch() -> None:
    # Regression coverage: a second call with the same idempotency_key must
    # return the recorded summary without calling back out to Plaid, and
    # must not create a second SyncRun row.
    engine, session_factory = await _factory()
    user_id, connection_id = uuid4(), uuid4()
    async with session_factory() as session:
        session.add(User(id=user_id, email="replay@example.com", display_name="Replay"))
        session.add(BrokerageConnection(
            id=connection_id, user_id=user_id, provider="plaid_investments",
            display_name="Robinhood", status="connected"))
        store = BrokerageCredentialStore(session=session, vault=TokenVault("k"))
        await session.flush()
        await store.save(connection_id=connection_id, access_token="plaid-access")
        await session.commit()

    client = FakePlaidClient()
    async with session_factory() as session:
        connection = await session.get(BrokerageConnection, connection_id)
        store = BrokerageCredentialStore(session=session, vault=TokenVault("k"))
        first = await sync_plaid_investments_connection(
            session, connection=connection, idempotency_key="pi-repeat01",
            credential_store=store, client=client, as_of=NOW)
    assert first.repeated is False

    async with session_factory() as session:
        connection = await session.get(BrokerageConnection, connection_id)
        store = BrokerageCredentialStore(session=session, vault=TokenVault("k"))
        second = await sync_plaid_investments_connection(
            session, connection=connection, idempotency_key="pi-repeat01",
            credential_store=store, client=client, as_of=NOW)
    assert second.repeated is True
    assert client.calls == 1

    async with session_factory() as session:
        assert (await session.scalar(select(func.count()).select_from(SyncRun))) == 1
    await engine.dispose()


async def test_missing_credential_raises_and_records_failed_run() -> None:
    engine, session_factory = await _factory()
    user_id, connection_id = uuid4(), uuid4()
    async with session_factory() as session:
        session.add(User(id=user_id, email="nocred@example.com", display_name="NoCred"))
        session.add(BrokerageConnection(
            id=connection_id, user_id=user_id, provider="plaid_investments",
            display_name="Robinhood", status="connected"))
        await session.commit()
        # No BrokerageCredential saved for this connection.

    class _UnexpectedClient:
        async def get_investment_holdings(self, access_token: str) -> dict:
            raise AssertionError("provider must not be fetched without stored credentials")

    async with session_factory() as session:
        connection = await session.get(BrokerageConnection, connection_id)
        store = BrokerageCredentialStore(session=session, vault=TokenVault("k"))
        with pytest.raises(PlaidInvestmentsSyncError, match="Reconnect this brokerage"):
            await sync_plaid_investments_connection(
                session, connection=connection, idempotency_key="pi-missing1",
                credential_store=store, client=_UnexpectedClient(), as_of=NOW)

    async with session_factory() as session:
        run = await session.scalar(select(SyncRun))
        assert run is not None
        assert run.status == "failed"
        connection = await session.get(BrokerageConnection, connection_id)
        assert connection is not None
        assert connection.status == "error"
    await engine.dispose()


async def test_provider_failure_raises_safe_error_and_records_failed_run() -> None:
    engine, session_factory = await _factory()
    user_id, connection_id = uuid4(), uuid4()
    async with session_factory() as session:
        session.add(User(id=user_id, email="providerfail@example.com", display_name="Fail"))
        session.add(BrokerageConnection(
            id=connection_id, user_id=user_id, provider="plaid_investments",
            display_name="Robinhood", status="connected"))
        store = BrokerageCredentialStore(session=session, vault=TokenVault("k"))
        await session.flush()
        await store.save(connection_id=connection_id, access_token="plaid-access")
        await session.commit()

    class _FailingClient:
        async def get_investment_holdings(self, access_token: str) -> dict:
            raise httpx.HTTPError("Plaid is unavailable")

    async with session_factory() as session:
        connection = await session.get(BrokerageConnection, connection_id)
        store = BrokerageCredentialStore(session=session, vault=TokenVault("k"))
        with pytest.raises(PlaidInvestmentsSyncError, match="the prior portfolio was kept"):
            await sync_plaid_investments_connection(
                session, connection=connection, idempotency_key="pi-provfail",
                credential_store=store, client=_FailingClient(), as_of=NOW)

    async with session_factory() as session:
        run = await session.scalar(select(SyncRun))
        assert run is not None
        assert run.status == "failed"
        connection = await session.get(BrokerageConnection, connection_id)
        assert connection is not None
        assert connection.status == "error"
    await engine.dispose()


async def test_naive_as_of_raises_before_any_provider_fetch() -> None:
    # Regression coverage: sync_plaid_investments_connection must fail fast
    # on a naive (tz-unaware) as_of instead of silently treating it as local
    # time and converting it -- and it must do so before any credential
    # lookup or provider call, not merely inside sync_brokerage_snapshot
    # after the network round trip.
    engine, session_factory = await _factory()
    user_id, connection_id = uuid4(), uuid4()
    async with session_factory() as session:
        session.add(User(id=user_id, email="naive@example.com", display_name="Naive"))
        session.add(BrokerageConnection(
            id=connection_id, user_id=user_id, provider="plaid_investments",
            display_name="Robinhood", status="connected"))
        await session.commit()

    class _UnexpectedClient:
        async def get_investment_holdings(self, access_token: str) -> dict:
            raise AssertionError("provider must not be fetched for a naive as_of")

    async with session_factory() as session:
        connection = await session.get(BrokerageConnection, connection_id)
        store = BrokerageCredentialStore(session=session, vault=TokenVault("k"))
        with pytest.raises(PlaidInvestmentsSyncError, match="as_of must be timezone-aware"):
            await sync_plaid_investments_connection(
                session, connection=connection, idempotency_key="pi-naive001",
                credential_store=store, client=_UnexpectedClient(),
                as_of=datetime(2026, 7, 25, 15),  # naive: no tzinfo
            )

        # No SyncRun (successful or failed) should have been recorded --
        # the guard must fire before record_failed_run's provider-error path.
        assert await session.scalar(select(func.count(SyncRun.id))) == 0

    await engine.dispose()
