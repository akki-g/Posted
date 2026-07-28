from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from sqlalchemy import select

from app.config import Settings
from app.db.base import Base
from app.db.models import BrokerageConnection, FinancialConnection, FinancialCredential, User
from app.db.session import create_engine, create_session_factory
from app.security.vault import TokenVault
from app.services import connection_sync


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "database_url": "sqlite+aiosqlite:///:memory:",
        "app_secret": "test-vault-key",
        "plaid_client_id": "sandbox-client-id",
        "plaid_secret": "sandbox-secret",
        "plaid_environment": "sandbox",
    }
    values.update(overrides)
    return Settings(**values)


def test_is_stale_treats_never_synced_as_stale() -> None:
    assert connection_sync.is_stale(None) is True


def test_is_stale_is_false_within_the_threshold() -> None:
    now = datetime(2026, 7, 28, 12, 0, tzinfo=UTC)
    last_synced_at = now - timedelta(minutes=1)

    assert connection_sync.is_stale(last_synced_at, now=now) is False


def test_is_stale_is_true_past_the_threshold() -> None:
    now = datetime(2026, 7, 28, 12, 0, tzinfo=UTC)
    last_synced_at = now - timedelta(minutes=6)

    assert connection_sync.is_stale(last_synced_at, now=now) is True


def test_is_stale_treats_naive_datetimes_as_utc() -> None:
    now = datetime(2026, 7, 28, 12, 0, tzinfo=UTC)
    last_synced_at = (now - timedelta(minutes=1)).replace(tzinfo=None)

    assert connection_sync.is_stale(last_synced_at, now=now) is False


async def _make_session_factory():
    settings = _settings()
    engine = create_engine(settings)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return engine, create_session_factory(engine)


async def test_sync_stale_brokerage_connections_calls_adapter_when_stale() -> None:
    engine, session_factory = await _make_session_factory()
    settings = _settings()
    user_id = uuid4()
    stale_at = datetime.now(UTC) - timedelta(minutes=30)

    async with session_factory() as session:
        session.add(User(id=user_id, email="stale-brokerage@test.local", display_name="Stale"))
        session.add(
            BrokerageConnection(
                user_id=user_id,
                provider="fake_broker",
                display_name="Fake Broker",
                status="connected",
                last_synced_at=stale_at,
            )
        )
        await session.commit()

        fake_adapter = AsyncMock()
        with patch.dict(connection_sync.BROKERAGE_SYNC_ADAPTERS, {"fake_broker": fake_adapter}):
            await connection_sync.sync_stale_brokerage_connections(
                session, user_id=user_id, settings=settings
            )

        fake_adapter.assert_awaited_once()

    await engine.dispose()


async def test_sync_stale_brokerage_connections_skips_fresh_connections() -> None:
    engine, session_factory = await _make_session_factory()
    settings = _settings()
    user_id = uuid4()

    async with session_factory() as session:
        session.add(User(id=user_id, email="fresh-brokerage@test.local", display_name="Fresh"))
        session.add(
            BrokerageConnection(
                user_id=user_id,
                provider="fake_broker",
                display_name="Fake Broker",
                status="connected",
                last_synced_at=datetime.now(UTC),
            )
        )
        await session.commit()

        fake_adapter = AsyncMock()
        with patch.dict(connection_sync.BROKERAGE_SYNC_ADAPTERS, {"fake_broker": fake_adapter}):
            await connection_sync.sync_stale_brokerage_connections(
                session, user_id=user_id, settings=settings
            )

        fake_adapter.assert_not_awaited()

    await engine.dispose()


async def test_sync_stale_brokerage_connections_skips_demo_connections() -> None:
    engine, session_factory = await _make_session_factory()
    settings = _settings()
    user_id = uuid4()

    async with session_factory() as session:
        session.add(User(id=user_id, email="demo-brokerage@test.local", display_name="Demo"))
        session.add(
            BrokerageConnection(
                user_id=user_id,
                provider="fake_broker",
                display_name="Fake Broker",
                status="demo",
                last_synced_at=None,
            )
        )
        await session.commit()

        fake_adapter = AsyncMock()
        with patch.dict(connection_sync.BROKERAGE_SYNC_ADAPTERS, {"fake_broker": fake_adapter}):
            await connection_sync.sync_stale_brokerage_connections(
                session, user_id=user_id, settings=settings
            )

        fake_adapter.assert_not_awaited()

    await engine.dispose()


async def test_sync_stale_brokerage_connections_ignores_unsupported_providers() -> None:
    engine, session_factory = await _make_session_factory()
    settings = _settings()
    user_id = uuid4()

    async with session_factory() as session:
        session.add(User(id=user_id, email="unsupported@test.local", display_name="Unsupported"))
        session.add(
            BrokerageConnection(
                user_id=user_id,
                provider="robinhood",
                display_name="Robinhood",
                status="connected",
                last_synced_at=None,
            )
        )
        await session.commit()

        # Must not raise even though "robinhood" has no registered adapter.
        await connection_sync.sync_stale_brokerage_connections(
            session, user_id=user_id, settings=settings
        )

    await engine.dispose()


