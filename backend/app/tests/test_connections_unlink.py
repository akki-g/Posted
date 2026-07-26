from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select

from app.api.routes.connections import unlink_connection
from app.config import Settings
from app.db.base import Base
from app.db.models import (
    BrokerageAccount,
    BrokerageConnection,
    BrokerageCredential,
    Position,
    Security,
    SyncRun,
    User,
)
from app.db.session import create_engine, create_session_factory
from app.security.brokerage_credentials import BrokerageCredentialStore
from app.security.vault import TokenVault

NOW = datetime(2026, 7, 25, 15, tzinfo=UTC)


async def _factory():
    settings = Settings(
        app_env="test",
        database_url="sqlite+aiosqlite:///:memory:",
        demo_mode=False,
        app_secret="test-vault-key",
    )
    engine = create_engine(settings)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return settings, engine, create_session_factory(engine)


async def _seed_schwab_connection_with_sync_run(session_factory, *, user_id, connection_id):
    async with session_factory() as session:
        session.add(User(id=user_id, email="schwab@test.local", display_name="Schwab User"))
        connection = BrokerageConnection(
            id=connection_id,
            user_id=user_id,
            provider="schwab",
            display_name="Charles Schwab",
            status="connected",
        )
        session.add(connection)
        security = Security(symbol="AAPL", name="Apple", asset_type="equity")
        session.add(security)
        await session.flush()
        account = BrokerageAccount(
            connection_id=connection_id,
            provider_account_id="acc-1",
            display_name="Brokerage",
            account_type="brokerage",
            balance=1000,
        )
        session.add(account)
        await session.flush()
        session.add(
            Position(
                account_id=account.id,
                security_id=security.id,
                quantity=10,
                market_value=1000,
            )
        )
        session.add(
            SyncRun(
                connection_id=connection_id,
                status="completed",
                idempotency_key="schwab-0001",
                trigger="manual",
                started_at=NOW,
                completed_at=NOW,
            )
        )
        await session.commit()


class FakePlaidClient:
    def __init__(self) -> None:
        self.remove_item_calls: list[str] = []

    async def remove_item(self, access_token: str) -> None:
        self.remove_item_calls.append(access_token)


async def test_unlink_schwab_connection_deletes_sync_runs_accounts_and_positions_without_plaid_call(
    monkeypatch,
) -> None:
    settings, engine, session_factory = await _factory()
    user_id, connection_id = uuid4(), uuid4()
    await _seed_schwab_connection_with_sync_run(
        session_factory, user_id=user_id, connection_id=connection_id
    )

    fake_plaid = FakePlaidClient()
    monkeypatch.setattr(
        "app.api.routes.connections._plaid_client", lambda _settings: fake_plaid
    )

    async with session_factory() as session:
        response = await unlink_connection(
            connection_id=connection_id,
            session=session,
            user_id=user_id,
            settings=settings,
        )
    assert response.status_code == 204
    assert fake_plaid.remove_item_calls == []

    async with session_factory() as session:
        assert (
            await session.scalar(
                select(func.count()).select_from(BrokerageConnection)
            )
        ) == 0
        assert (await session.scalar(select(func.count()).select_from(BrokerageAccount))) == 0
        assert (await session.scalar(select(func.count()).select_from(Position))) == 0
        assert (await session.scalar(select(func.count()).select_from(SyncRun))) == 0
    await engine.dispose()


