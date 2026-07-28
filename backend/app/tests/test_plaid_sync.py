from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.models import FinancialAccount, FinancialConnection, MoneyTransactionRecord, User
from app.providers.plaid.client import PlaidSyncPage
from app.services.plaid_sync import sync_plaid_money_connection, sync_plaid_transactions
from app.tests.user_owned.factories import stable_id


class FakePlaidClient:
    def __init__(self, *pages: PlaidSyncPage, accounts: tuple[dict[str, object], ...] = ()) -> None:
        self.pages = list(pages)
        self.requested_cursors: list[str | None] = []
        self._accounts = accounts

    async def sync_transactions(
        self,
        access_token: str,
        *,
        cursor: str | None = None,
    ) -> PlaidSyncPage:
        assert access_token == "access-sandbox"
        self.requested_cursors.append(cursor)
        return self.pages.pop(0)

    async def get_accounts(self, access_token: str) -> tuple[dict[str, object], ...]:
        assert access_token == "access-sandbox"
        return self._accounts


def _raw_transaction(
    transaction_id: str,
    *,
    pending: bool,
    pending_transaction_id: str | None = None,
    amount: str = "6.50",
) -> dict[str, object]:
    return {
        "transaction_id": transaction_id,
        "pending_transaction_id": pending_transaction_id,
        "account_id": "plaid-checking",
        "pending": pending,
        "amount": amount,
        "iso_currency_code": "USD",
        "merchant_name": "Northstar Coffee",
        "name": "NORTHSTAR COFFEE",
        "authorized_datetime": "2026-07-22T12:00:00Z",
        "datetime": "2026-07-23T12:00:00Z",
        "personal_finance_category": {"primary": "FOOD_AND_DRINK"},
        "payment_channel": "in store",
    }


@pytest.mark.asyncio
async def test_plaid_sync_replaces_pending_without_double_counting() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as database:
        await database.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        user = User(
            id=stable_id("plaid-sync-user"),
            email="plaid-sync@example.test",
            display_name="Plaid Sync",
        )
        connection = FinancialConnection(
            id=stable_id("plaid-sync-connection"),
            user_id=user.id,
            provider="plaid",
            provider_item_id="item-sandbox",
            display_name="Sandbox bank",
            status="connected",
            is_demo=False,
        )
        account = FinancialAccount(
            id=stable_id("plaid-sync-account"),
            connection_id=connection.id,
            provider_account_id="plaid-checking",
            display_name="Checking",
            account_type="checking",
            currency="USD",
            current_balance=0,
            is_active=True,
        )
        session.add_all((user, connection, account))
        await session.commit()

        pending_page = PlaidSyncPage(
            added=(_raw_transaction("pending-1", pending=True),),
            modified=(),
            removed=(),
            next_cursor="cursor-1",
            has_more=False,
        )
        first = await sync_plaid_transactions(
            session,
            connection=connection,
            access_token="access-sandbox",
            client=FakePlaidClient(pending_page),
            as_of=datetime(2026, 7, 23, 13, tzinfo=UTC),
        )

        assert first.inserted == 1
        assert connection.cursor == "cursor-1"
        pending_record = await session.scalar(select(MoneyTransactionRecord))
        assert pending_record is not None
        pending_record_id = pending_record.id
        assert pending_record.status == "pending"

        posted_page = PlaidSyncPage(
            added=(
                _raw_transaction(
                    "posted-1",
                    pending=False,
                    pending_transaction_id="pending-1",
                    amount="6.84",
                ),
            ),
            modified=(),
            removed=(),
            next_cursor="cursor-2",
            has_more=False,
        )
        second_client = FakePlaidClient(posted_page)
        second = await sync_plaid_transactions(
            session,
            connection=connection,
            access_token="access-sandbox",
            client=second_client,
            as_of=datetime(2026, 7, 23, 14, tzinfo=UTC),
        )

        assert second.replaced_pending == 1
        assert second_client.requested_cursors == ["cursor-1"]
        assert await session.scalar(select(func.count(MoneyTransactionRecord.id))) == 1
        posted_record = await session.scalar(select(MoneyTransactionRecord))
        assert posted_record is not None
        assert posted_record.id == pending_record_id
        assert posted_record.provider_transaction_id == "posted-1"
        assert posted_record.status == "posted"
        assert posted_record.amount == Decimal("6.84")

    await engine.dispose()


async def test_sync_plaid_money_connection_refreshes_balances_and_transactions() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as database:
        await database.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        user = User(
            id=stable_id("plaid-money-user"),
            email="plaid-money@example.test",
            display_name="Plaid Money",
        )
        connection = FinancialConnection(
            id=stable_id("plaid-money-connection"),
            user_id=user.id,
            provider="plaid",
            provider_item_id="item-money-sandbox",
            display_name="Sandbox bank",
            status="connected",
            is_demo=False,
        )
        session.add_all((user, connection))
        await session.commit()

        page = PlaidSyncPage(
            added=(_raw_transaction("money-1", pending=False),),
            modified=(),
            removed=(),
            next_cursor="cursor-money-1",
            has_more=False,
        )
        client = FakePlaidClient(
            page,
            accounts=(
                {
                    "account_id": "plaid-checking",
                    "name": "Plaid Checking",
                    "type": "depository",
                    "subtype": "checking",
                    "balances": {"current": 942.11, "iso_currency_code": "USD"},
                },
            ),
        )

        result = await sync_plaid_money_connection(
            session,
            connection=connection,
            access_token="access-sandbox",
            client=client,
            as_of=datetime(2026, 7, 23, 13, tzinfo=UTC),
        )

        assert result.inserted == 1
        account = await session.scalar(
            select(FinancialAccount).where(
                FinancialAccount.connection_id == connection.id,
                FinancialAccount.provider_account_id == "plaid-checking",
            )
        )
        assert account is not None
        assert account.current_balance == Decimal("942.11")
        assert account.account_type == "checking"

    await engine.dispose()
