"""Institution-scoped dedup for the Plaid-investments exchange endpoint.

A re-link of the *same* Plaid institution must refresh the existing
`BrokerageConnection` in place (swap the stored token, drop the old Plaid
Item, clear stale accounts for a fresh sync) instead of minting a second
connection. Linking a *different* institution must create a new one.
"""

from dataclasses import dataclass, field
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.api.routes import plaid_investments
from app.api.schemas import PlaidExchangeRequest
from app.config import Settings
from app.db.base import Base
from app.db.models import BrokerageAccount, BrokerageConnection, User
from app.db.session import create_engine, create_session_factory
from app.security.brokerage_credentials import BrokerageCredentialStore
from app.security.vault import TokenVault


@dataclass
class FakePlaidInvestmentsClient:
    """Fake Plaid client keyed by public_token, exposing the four methods the
    exchange route calls: exchange_public_token, get_item, get_accounts,
    remove_item."""

    tokens: dict[str, dict[str, object]]
    removed_access_tokens: list[str] = field(default_factory=list)
    remove_item_should_raise: bool = False

    async def exchange_public_token(self, public_token: str) -> SimpleNamespace:
        data = self.tokens[public_token]
        return SimpleNamespace(
            access_token=data["access_token"], item_id=data["access_token"], request_id=None
        )

    async def get_accounts(self, access_token: str) -> tuple[dict[str, object], ...]:
        return tuple(self._by_access_token(access_token)["accounts"])

    async def get_item(self, access_token: str) -> dict[str, object]:
        return {"institution_id": self._by_access_token(access_token)["institution_id"]}

    async def remove_item(self, access_token: str) -> None:
        if self.remove_item_should_raise:
            raise RuntimeError("plaid unavailable")
        self.removed_access_tokens.append(access_token)

    def _by_access_token(self, access_token: str) -> dict[str, object]:
        for data in self.tokens.values():
            if data["access_token"] == access_token:
                return data
        raise KeyError(access_token)


def _settings() -> Settings:
    return Settings(
        app_env="test",
        database_url="sqlite+aiosqlite:///:memory:",
        demo_mode=False,
        app_secret="test-vault-key",
    )


async def _make_session_factory():
    settings = _settings()
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return settings, engine, session_factory


async def _exchange(
    *, monkeypatch, fake_client, session, user_id, settings, public_token
):
    monkeypatch.setattr(plaid_investments, "_plaid_client", lambda _settings: fake_client)
    return await plaid_investments.exchange_plaid_investments_token(
        request=PlaidExchangeRequest(public_token=public_token),
        session=session,
        user_id=user_id,
        settings=settings,
    )


async def test_relinking_same_institution_refreshes_connection_in_place(monkeypatch):
    settings, engine, session_factory = await _make_session_factory()
    user_id = uuid4()

    fake_client = FakePlaidInvestmentsClient(
        tokens={
            "pub-first": {
                "access_token": "access-first",
                "institution_id": "ins_acme",
                "accounts": [{"account_id": "a1"}, {"account_id": "a2"}],
            },
            "pub-second": {
                "access_token": "access-second",
                "institution_id": "ins_acme",
                "accounts": [{"account_id": "b1"}],
            },
        }
    )

    async with session_factory() as session:
        session.add(User(id=user_id, email="dedup@test.local", display_name="Dedup"))
        await session.commit()

        first = await _exchange(
            monkeypatch=monkeypatch, fake_client=fake_client, session=session,
            user_id=user_id, settings=settings, public_token="pub-first",
        )
        assert first.account_count == 2
        assert first.provider == "plaid_investments"

        connections = (
            await session.scalars(
                select(BrokerageConnection).where(
                    BrokerageConnection.user_id == user_id,
                    BrokerageConnection.provider == "plaid_investments",
                )
            )
        ).all()
        assert len(connections) == 1
        connection_id = connections[0].id
        assert connections[0].institution_id == "ins_acme"

        # Seed a stale account row on the connection to prove refresh clears it.
        session.add(
            BrokerageAccount(
                connection_id=connection_id,
                provider_account_id="a1",
                display_name="Old brokerage account",
                account_type="brokerage",
                balance=Decimal("100.00"),
                day_change=Decimal("0"),
                total_gain=Decimal("0"),
            )
        )
        await session.commit()

        store = BrokerageCredentialStore(
            session=session, vault=TokenVault(settings.app_secret.get_secret_value())
        )
        stored = await store.load(connection_id=connection_id)
        assert stored is not None
        assert stored.access_token == "access-first"

        second = await _exchange(
            monkeypatch=monkeypatch, fake_client=fake_client, session=session,
            user_id=user_id, settings=settings, public_token="pub-second",
        )
        assert second.account_count == 1
        assert second.id == connection_id

        # Still exactly one connection for this user/provider/institution.
        connections_after = (
            await session.scalars(
                select(BrokerageConnection).where(
                    BrokerageConnection.user_id == user_id,
                    BrokerageConnection.provider == "plaid_investments",
                )
            )
        ).all()
        assert len(connections_after) == 1
        assert connections_after[0].id == connection_id

        # The old Plaid Item was removed, and the token on file was swapped.
        assert fake_client.removed_access_tokens == ["access-first"]
        refreshed = await store.load(connection_id=connection_id)
        assert refreshed is not None
        assert refreshed.access_token == "access-second"

        # Stale accounts from the pre-refresh state were cleared (next sync repopulates).
        remaining_accounts = (
            await session.scalars(
                select(BrokerageAccount).where(BrokerageAccount.connection_id == connection_id)
            )
        ).all()
        assert remaining_accounts == []

    await engine.dispose()


