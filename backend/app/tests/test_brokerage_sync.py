from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import func, select

from app.config import Settings
from app.db.base import Base
from app.db.models import BrokerageAccount, BrokerageConnection, Position, Security, SyncRun, User
from app.db.session import create_engine, create_session_factory
from app.domain.enums import AssetType
from app.domain.models import PositionObservation
from app.services.brokerage_sync import (
    PositionMetrics,
    RawBrokerageAccount,
    prior_summary,
    sync_brokerage_snapshot,
)

NOW = datetime(2026, 7, 25, 15, tzinfo=UTC)


def _raw_account(*, provider_account_id: str, symbol: str, qty: str) -> RawBrokerageAccount:
    placeholder = uuid4()
    return RawBrokerageAccount(
        provider_account_id=provider_account_id,
        display_name=f"Test {provider_account_id[-4:]}",
        account_type="brokerage",
        balance=Decimal("1000"),
        day_change=Decimal("5"),
        total_gain=Decimal("100"),
        positions=(
            PositionObservation(
                account_id=placeholder,
                observed_at=NOW,
                provider_instrument_id=None,
                symbol=symbol,
                cusip=None,
                asset_type=AssetType.EQUITY,
                quantity=Decimal(qty),
                market_value=Decimal("1000"),
                average_price=Decimal("90"),
            ),
        ),
        security_names={symbol: f"{symbol} Inc"},
        metrics={symbol: PositionMetrics(day_change=Decimal("5"), total_gain=Decimal("100"))},
    )


async def _seed_connection(session_factory) -> tuple:
    user_id, connection_id = uuid4(), uuid4()
    async with session_factory() as session:
        session.add(User(id=user_id, email="brk@example.com", display_name="Brk"))
        session.add(
            BrokerageConnection(
                id=connection_id, user_id=user_id, provider="plaid_investments",
                display_name="Test", status="connected",
            )
        )
        await session.commit()
    return user_id, connection_id


async def _factory():
    engine = create_engine(Settings(database_url="sqlite+aiosqlite:///:memory:", app_secret="k"))
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return engine, create_session_factory(engine)


async def test_sync_brokerage_snapshot_persists_positions() -> None:
    engine, session_factory = await _factory()
    _user_id, connection_id = await _seed_connection(session_factory)
    async with session_factory() as session:
        connection = await session.get(BrokerageConnection, connection_id)
        summary = await sync_brokerage_snapshot(
            session, connection=connection, idempotency_key="key-00000001",
            accounts=[_raw_account(provider_account_id="acct-1", symbol="AAPL", qty="10")],
            as_of=NOW,
        )
    assert summary.status == "completed"
    assert summary.accounts_seen == 1
    async with session_factory() as session:
        assert (await session.scalar(select(func.count()).select_from(Position))) == 1
        assert (await session.scalar(select(func.count()).select_from(Security))) == 1
    await engine.dispose()


async def test_replay_is_idempotent() -> None:
    engine, session_factory = await _factory()
    _user_id, connection_id = await _seed_connection(session_factory)
    accounts = [_raw_account(provider_account_id="acct-1", symbol="AAPL", qty="10")]
    async with session_factory() as session:
        connection = await session.get(BrokerageConnection, connection_id)
        first = await sync_brokerage_snapshot(
            session, connection=connection, idempotency_key="key-00000001",
            accounts=accounts, as_of=NOW,
        )
    async with session_factory() as session:
        replay = await prior_summary(
            session, connection_id=connection_id, idempotency_key="key-00000001"
        )
    assert replay is not None and replay.repeated is True
    assert replay.sync_run_id == first.sync_run_id
    async with session_factory() as session:
        assert (await session.scalar(select(func.count()).select_from(SyncRun))) == 1
    await engine.dispose()


async def test_shared_symbol_across_two_accounts_reconciles() -> None:
    engine, session_factory = await _factory()
    _user_id, connection_id = await _seed_connection(session_factory)
    accounts = [
        _raw_account(provider_account_id="acct-1", symbol="AAPL", qty="10"),
        _raw_account(provider_account_id="acct-2", symbol="AAPL", qty="5"),
    ]
    async with session_factory() as session:
        connection = await session.get(BrokerageConnection, connection_id)
        summary = await sync_brokerage_snapshot(
            session, connection=connection, idempotency_key="key-00000002",
            accounts=accounts, as_of=NOW,
        )
    assert summary.status == "completed"
    assert summary.accounts_seen == 2
    assert summary.positions_seen == 2
    async with session_factory() as session:
        assert (await session.scalar(select(func.count()).select_from(BrokerageAccount))) == 2
        assert (await session.scalar(select(func.count()).select_from(Position))) == 2
        assert (await session.scalar(select(func.count()).select_from(Security))) == 1
    await engine.dispose()