async def test_unlink_plaid_investments_connection_calls_remove_item_and_removes_it(
    monkeypatch,
) -> None:
    settings, engine, session_factory = await _factory()
    user_id, connection_id = uuid4(), uuid4()
    async with session_factory() as session:
        session.add(User(id=user_id, email="plaid-inv@test.local", display_name="Plaid Investor"))
        session.add(
            BrokerageConnection(
                id=connection_id,
                user_id=user_id,
                provider="plaid_investments",
                display_name="Plaid Brokerage",
                status="connected",
            )
        )
        await session.flush()
        store = BrokerageCredentialStore(
            session=session, vault=TokenVault(settings.app_secret.get_secret_value())
        )
        await store.save(connection_id=connection_id, access_token="plaid-access-token")
        await session.commit()

    fake_plaid = FakePlaidClient()
    monkeypatch.setattr(
        "app.api.routes.connections._plaid_client", lambda _settings: fake_plaid
    )

    async with session_factory() as session:
        response = await unlink_connection(
            connection_id=connection_id,
            session=session,
            user_id=user_id,
            settings=settings,
        )
    assert response.status_code == 204
    assert fake_plaid.remove_item_calls == ["plaid-access-token"]

    async with session_factory() as session:
        assert (
            await session.scalar(
                select(func.count()).select_from(BrokerageConnection)
            )
        ) == 0
        # Regression: BrokerageConnection has no ORM relationship to
        # BrokerageCredential, and the DB-level ON DELETE CASCADE on that FK
        # is not enforced by SQLite -- the encrypted token row must be
        # deleted explicitly by the handler, or it's orphaned after unlink.
        assert (
            await session.scalar(
                select(func.count()).select_from(BrokerageCredential).where(
                    BrokerageCredential.connection_id == connection_id
                )
            )
        ) == 0
    await engine.dispose()


async def test_unlink_plaid_investments_still_deletes_locally_when_remove_item_fails(
    monkeypatch,
) -> None:
    # remove_item is best-effort: a Plaid-side failure must not block the
    # local unlink.
    settings, engine, session_factory = await _factory()
    user_id, connection_id = uuid4(), uuid4()
    async with session_factory() as session:
        session.add(User(id=user_id, email="plaid-inv2@test.local", display_name="Plaid Investor"))
        session.add(
            BrokerageConnection(
                id=connection_id,
                user_id=user_id,
                provider="plaid_investments",
                display_name="Plaid Brokerage",
                status="connected",
            )
        )
        await session.flush()
        store = BrokerageCredentialStore(
            session=session, vault=TokenVault(settings.app_secret.get_secret_value())
        )
        await store.save(connection_id=connection_id, access_token="plaid-access-token")
        await session.commit()

    class ExplodingPlaidClient:
        async def remove_item(self, access_token: str) -> None:
            raise RuntimeError("plaid is down")

    monkeypatch.setattr(
        "app.api.routes.connections._plaid_client", lambda _settings: ExplodingPlaidClient()
    )

    async with session_factory() as session:
        response = await unlink_connection(
            connection_id=connection_id,
            session=session,
            user_id=user_id,
            settings=settings,
        )
    assert response.status_code == 204

    async with session_factory() as session:
        assert (
            await session.scalar(
                select(func.count()).select_from(BrokerageConnection)
            )
        ) == 0
    await engine.dispose()


async def test_unlink_rejects_other_users_connection_with_404() -> None:
    settings, engine, session_factory = await _factory()
    owner_id, other_user_id, connection_id = uuid4(), uuid4(), uuid4()
    async with session_factory() as session:
        session.add(User(id=owner_id, email="owner@test.local", display_name="Owner"))
        session.add(User(id=other_user_id, email="other@test.local", display_name="Other"))
        session.add(
            BrokerageConnection(
                id=connection_id,
                user_id=owner_id,
                provider="schwab",
                display_name="Charles Schwab",
                status="connected",
            )
        )
        await session.commit()

    async with session_factory() as session:
        with pytest.raises(HTTPException) as exc_info:
            await unlink_connection(
                connection_id=connection_id,
                session=session,
                user_id=other_user_id,
                settings=settings,
            )
        assert exc_info.value.status_code == 404

    async with session_factory() as session:
        assert (
            await session.scalar(
                select(func.count()).select_from(BrokerageConnection)
            )
        ) == 1
    await engine.dispose()


async def test_unlink_unknown_connection_id_returns_404() -> None:
    settings, engine, session_factory = await _factory()
    user_id = uuid4()
    async with session_factory() as session:
        session.add(User(id=user_id, email="lonely@test.local", display_name="Lonely"))
        await session.commit()

    async with session_factory() as session:
        with pytest.raises(HTTPException) as exc_info:
            await unlink_connection(
                connection_id=uuid4(),
                session=session,
                user_id=user_id,
                settings=settings,
            )
        assert exc_info.value.status_code == 404
    await engine.dispose()
