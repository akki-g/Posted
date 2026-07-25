import math
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.db.models import (
    BalanceSnapshot,
    BrokerageAccount,
    BrokerageConnection,
    EventSecurityLink,
    FinancialAccount,
    FinancialConnection,
    MarketEvent,
    MoneyTransactionRecord,
    PortfolioSnapshot,
    Position,
    RecurringStream,
    Security,
    User,
)


def demo_id(name: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"https://posted.local/demo/{name}")


async def ensure_local_user(session: AsyncSession, settings: Settings) -> None:
    """Create the single local MVP user when demo fixtures are disabled.

    Real multi-user deployment must replace the development header/user fallback
    with authentication before exposing the API publicly.
    """

    if await session.get(User, settings.dev_user_id) is not None:
        return
    session.add(
        User(
            id=settings.dev_user_id,
            email="local@posted.app",
            display_name="Posted User",
        )
    )
    await session.commit()


async def seed_demo_data(session: AsyncSession, settings: Settings) -> None:
    existing = await session.scalar(select(func.count(User.id)))
    if existing:
        await _seed_demo_money_data(session, settings=settings)
        await session.commit()
        return

    now = datetime.now(UTC).replace(microsecond=0)
    user = User(
        id=settings.dev_user_id,
        email="demo@posted.local",
        display_name="Alex Morgan",
    )
    connection = BrokerageConnection(
        id=demo_id("connection-schwab"),
        user_id=user.id,
        provider="schwab",
        display_name="Charles Schwab",
        status="demo",
        last_synced_at=now - timedelta(minutes=4),
    )
    individual = BrokerageAccount(
        id=demo_id("account-individual"),
        connection_id=connection.id,
        provider_account_id="demo-individual-001",
        display_name="Individual brokerage ••1842",
        account_type="Individual",
        balance=Decimal("196124.00"),
        day_change=Decimal("2818.62"),
        total_gain=Decimal("31240.18"),
    )
    roth = BrokerageAccount(
        id=demo_id("account-roth"),
        connection_id=connection.id,
        provider_account_id="demo-roth-001",
        display_name="Roth IRA ••6207",
        account_type="Roth IRA",
        balance=Decimal("88497.40"),
        day_change=Decimal("430.00"),
        total_gain=Decimal("11590.00"),
    )

    securities = {
        "AAPL": Security(
            id=demo_id("security-aapl"),
            symbol="AAPL",
            name="Apple Inc.",
            asset_type="equity",
            sector="Technology",
            cik="0000320193",
        ),
        "MSFT": Security(
            id=demo_id("security-msft"),
            symbol="MSFT",
            name="Microsoft Corporation",
            asset_type="equity",
            sector="Technology",
            cik="0000789019",
        ),
        "NVDA": Security(
            id=demo_id("security-nvda"),
            symbol="NVDA",
            name="NVIDIA Corporation",
            asset_type="equity",
            sector="Technology",
            cik="0001045810",
        ),
        "VTI": Security(
            id=demo_id("security-vti"),
            symbol="VTI",
            name="Vanguard Total Stock Market ETF",
            asset_type="etf",
            sector="Broad market",
        ),
        "CASH": Security(
            id=demo_id("security-cash"),
            symbol="CASH",
            name="Cash & cash investments",
            asset_type="cash",
            sector="Cash",
        ),
    }

    positions = [
        Position(
            account_id=individual.id,
            security_id=securities["AAPL"].id,
            quantity=Decimal("290"),
            average_price=Decimal("188.20"),
            last_price=Decimal("235.88"),
            market_value=Decimal("68405.20"),
            day_change=Decimal("1230.24"),
            day_change_percent=Decimal("1.83"),
            total_gain=Decimal("13827.20"),
            total_gain_percent=Decimal("25.34"),
            portfolio_weight=Decimal("24.03"),
        ),
        Position(
            account_id=individual.id,
            security_id=securities["MSFT"].id,
            quantity=Decimal("180"),
            average_price=Decimal("402.15"),
            last_price=Decimal("514.60"),
            market_value=Decimal("92628.00"),
            day_change=Decimal("1690.18"),
            day_change_percent=Decimal("1.86"),
            total_gain=Decimal("20241.00"),
            total_gain_percent=Decimal("27.96"),
            portfolio_weight=Decimal("32.54"),
        ),
        Position(
            account_id=individual.id,
            security_id=securities["NVDA"].id,
            quantity=Decimal("100"),
            average_price=Decimal("142.18"),
            last_price=Decimal("187.42"),
            market_value=Decimal("18742.00"),
            day_change=Decimal("-101.80"),
            day_change_percent=Decimal("-0.54"),
            total_gain=Decimal("4524.00"),
            total_gain_percent=Decimal("31.82"),
            portfolio_weight=Decimal("6.59"),
        ),
        Position(
            account_id=individual.id,
            security_id=securities["CASH"].id,
            quantity=Decimal("16348.8"),
            average_price=Decimal("1"),
            last_price=Decimal("1"),
            market_value=Decimal("16348.80"),
            day_change=Decimal("0"),
            day_change_percent=Decimal("0"),
            total_gain=Decimal("0"),
            total_gain_percent=Decimal("0"),
            portfolio_weight=Decimal("5.74"),
        ),
        Position(
            account_id=roth.id,
            security_id=securities["NVDA"].id,
            quantity=Decimal("220"),
            average_price=Decimal("121.30"),
            last_price=Decimal("187.42"),
            market_value=Decimal("41232.40"),
            day_change=Decimal("-224.00"),
            day_change_percent=Decimal("-0.54"),
            total_gain=Decimal("14546.40"),
            total_gain_percent=Decimal("54.51"),
            portfolio_weight=Decimal("14.49"),
        ),
        Position(
            account_id=roth.id,
            security_id=securities["VTI"].id,
            quantity=Decimal("150"),
            average_price=Decimal("271.16"),
            last_price=Decimal("315.10"),
            market_value=Decimal("47265.00"),
            day_change=Decimal("654.00"),
            day_change_percent=Decimal("1.40"),
            total_gain=Decimal("6591.00"),
            total_gain_percent=Decimal("16.20"),
            portfolio_weight=Decimal("16.61"),
        ),
    ]

    snapshots: list[PortfolioSnapshot] = []
    total_value = Decimal("284621.40")
    for days_ago in range(30, -1, -1):
        trend = Decimal(str((30 - days_ago) * 820))
        wave = Decimal(str(round(math.sin(days_ago / 2.7) * 3800, 2)))
        value = total_value - Decimal("24600") + trend + wave
        snapshots.append(
            PortfolioSnapshot(
                user_id=user.id,
                observed_at=now - timedelta(days=days_ago),
                total_value=value.quantize(Decimal("0.01")),
                day_change=Decimal("3248.62") if days_ago == 0 else Decimal("0"),
                day_change_percent=Decimal("1.15") if days_ago == 0 else Decimal("0"),
                total_gain=Decimal("42830.18"),
                total_gain_percent=Decimal("17.71"),
            )
        )

    events = [
        MarketEvent(
            id=demo_id("event-nvda-guidance"),
            event_type="guidance",
            headline="Demo event · Earnings guidance changed after quarterly results",
            summary=(
                "A demonstration event showing how Posted would prioritize a fresh guidance "
                "change for a position representing more than one fifth of this portfolio."
            ),
            occurred_at=now - timedelta(minutes=18),
            source_name="Posted demo feed",
            source_url=None,
            fingerprint="demo-nvda-guidance",
            score=Decimal("91.40"),
            level="urgent",
            confidence=Decimal("0.98"),
            unread=True,
            is_demo=True,
            reasons=[
                {"code": "material_event", "message": "Guidance changes are high materiality."},
                {"code": "direct_exposure", "message": "NVDA represents 21.08% of the portfolio."},
                {"code": "recent_event", "message": "Published less than one hour ago."},
            ],
        ),
        MarketEvent(
            id=demo_id("event-msft-8k"),
            event_type="sec_filing",
            headline="Demo event · Current report filed with material business update",
            summary=(
                "A simulated 8-K alert demonstrating how an authoritative filing is linked "
                "to the user's largest position."
            ),
            occurred_at=now - timedelta(hours=2, minutes=24),
            source_name="SEC EDGAR · demo record",
            source_url="https://www.sec.gov/edgar/search/",
            fingerprint="demo-msft-8k",
            score=Decimal("78.20"),
            level="important",
            confidence=Decimal("1.00"),
            unread=True,
            is_demo=True,
            reasons=[
                {"code": "authoritative_source", "message": "Primary source is an SEC filing."},
                {"code": "direct_exposure", "message": "MSFT represents 32.54% of the portfolio."},
            ],
        ),
        MarketEvent(
            id=demo_id("event-aapl-regulatory"),
            event_type="regulatory_legal",
            headline="Demo event · Regulatory proceeding received a procedural update",
            summary=(
                "A simulated legal update ranked as important because of position size, "
                "while avoiding any claim about likely price direction."
            ),
            occurred_at=now - timedelta(hours=7),
            source_name="Posted demo feed",
            source_url=None,
            fingerprint="demo-aapl-regulatory",
            score=Decimal("69.80"),
            level="important",
            confidence=Decimal("0.91"),
            unread=False,
            is_demo=True,
            reasons=[
                {"code": "material_event", "message": "Regulatory events can alter company risk."},
                {"code": "direct_exposure", "message": "AAPL represents 24.03% of the portfolio."},
            ],
        ),
        MarketEvent(
            id=demo_id("event-vti-distribution"),
            event_type="dividend",
            headline="Demo event · Quarterly fund distribution announced",
            summary="A routine simulated ETF distribution shown as a lower-priority update.",
            occurred_at=now - timedelta(days=1, hours=3),
            source_name="Posted demo feed",
            source_url=None,
            fingerprint="demo-vti-distribution",
            score=Decimal("44.10"),
            level="notable",
            confidence=Decimal("0.96"),
            unread=False,
            is_demo=True,
            reasons=[
                {"code": "direct_exposure", "message": "VTI represents 16.61% of the portfolio."},
                {"code": "repeated_story", "message": "This is a scheduled recurring event."},
            ],
        ),
    ]

    links = [
        EventSecurityLink(
            event_id=events[0].id,
            security_id=securities["NVDA"].id,
            match_confidence=Decimal("0.99"),
            effective_weight=Decimal("21.08"),
        ),
        EventSecurityLink(
            event_id=events[1].id,
            security_id=securities["MSFT"].id,
            match_confidence=Decimal("1"),
            effective_weight=Decimal("32.54"),
        ),
        EventSecurityLink(
            event_id=events[2].id,
            security_id=securities["AAPL"].id,
            match_confidence=Decimal("0.95"),
            effective_weight=Decimal("24.03"),
        ),
        EventSecurityLink(
            event_id=events[3].id,
            security_id=securities["VTI"].id,
            match_confidence=Decimal("0.98"),
            effective_weight=Decimal("16.61"),
        ),
    ]

    session.add_all(
        [user, connection, individual, roth, *securities.values(), *positions, *snapshots, *events]
    )
    await session.flush()
    session.add_all(links)
    await _seed_demo_money_data(session, settings=settings, now=now)
    await session.commit()


