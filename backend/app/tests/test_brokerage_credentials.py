from datetime import UTC, datetime
from uuid import uuid4

from app.config import Settings
from app.db.base import Base
from app.db.models import BrokerageConnection, User
from app.db.session import create_engine, create_session_factory
from app.security.brokerage_credentials import BrokerageCredentialStore
from app.security.vault import TokenVault

NOW = datetime(2026, 7, 25, 12, tzinfo=UTC)


async def _make_connection_session():
    settings = Settings(
        app_env="test",
        database_url="sqlite+aiosqlite:///:memory:",
        demo_mode=False,
        app_secret="test-vault-key",
    )
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    user_id = uuid4()
    connection_id = uuid4()
    session = session_factory()
    session.add(User(id=user_id, email="plaid@test.local", display_name="Test User"))
    session.add(
        BrokerageConnection(
            id=connection_id,
            user_id=user_id,
            provider="plaid",
            display_name="A Brokerage",
            status="connected",
        )
    )
    await session.commit()
    return engine, session, connection_id


async def test_save_then_load_round_trips_credential_fields() -> None:
    engine, session, connection_id = await _make_connection_session()
    vault = TokenVault("test-vault-key")
    store = BrokerageCredentialStore(session=session, vault=vault)

    await store.save(
        connection_id=connection_id,
        access_token="access-1",
        refresh_token="refresh-1",
        token_type="Bearer",
        scope="investments",
        expires_at=NOW,
    )
    await session.commit()

    stored = await store.load(connection_id=connection_id)
    assert stored is not None
    assert stored.access_token == "access-1"
    assert stored.refresh_token == "refresh-1"
    assert stored.token_type == "Bearer"
    assert stored.scope == "investments"
    assert stored.expires_at is not None
    assert stored.expires_at.replace(tzinfo=UTC) == NOW

    await session.close()
    await engine.dispose()


async def test_save_without_expires_at_stores_none_for_providers_without_expiry() -> None:
    engine, session, connection_id = await _make_connection_session()
    vault = TokenVault("test-vault-key")
    store = BrokerageCredentialStore(session=session, vault=vault)

    await store.save(connection_id=connection_id, access_token="access-1")
    await session.commit()

    stored = await store.load(connection_id=connection_id)
    assert stored is not None
    assert stored.expires_at is None
    assert stored.refresh_token is None

    await session.close()
    await engine.dispose()


async def test_save_omitting_refresh_token_preserves_previously_stored_one() -> None:
    engine, session, connection_id = await _make_connection_session()
    vault = TokenVault("test-vault-key")
    store = BrokerageCredentialStore(session=session, vault=vault)

    await store.save(
        connection_id=connection_id,
        access_token="access-1",
        refresh_token="refresh-1",
    )
    await session.commit()

    await store.save(connection_id=connection_id, access_token="access-2")
    await session.commit()

    stored = await store.load(connection_id=connection_id)
    assert stored is not None
    assert stored.access_token == "access-2"
    assert stored.refresh_token == "refresh-1"

    await session.close()
    await engine.dispose()


async def test_load_returns_none_when_no_credential_exists() -> None:
    engine, session, connection_id = await _make_connection_session()
    vault = TokenVault("test-vault-key")
    store = BrokerageCredentialStore(session=session, vault=vault)

    assert await store.load(connection_id=connection_id) is None

    await session.close()
    await engine.dispose()
