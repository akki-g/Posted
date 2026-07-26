from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.routes.plaid import exchange_plaid_public_token
from app.api.schemas import PlaidExchangeRequest
from app.config import Settings
from app.db.base import Base
from app.db.models import FinancialAccount, FinancialConnection, User
from app.providers.plaid.client import PlaidTokenExchange


class FakePlaidClient:
    """Fake Plaid client exposing exactly the surface the routes call."""

    def __init__(
        self,
        *,
        item_id: str,
        institution_id: str | None,
        accounts: tuple[dict[str, Any], ...],
    ) -> None:
        self.item_id = item_id
        self.institution_id = institution_id
        self.accounts = accounts
        self.remove_item_calls: list[str] = []

    async def exchange_public_token(self, public_token: str) -> PlaidTokenExchange:
        return PlaidTokenExchange(
            access_token=f"access-{self.item_id}",
            item_id=self.item_id,
            request_id=None,
        )

    async def get_item(self, access_token: str) -> dict[str, Any]:
        return {"institution_id": self.institution_id}

    async def get_accounts(self, access_token: str) -> tuple[dict[str, Any], ...]:
        return self.accounts

    async def remove_item(self, access_token: str) -> None:
        self.remove_item_calls.append(access_token)


def _account(account_id: str, *, balance: str = "100.00") -> dict[str, Any]:
    return {
        "account_id": account_id,
        "name": "Checking",
        "official_name": None,
        "mask": "1234",
        "type": "depository",
        "subtype": "checking",
        "balances": {
            "current": balance,
            "available": balance,
            "iso_currency_code": "USD",
        },
    }


@pytest.fixture
def settings() -> Settings:
    return Settings(
        app_env="test",
        database_url="sqlite+aiosqlite:///:memory:",
        demo_mode=False,
        app_secret="test-vault-key",
        plaid_client_id="sandbox-client-id",
        plaid_secret="sandbox-secret",
        plaid_environment="sandbox",
    )


@pytest.fixture
async def session_factory() -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


async def _seed_user(session_factory: async_sessionmaker[AsyncSession]) -> UUID:
    user_id = uuid4()
    async with session_factory() as session:
        session.add(User(id=user_id, email=f"{user_id}@example.test", display_name="Tester"))
        await session.commit()
    return user_id


async def test_exchanging_the_same_institution_twice_refreshes_in_place(
    session_factory: async_sessionmaker[AsyncSession], settings: Settings, monkeypatch
) -> None:
    from app.api.routes import plaid as plaid_routes

    user_id = await _seed_user(session_factory)

    first_client = FakePlaidClient(
        item_id="item-1",
        institution_id="ins_x",
        accounts=(_account("acct-1"), _account("acct-2")),
    )
    monkeypatch.setattr(plaid_routes, "_plaid_client", lambda settings: first_client)

    async with session_factory() as session:
        await exchange_plaid_public_token(
            request=PlaidExchangeRequest(public_token="public-token-aaaaaaaa"),
            session=session,
            user_id=user_id,
            settings=settings,
        )

    second_client = FakePlaidClient(
        item_id="item-2",
        institution_id="ins_x",
        accounts=(_account("acct-3", balance="55.00"),),
    )
    monkeypatch.setattr(plaid_routes, "_plaid_client", lambda settings: second_client)

    async with session_factory() as session:
        result = await exchange_plaid_public_token(
            request=PlaidExchangeRequest(public_token="public-token-bbbbbbbb"),
            session=session,
            user_id=user_id,
            settings=settings,
        )

    async with session_factory() as session:
        connection_count = await session.scalar(
            select(func.count()).select_from(FinancialConnection).where(
                FinancialConnection.user_id == user_id
            )
        )
        assert connection_count == 1

        connection = await session.scalar(
            select(FinancialConnection).where(FinancialConnection.user_id == user_id)
        )
        assert connection is not None
        assert connection.id == result.id
        assert connection.provider_item_id == "item-2"
        assert connection.institution_id == "ins_x"
        assert connection.cursor is None

        account_count = await session.scalar(
            select(func.count()).select_from(FinancialAccount).where(
                FinancialAccount.connection_id == connection.id
            )
        )
        assert account_count == 1  # second payload's count, not doubled

        account = await session.scalar(
            select(FinancialAccount).where(FinancialAccount.connection_id == connection.id)
        )
        assert account is not None
        assert account.provider_account_id == "acct-3"
        assert account.current_balance == Decimal("55.00")

    # The active client at exchange time is the second one; it is the one that
    # tells Plaid to invalidate the now-dead first Item.
    assert first_client.remove_item_calls == []
    assert second_client.remove_item_calls == ["access-item-1"]


async def test_exchanging_two_different_institutions_creates_two_connections(
    session_factory: async_sessionmaker[AsyncSession], settings: Settings, monkeypatch
) -> None:
    from app.api.routes import plaid as plaid_routes

    user_id = await _seed_user(session_factory)

    first_client = FakePlaidClient(
        item_id="item-1", institution_id="ins_x", accounts=(_account("acct-1"),)
    )
    monkeypatch.setattr(plaid_routes, "_plaid_client", lambda settings: first_client)
    async with session_factory() as session:
        await exchange_plaid_public_token(
            request=PlaidExchangeRequest(public_token="public-token-aaaaaaaa"),
            session=session,
            user_id=user_id,
            settings=settings,
        )

    second_client = FakePlaidClient(
        item_id="item-2", institution_id="ins_y", accounts=(_account("acct-2"),)
    )
    monkeypatch.setattr(plaid_routes, "_plaid_client", lambda settings: second_client)
    async with session_factory() as session:
        await exchange_plaid_public_token(
            request=PlaidExchangeRequest(public_token="public-token-bbbbbbbb"),
            session=session,
            user_id=user_id,
            settings=settings,
        )

    async with session_factory() as session:
        connection_count = await session.scalar(
            select(func.count()).select_from(FinancialConnection).where(
                FinancialConnection.user_id == user_id
            )
        )
        assert connection_count == 2

    assert first_client.remove_item_calls == []
    assert second_client.remove_item_calls == []