async def test_sync_stale_brokerage_connections_rolls_back_after_adapter_error() -> None:
    engine, session_factory = await _make_session_factory()
    settings = _settings()
    user_id = uuid4()

    async with session_factory() as session:
        session.add(User(id=user_id, email="rollback-brokerage@test.local", display_name="RB"))
        session.add(
            BrokerageConnection(
                user_id=user_id,
                provider="fake_broker",
                display_name="Fake Broker",
                status="connected",
                last_synced_at=None,
            )
        )
        await session.commit()

        fake_adapter = AsyncMock(side_effect=RuntimeError("provider unreachable"))
        with (
            patch.dict(connection_sync.BROKERAGE_SYNC_ADAPTERS, {"fake_broker": fake_adapter}),
            patch.object(
                session, "rollback", new=AsyncMock(wraps=session.rollback)
            ) as rollback_mock,
        ):
            await connection_sync.sync_stale_brokerage_connections(
                session, user_id=user_id, settings=settings
            )

        rollback_mock.assert_awaited_once()
        # The session must still be usable for the read the sync was meant to protect.
        assert (await session.scalars(select(BrokerageConnection))).one()

    await engine.dispose()


async def test_sync_stale_brokerage_connections_swallows_adapter_errors() -> None:
    engine, session_factory = await _make_session_factory()
    settings = _settings()
    user_id = uuid4()

    async with session_factory() as session:
        session.add(User(id=user_id, email="broken-brokerage@test.local", display_name="Broken"))
        session.add(
            BrokerageConnection(
                user_id=user_id,
                provider="fake_broker",
                display_name="Fake Broker",
                status="connected",
                last_synced_at=None,
            )
        )
        await session.commit()

        fake_adapter = AsyncMock(side_effect=RuntimeError("provider unreachable"))
        with patch.dict(connection_sync.BROKERAGE_SYNC_ADAPTERS, {"fake_broker": fake_adapter}):
            # Must not raise -- a failed background sync must not block the read.
            await connection_sync.sync_stale_brokerage_connections(
                session, user_id=user_id, settings=settings
            )

        fake_adapter.assert_awaited_once()

    await engine.dispose()


async def test_sync_stale_money_connections_calls_sync_when_stale() -> None:
    engine, session_factory = await _make_session_factory()
    settings = _settings()
    user_id = uuid4()
    stale_at = datetime.now(UTC) - timedelta(minutes=30)

    async with session_factory() as session:
        session.add(User(id=user_id, email="stale-money@test.local", display_name="Stale Money"))
        connection = FinancialConnection(
            user_id=user_id,
            provider="plaid",
            provider_item_id="item-stale",
            display_name="Sandbox bank",
            status="connected",
            is_demo=False,
            last_synced_at=stale_at,
        )
        session.add(connection)
        await session.flush()
        session.add(
            FinancialCredential(
                connection_id=connection.id,
                access_token_encrypted=TokenVault("test-vault-key").encrypt("access-sandbox"),
            )
        )
        await session.commit()

        with patch(
            "app.services.connection_sync.sync_plaid_money_connection", new=AsyncMock()
        ) as sync_fn:
            await connection_sync.sync_stale_money_connections(
                session, user_id=user_id, settings=settings
            )

        sync_fn.assert_awaited_once()
        assert sync_fn.await_args.kwargs["access_token"] == "access-sandbox"

    await engine.dispose()


async def test_sync_stale_money_connections_skips_fresh_connections() -> None:
    engine, session_factory = await _make_session_factory()
    settings = _settings()
    user_id = uuid4()

    async with session_factory() as session:
        session.add(User(id=user_id, email="fresh-money@test.local", display_name="Fresh Money"))
        connection = FinancialConnection(
            user_id=user_id,
            provider="plaid",
            provider_item_id="item-fresh",
            display_name="Sandbox bank",
            status="connected",
            is_demo=False,
            last_synced_at=datetime.now(UTC),
        )
        session.add(connection)
        await session.flush()
        session.add(
            FinancialCredential(
                connection_id=connection.id,
                access_token_encrypted=TokenVault("test-vault-key").encrypt("access-sandbox"),
            )
        )
        await session.commit()

        with patch(
            "app.services.connection_sync.sync_plaid_money_connection", new=AsyncMock()
        ) as sync_fn:
            await connection_sync.sync_stale_money_connections(
                session, user_id=user_id, settings=settings
            )

        sync_fn.assert_not_awaited()

    await engine.dispose()


async def test_sync_stale_money_connections_skips_demo_connections() -> None:
    engine, session_factory = await _make_session_factory()
    settings = _settings()
    user_id = uuid4()

    async with session_factory() as session:
        session.add(User(id=user_id, email="demo-money@test.local", display_name="Demo Money"))
        session.add(
            FinancialConnection(
                user_id=user_id,
                provider="plaid",
                provider_item_id="item-demo",
                display_name="Demo bank",
                status="demo",
                is_demo=True,
                last_synced_at=None,
            )
        )
        await session.commit()

        with patch(
            "app.services.connection_sync.sync_plaid_money_connection", new=AsyncMock()
        ) as sync_fn:
            await connection_sync.sync_stale_money_connections(
                session, user_id=user_id, settings=settings
            )

        sync_fn.assert_not_awaited()

    await engine.dispose()


