from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.routes.connections import sync_connection
from app.api.schemas import SyncRequest
from app.config import Settings
from app.db.base import Base
from app.db.models import BrokerageConnection, User
from app.db.session import create_engine, create_session_factory


async def test_sync_rejects_unsupported_provider_cleanly() -> None:
    # A connection with an unsupported provider must 400, not 500 -- proves
    # the dispatch table guards unknown providers before any adapter runs.
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
    async with session_factory() as session:
        session.add(User(id=user_id, email="unsupported@test.local", display_name="Unsupported"))
        brokerage_connection = BrokerageConnection(
            id=connection_id,
            user_id=user_id,
            provider="robinhood",
            display_name="Robinhood",
            status="connected",
        )
        session.add(brokerage_connection)
        await session.commit()

        with pytest.raises(HTTPException) as exc_info:
            await sync_connection(
                connection_id=connection_id,
                request=SyncRequest(idempotency_key="unsupported-0001"),
                session=session,
                user_id=user_id,
                settings=settings,
            )
        assert exc_info.value.status_code == 400
        assert "robinhood" in exc_info.value.detail

    await engine.dispose()


async def test_sync_dispatches_plaid_investments_connection_to_plaid_adapter() -> None:
    # A plaid_investments connection with demo_mode off and no stored credential
    # should fail through the Plaid adapter (502, Plaid-flavored message), proving
    # the dispatch table routed it to sync_plaid_investments_connection and not
    # to the Schwab path.
    settings = Settings(
        app_env="test",
        database_url="sqlite+aiosqlite:///:memory:",
        demo_mode=False,
        app_secret="test-vault-key",
        plaid_client_id="sandbox-client-id",
        plaid_secret="sandbox-secret",
        plaid_environment="sandbox",
    )
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    user_id = uuid4()
    connection_id = uuid4()
    async with session_factory() as session:
        session.add(User(id=user_id, email="plaid-inv@test.local", display_name="Plaid Investor"))
        brokerage_connection = BrokerageConnection(
            id=connection_id,
            user_id=user_id,
            provider="plaid_investments",
            display_name="Plaid Brokerage",
            status="connected",
        )
        session.add(brokerage_connection)
        await session.commit()

        with pytest.raises(HTTPException) as exc_info:
            await sync_connection(
                connection_id=connection_id,
                request=SyncRequest(idempotency_key="plaid-inv-sync-01"),
                session=session,
                user_id=user_id,
                settings=settings,
            )
        assert exc_info.value.status_code == 502
        assert "Reconnect this brokerage" in exc_info.value.detail

    await engine.dispose()