async def test_relinking_different_institution_creates_second_connection(monkeypatch):
    settings, engine, session_factory = await _make_session_factory()
    user_id = uuid4()

    fake_client = FakePlaidInvestmentsClient(
        tokens={
            "pub-acme": {
                "access_token": "access-acme",
                "institution_id": "ins_acme",
                "accounts": [{"account_id": "a1"}],
            },
            "pub-globex": {
                "access_token": "access-globex",
                "institution_id": "ins_globex",
                "accounts": [{"account_id": "g1"}, {"account_id": "g2"}],
            },
        }
    )

    async with session_factory() as session:
        session.add(User(id=user_id, email="two-inst@test.local", display_name="TwoInst"))
        await session.commit()

        first = await _exchange(
            monkeypatch=monkeypatch, fake_client=fake_client, session=session,
            user_id=user_id, settings=settings, public_token="pub-acme",
        )
        second = await _exchange(
            monkeypatch=monkeypatch, fake_client=fake_client, session=session,
            user_id=user_id, settings=settings, public_token="pub-globex",
        )

        assert first.id != second.id

        connections = (
            await session.scalars(
                select(BrokerageConnection).where(
                    BrokerageConnection.user_id == user_id,
                    BrokerageConnection.provider == "plaid_investments",
                )
            )
        ).all()
        assert len(connections) == 2
        assert {c.institution_id for c in connections} == {"ins_acme", "ins_globex"}
        # No refresh happened -- neither Item was removed.
        assert fake_client.removed_access_tokens == []

    await engine.dispose()


async def test_remove_item_failure_does_not_block_refresh(monkeypatch):
    settings, engine, session_factory = await _make_session_factory()
    user_id = uuid4()

    fake_client = FakePlaidInvestmentsClient(
        tokens={
            "pub-first": {
                "access_token": "access-first",
                "institution_id": "ins_acme",
                "accounts": [{"account_id": "a1"}],
            },
            "pub-second": {
                "access_token": "access-second",
                "institution_id": "ins_acme",
                "accounts": [{"account_id": "b1"}],
            },
        },
        remove_item_should_raise=True,
    )

    async with session_factory() as session:
        session.add(User(id=user_id, email="best-effort@test.local", display_name="BestEffort"))
        await session.commit()

        await _exchange(
            monkeypatch=monkeypatch, fake_client=fake_client, session=session,
            user_id=user_id, settings=settings, public_token="pub-first",
        )
        second = await _exchange(
            monkeypatch=monkeypatch, fake_client=fake_client, session=session,
            user_id=user_id, settings=settings, public_token="pub-second",
        )

        store = BrokerageCredentialStore(
            session=session, vault=TokenVault(settings.app_secret.get_secret_value())
        )
        stored = await store.load(connection_id=second.id)
        assert stored is not None
        assert stored.access_token == "access-second"

    await engine.dispose()


async def test_exchange_without_institution_id_still_creates_connection(monkeypatch):
    # A provider response that omits institution_id must not blow up; the
    # connection is created (dedup is simply skipped for that link).
    settings, engine, session_factory = await _make_session_factory()
    user_id = uuid4()

    fake_client = FakePlaidInvestmentsClient(
        tokens={
            "pub-no-inst": {
                "access_token": "access-no-inst",
                "institution_id": None,
                "accounts": [{"account_id": "a1"}],
            },
        }
    )

    async with session_factory() as session:
        session.add(User(id=user_id, email="no-inst@test.local", display_name="NoInst"))
        await session.commit()

        result = await _exchange(
            monkeypatch=monkeypatch, fake_client=fake_client, session=session,
            user_id=user_id, settings=settings, public_token="pub-no-inst",
        )
        assert result.status == "connected"

        connection = await session.get(BrokerageConnection, result.id)
        assert connection is not None
        assert connection.institution_id is None

    await engine.dispose()


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