async def _seed_demo_money_data(
    session: AsyncSession,
    *,
    settings: Settings,
    now: datetime | None = None,
) -> None:
    existing = await session.scalar(select(func.count(FinancialConnection.id)))
    if existing:
        return

    now = now or datetime.now(UTC).replace(microsecond=0)
    connection = FinancialConnection(
        id=demo_id("money-connection-plaid"),
        user_id=settings.dev_user_id,
        provider="plaid",
        provider_item_id="demo-plaid-item",
        display_name="Plaid Sandbox",
        status="demo",
        last_synced_at=now - timedelta(minutes=6),
        is_demo=True,
    )
    checking = FinancialAccount(
        id=demo_id("money-account-checking"),
        connection_id=connection.id,
        provider_account_id="demo-checking-4821",
        display_name="Everyday Checking",
        mask="4821",
        account_type="checking",
        subtype="checking",
        currency="USD",
        current_balance=Decimal("6842.18"),
        available_balance=Decimal("6510.72"),
    )
    savings = FinancialAccount(
        id=demo_id("money-account-savings"),
        connection_id=connection.id,
        provider_account_id="demo-savings-9914",
        display_name="High Yield Savings",
        mask="9914",
        account_type="savings",
        subtype="savings",
        currency="USD",
        current_balance=Decimal("24860.00"),
        available_balance=Decimal("24860.00"),
    )
    credit = FinancialAccount(
        id=demo_id("money-account-credit"),
        connection_id=connection.id,
        provider_account_id="demo-credit-3049",
        display_name="Sapphire Card",
        mask="3049",
        account_type="credit_card",
        subtype="credit card",
        currency="USD",
        current_balance=Decimal("1842.67"),
        available_balance=Decimal("8157.33"),
        credit_limit=Decimal("10000.00"),
    )

    snapshots: list[BalanceSnapshot] = []
    for account, base_balance in (
        (checking, Decimal("6842.18")),
        (savings, Decimal("24860.00")),
        (credit, Decimal("1842.67")),
    ):
        for days_ago in range(6, -1, -1):
            drift = Decimal(days_ago * 42 if account is checking else days_ago * 7)
            snapshots.append(
                BalanceSnapshot(
                    id=demo_id(f"balance-{account.provider_account_id}-{days_ago}"),
                    account_id=account.id,
                    observed_at=now - timedelta(days=days_ago),
                    current_balance=base_balance + drift,
                    available_balance=(
                        base_balance + drift
                        if account is not credit
                        else Decimal("10000") - base_balance - drift
                    ),
                )
            )

    transactions: list[MoneyTransactionRecord] = []

    def add_transaction(
        name: str,
        *,
        account: FinancialAccount = checking,
        days_ago: int,
        amount: str,
        merchant: str,
        category: str,
        direction: str = "outflow",
        status: str = "posted",
        is_transfer: bool = False,
        is_recurring: bool = False,
    ) -> None:
        occurred_at = now - timedelta(days=days_ago)
        transactions.append(
            MoneyTransactionRecord(
                id=demo_id(f"money-transaction-{name}"),
                account_id=account.id,
                source="demo",
                provider_transaction_id=f"demo-{name}",
                pending_provider_transaction_id=None,
                status=status,
                direction=direction,
                amount=Decimal(amount),
                currency="USD",
                merchant_name=merchant,
                description=merchant,
                occurred_at=occurred_at,
                posted_at=occurred_at if status == "posted" else None,
                category_primary=category,
                category_detailed=None,
                payment_channel="online" if is_recurring else "in_store",
                fingerprint=f"demo-{name}",
                is_transfer=is_transfer,
                is_recurring=is_recurring,
                is_demo=True,
            )
        )

    add_transaction(
        "salary-july",
        days_ago=5,
        amount="3250.00",
        merchant="Acme Payroll",
        category="INCOME",
        direction="inflow",
    )
    add_transaction(
        "rent-july",
        days_ago=3,
        amount="1850.00",
        merchant="Parkview Rent",
        category="RENT",
        is_recurring=True,
    )
    add_transaction(
        "market-july", days_ago=2, amount="126.84", merchant="Greenway Market", category="GROCERIES"
    )
    add_transaction(
        "coffee-july",
        days_ago=1,
        amount="6.50",
        merchant="Northstar Coffee",
        category="FOOD_AND_DRINK",
    )
    add_transaction(
        "transit-july",
        days_ago=1,
        amount="24.50",
        merchant="Metro Transit",
        category="TRANSPORTATION",
    )
    add_transaction(
        "restaurant-july",
        account=credit,
        days_ago=2,
        amount="78.20",
        merchant="Juniper Kitchen",
        category="FOOD_AND_DRINK",
    )
    add_transaction(
        "gym-july",
        account=credit,
        days_ago=1,
        amount="39.99",
        merchant="Form Athletics",
        category="HEALTH_AND_FITNESS",
        is_recurring=True,
    )
    add_transaction(
        "spotify-july",
        account=credit,
        days_ago=1,
        amount="11.99",
        merchant="Spotify",
        category="ENTERTAINMENT",
        is_recurring=True,
    )
    add_transaction(
        "pending-store",
        account=credit,
        days_ago=0,
        amount="42.15",
        merchant="Corner Store",
        category="GENERAL_MERCHANDISE",
        status="pending",
    )
    add_transaction(
        "card-payment-out",
        days_ago=4,
        amount="450.00",
        merchant="Credit Card Payment",
        category="CREDIT_CARD_PAYMENT",
        is_transfer=True,
    )
    add_transaction(
        "card-payment-in",
        account=credit,
        days_ago=3,
        amount="450.00",
        merchant="Payment Received",
        category="TRANSFER_IN",
        direction="inflow",
        is_transfer=True,
    )

    for prefix, merchant, amount, category, offsets in (
        ("rent", "Parkview Rent", "1850.00", "RENT", (63, 33)),
        ("gym", "Form Athletics", "39.99", "HEALTH_AND_FITNESS", (61, 31)),
        ("spotify", "Spotify", "11.99", "ENTERTAINMENT", (61, 31)),
        ("streambox", "Streambox", "15.49", "ENTERTAINMENT", (62, 32, 2)),
    ):
        for offset in offsets:
            add_transaction(
                f"{prefix}-{offset}",
                account=credit if prefix != "rent" else checking,
                days_ago=offset,
                amount=amount,
                merchant=merchant,
                category=category,
                is_recurring=True,
            )

    recurring_streams = [
        RecurringStream(
            id=demo_id(f"recurring-{key}"),
            user_id=settings.dev_user_id,
            stream_key=key,
            merchant_name=merchant,
            frequency="monthly",
            average_amount=Decimal(amount),
            last_amount=Decimal(amount),
            currency="USD",
            last_charged_at=now - timedelta(days=last_days_ago),
            next_expected_date=(now + timedelta(days=next_days)).date(),
            confidence=Decimal(confidence),
            status="active",
            is_demo=True,
        )
        for key, merchant, amount, last_days_ago, next_days, confidence in (
            ("parkview-rent-monthly", "Parkview Rent", "1850.00", 3, 27, "0.99"),
            ("form-athletics-monthly", "Form Athletics", "39.99", 1, 29, "0.97"),
            ("spotify-monthly", "Spotify", "11.99", 1, 29, "0.98"),
            ("streambox-monthly", "Streambox", "15.49", 2, 28, "0.96"),
        )
    ]

    session.add_all(
        [
            connection,
            checking,
            savings,
            credit,
            *snapshots,
            *transactions,
            *recurring_streams,
        ]
    )
