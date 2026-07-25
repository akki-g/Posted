from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import func, select

from app.config import Settings
from app.db.base import Base
from app.db.models import (
    BrokerageAccount,
    BrokerageConnection,
    OAuthCredential,
    PortfolioSnapshot,
    Position,
    Security,
    SyncRun,
    User,
)
from app.db.session import create_engine, create_session_factory
from app.providers.schwab.credentials import SchwabCredentialStore
from app.providers.schwab.oauth import OAuthTokenSet
from app.security.vault import TokenVault
from app.services.schwab_sync import sync_schwab_connection

NOW = datetime(2026, 7, 23, 12, tzinfo=UTC)


class FakeOAuthClient:
    refresh_calls = 0

    async def refresh(self, *, refresh_token: str) -> OAuthTokenSet:
        assert refresh_token == "refresh-original"
        self.refresh_calls += 1
        # Schwab-style refresh response without a replacement refresh token.
        return OAuthTokenSet(
            access_token="access-refreshed",
            expires_in=1800,
            obtained_at=NOW,
        )


class FakeTraderClient:
    async def get_account_numbers(self) -> list[dict[str, object]]:
        return [{"accountNumber": "12345678", "hashValue": "opaque-account-hash"}]

    async def get_accounts_with_positions(self) -> list[dict[str, object]]:
        return [
            {
                "securitiesAccount": {
                    "accountNumber": "12345678",
                    "type": "MARGIN",
                    "currentBalances": {"liquidationValue": "12500"},
                    "positions": [
                        {
                            "longQuantity": "10",
                            "shortQuantity": "0",
                            "averagePrice": "100",
                            "marketValue": "1500",
                            "currentDayProfitLoss": "25",
                            "longOpenProfitLoss": "500",
                            "instrument": {
                                "assetType": "EQUITY",
                                "symbol": "AAPL",
                                "description": "Apple Inc.",
                            },
                        },
                        {
                            "longQuantity": "20",
                            "shortQuantity": "0",
                            "averagePrice": "200",
                            "marketValue": "5000",
                            "currentDayProfitLoss": "-10",
                            "longOpenProfitLoss": "1000",
                            "instrument": {
                                "assetType": "ETF",
                                "symbol": "VTI",
                                "description": "Vanguard Total Stock Market ETF",
                            },
                        },
                        {
                            # Schwab (via its inherited TD Ameritrade API) commonly reports
                            # real ETF holdings under this asset type rather than "ETF" --
                            # must not be silently dropped from sync.
                            "longQuantity": "5",
                            "shortQuantity": "0",
                            "averagePrice": "50",
                            "marketValue": "300",
                            "currentDayProfitLoss": "5",
                            "longOpenProfitLoss": "50",
                            "instrument": {
                                "assetType": "COLLECTIVE_INVESTMENT",
                                "symbol": "SCHB",
                                "description": "Schwab US Broad Market ETF",
                            },
                        },
                    ],
                }
            }
        ]


async def test_live_schwab_sync_refreshes_and_persists_complete_snapshot() -> None:
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
    vault = TokenVault(settings.app_secret.get_secret_value())
    async with session_factory() as session:
        session.add(User(id=user_id, email="schwab@test.local", display_name="Test User"))
        connection = BrokerageConnection(
            id=connection_id,
            user_id=user_id,
            provider="schwab",
            display_name="Charles Schwab",
            status="connected",
        )
        session.add(connection)
        session.add(
            OAuthCredential(
                connection_id=connection_id,
                access_token_encrypted=vault.encrypt("access-expired"),
                refresh_token_encrypted=vault.encrypt("refresh-original"),
                token_type="Bearer",
                expires_at=NOW - timedelta(minutes=1),
            )
        )
        await session.commit()

        oauth = FakeOAuthClient()
        result = await sync_schwab_connection(
            session,
            connection=connection,
            idempotency_key="live-sync-0001",
            credential_store=SchwabCredentialStore(session=session, vault=vault),
            oauth_client=oauth,  # type: ignore[arg-type]
            trader_factory=lambda _token: FakeTraderClient(),
            as_of=NOW,
        )

        assert result.status == "completed"
        assert result.accounts_seen == 1
        assert result.positions_seen == 3
        assert oauth.refresh_calls == 1

        account = await session.scalar(select(BrokerageAccount))
        assert account is not None
        assert account.provider_account_id == "opaque-account-hash"
        assert account.display_name.endswith("••5678")
        assert account.balance == Decimal("12500")

        securities = list((await session.scalars(select(Security))).all())
        assert {security.symbol for security in securities} == {"AAPL", "VTI", "SCHB"}
        positions = list((await session.scalars(select(Position))).all())
        assert len(positions) == 3
        assert sum((position.day_change for position in positions), Decimal("0")) == Decimal(
            "20"
        )
        snapshot = await session.scalar(select(PortfolioSnapshot))
        assert snapshot is not None
        assert snapshot.total_value == Decimal("12500")
        assert snapshot.total_gain == Decimal("1550")

        stored = await SchwabCredentialStore(session=session, vault=vault).load(
            connection_id=connection_id
        )
        assert stored is not None
        assert stored.access_token == "access-refreshed"
        assert stored.refresh_token == "refresh-original"

        repeated = await sync_schwab_connection(
            session,
            connection=connection,
            idempotency_key="live-sync-0001",
            credential_store=SchwabCredentialStore(session=session, vault=vault),
            oauth_client=oauth,  # type: ignore[arg-type]
            trader_factory=lambda _token: (_ for _ in ()).throw(
                AssertionError("provider must not be called for an idempotent replay")
            ),
            as_of=NOW + timedelta(minutes=1),
        )
        assert repeated.repeated is True
        assert await session.scalar(select(func.count(SyncRun.id))) == 1

    await engine.dispose()