async def test_sync_stale_money_connections_skips_when_credential_missing() -> None:
    engine, session_factory = await _make_session_factory()
    settings = _settings()
    user_id = uuid4()

    async with session_factory() as session:
        session.add(
            User(id=user_id, email="no-credential-money@test.local", display_name="No Cred")
        )
        session.add(
            FinancialConnection(
                user_id=user_id,
                provider="plaid",
                provider_item_id="item-no-cred",
                display_name="Sandbox bank",
                status="connected",
                is_demo=False,
                last_synced_at=None,
            )
        )
        await session.commit()

        with patch(
            "app.services.connection_sync.sync_plaid_money_connection", new=AsyncMock()
        ) as sync_fn:
            # Must not raise even though there's no stored credential to sync with.
            await connection_sync.sync_stale_money_connections(
                session, user_id=user_id, settings=settings
            )

        sync_fn.assert_not_awaited()

    await engine.dispose()


async def test_sync_stale_money_connections_rolls_back_after_sync_error() -> None:
    engine, session_factory = await _make_session_factory()
    settings = _settings()
    user_id = uuid4()

    async with session_factory() as session:
        session.add(User(id=user_id, email="rollback-money@test.local", display_name="RB"))
        connection = FinancialConnection(
            user_id=user_id,
            provider="plaid",
            provider_item_id="item-rollback",
            display_name="Sandbox bank",
            status="connected",
            is_demo=False,
            last_synced_at=None,
        )
        session.add(connection)
        await session.flush()
        session.add(
            FinancialCredential(
                connection_id=connection.id,
                access_token_encrypted=TokenVault("test-vault-key").encrypt("access-sandbox"),
            )
        )
        await session.commit()

        with (
            patch(
                "app.services.connection_sync.sync_plaid_money_connection",
                new=AsyncMock(side_effect=RuntimeError("provider unreachable")),
            ),
            patch.object(
                session, "rollback", new=AsyncMock(wraps=session.rollback)
            ) as rollback_mock,
        ):
            await connection_sync.sync_stale_money_connections(
                session, user_id=user_id, settings=settings
            )

        rollback_mock.assert_awaited_once()
        # The session must still be usable for the read the sync was meant to protect.
        assert (await session.scalars(select(FinancialConnection))).one()

    await engine.dispose()


async def test_sync_stale_money_connections_recovers_for_a_later_connection_after_rollback() -> (
    None
):
    engine, session_factory = await _make_session_factory()
    settings = _settings()
    user_id = uuid4()
    stale_at = datetime.now(UTC) - timedelta(minutes=30)

    async with session_factory() as session:
        session.add(User(id=user_id, email="multi-money@test.local", display_name="Multi"))
        broken = FinancialConnection(
            user_id=user_id,
            provider="plaid",
            provider_item_id="item-broken",
            display_name="Broken bank",
            status="connected",
            is_demo=False,
            last_synced_at=stale_at,
        )
        healthy = FinancialConnection(
            user_id=user_id,
            provider="plaid",
            provider_item_id="item-healthy",
            display_name="Healthy bank",
            status="connected",
            is_demo=False,
            last_synced_at=stale_at,
        )
        session.add_all((broken, healthy))
        await session.flush()
        for connection in (broken, healthy):
            session.add(
                FinancialCredential(
                    connection_id=connection.id,
                    access_token_encrypted=TokenVault("test-vault-key").encrypt(
                        f"access-{connection.provider_item_id}"
                    ),
                )
            )
        await session.commit()

        sync_fn = AsyncMock(
            side_effect=[RuntimeError("provider unreachable"), None],
        )
        with patch("app.services.connection_sync.sync_plaid_money_connection", new=sync_fn):
            await connection_sync.sync_stale_money_connections(
                session, user_id=user_id, settings=settings
            )

        assert sync_fn.await_count == 2

    await engine.dispose()


async def test_sync_stale_money_connections_swallows_sync_errors() -> None:
    engine, session_factory = await _make_session_factory()
    settings = _settings()
    user_id = uuid4()

    async with session_factory() as session:
        session.add(User(id=user_id, email="broken-money@test.local", display_name="Broken"))
        connection = FinancialConnection(
            user_id=user_id,
            provider="plaid",
            provider_item_id="item-broken",
            display_name="Sandbox bank",
            status="connected",
            is_demo=False,
            last_synced_at=None,
        )
        session.add(connection)
        await session.flush()
        session.add(
            FinancialCredential(
                connection_id=connection.id,
                access_token_encrypted=TokenVault("test-vault-key").encrypt("access-sandbox"),
            )
        )
        await session.commit()

        with patch(
            "app.services.connection_sync.sync_plaid_money_connection",
            new=AsyncMock(side_effect=RuntimeError("provider unreachable")),
        ) as sync_fn:
            # Must not raise -- a failed background sync must not block the read.
            await connection_sync.sync_stale_money_connections(
                session, user_id=user_id, settings=settings
            )

        sync_fn.assert_awaited_once()

    await engine.dispose()
