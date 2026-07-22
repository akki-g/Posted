from collections import defaultdict
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.schemas import (
    DailySpendingPoint,
    MoneyAccountSummary,
    MoneyConnectionStatus,
    MoneyOverviewResponse,
    MoneyTransactionsResponse,
    MoneyTransactionSummary,
    RecurringStreamSummary,
    SpendingCategorySummary,
)
from app.db.models import (
    FinancialAccount,
    FinancialConnection,
    MoneyTransactionRecord,
    RecurringStream,
)

ZERO = Decimal("0")
EXCLUDED_SPENDING_CATEGORIES = {
    "CREDIT_CARD_PAYMENT",
    "INTERNAL_TRANSFER",
    "INVESTMENT_TRANSFER",
    "LOAN_PAYMENTS",
    "TRANSFER_IN",
    "TRANSFER_OUT",
}


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _account_schema(account: FinancialAccount) -> MoneyAccountSummary:
    return MoneyAccountSummary(
        id=account.id,
        name=account.display_name,
        provider=account.connection.provider,
        account_type=account.account_type,
        mask=account.mask,
        currency=account.currency,
        current_balance=account.current_balance,
        available_balance=account.available_balance,
        credit_limit=account.credit_limit,
        is_liability=account.account_type in {"credit_card", "loan"},
    )


def _transaction_schema(transaction: MoneyTransactionRecord) -> MoneyTransactionSummary:
    return MoneyTransactionSummary(
        id=transaction.id,
        account_id=transaction.account_id,
        account_name=transaction.account.display_name,
        merchant_name=transaction.merchant_name,
        description=transaction.description,
        status=transaction.status,
        direction=transaction.direction,
        amount=transaction.amount,
        currency=transaction.currency,
        occurred_at=transaction.occurred_at,
        category=transaction.category_primary,
        payment_channel=transaction.payment_channel,
        is_transfer=transaction.is_transfer,
        is_recurring=transaction.is_recurring,
    )


def _recurring_schema(stream: RecurringStream) -> RecurringStreamSummary:
    return RecurringStreamSummary(
        id=stream.id,
        merchant_name=stream.merchant_name,
        frequency=stream.frequency,
        average_amount=stream.average_amount,
        last_amount=stream.last_amount,
        currency=stream.currency,
        last_charged_at=stream.last_charged_at,
        next_expected_date=stream.next_expected_date.isoformat(),
        confidence=stream.confidence,
        status=stream.status,
    )


async def get_money_accounts(session: AsyncSession, *, user_id: UUID) -> list[MoneyAccountSummary]:
    result = await session.scalars(
        select(FinancialAccount)
        .join(FinancialConnection)
        .where(
            FinancialConnection.user_id == user_id,
            FinancialAccount.is_active.is_(True),
        )
        .options(selectinload(FinancialAccount.connection))
        .order_by(FinancialAccount.account_type, FinancialAccount.display_name)
    )
    return [_account_schema(account) for account in result.all()]


async def get_money_connections(
    session: AsyncSession, *, user_id: UUID
) -> list[MoneyConnectionStatus]:
    result = await session.execute(
        select(FinancialConnection, func.count(FinancialAccount.id))
        .outerjoin(FinancialAccount)
        .where(FinancialConnection.user_id == user_id)
        .group_by(FinancialConnection.id)
        .order_by(FinancialConnection.created_at)
    )
    return [
        MoneyConnectionStatus(
            id=connection.id,
            provider=connection.provider,
            display_name=connection.display_name,
            status=connection.status,
            last_synced_at=connection.last_synced_at,
            account_count=account_count,
            is_demo=connection.is_demo,
        )
        for connection, account_count in result.all()
    ]


async def get_money_transactions(
    session: AsyncSession,
    *,
    user_id: UUID,
    search: str | None = None,
    category: str | None = None,
    status: str | None = None,
    limit: int = 100,
) -> MoneyTransactionsResponse:
    ownership = FinancialConnection.user_id == user_id
    filters = [ownership]
    if search:
        pattern = f"%{search.strip()}%"
        filters.append(
            or_(
                MoneyTransactionRecord.merchant_name.ilike(pattern),
                MoneyTransactionRecord.description.ilike(pattern),
            )
        )
    if category:
        filters.append(MoneyTransactionRecord.category_primary == category.upper())
    if status:
        filters.append(MoneyTransactionRecord.status == status)

    query = (
        select(MoneyTransactionRecord)
        .join(FinancialAccount)
        .join(FinancialConnection)
        .where(*filters)
    )
    total = await session.scalar(select(func.count()).select_from(query.subquery()))
    result = await session.scalars(
        query.options(selectinload(MoneyTransactionRecord.account))
        .order_by(
            MoneyTransactionRecord.occurred_at.desc(),
            MoneyTransactionRecord.id,
        )
        .limit(limit)
    )
    return MoneyTransactionsResponse(
        items=[_transaction_schema(transaction) for transaction in result.all()],
        total=total or 0,
    )


async def get_recurring_streams(
    session: AsyncSession, *, user_id: UUID
) -> list[RecurringStreamSummary]:
    result = await session.scalars(
        select(RecurringStream)
        .where(RecurringStream.user_id == user_id, RecurringStream.status == "active")
        .order_by(RecurringStream.next_expected_date, RecurringStream.merchant_name)
    )
    return [_recurring_schema(stream) for stream in result.all()]


async def get_money_overview(
    session: AsyncSession,
    *,
    user_id: UUID,
    demo_mode: bool,
    now: datetime | None = None,
) -> MoneyOverviewResponse:
    now = now or datetime.now(UTC)
    period_start = now - timedelta(days=7)
    accounts = await get_money_accounts(session, user_id=user_id)
    transaction_result = await get_money_transactions(session, user_id=user_id, limit=200)
    subscriptions = await get_recurring_streams(session, user_id=user_id)
    connections = await get_money_connections(session, user_id=user_id)

    weekly_transactions = [
        transaction
        for transaction in transaction_result.items
        if _as_utc(transaction.occurred_at) >= period_start and transaction.status == "posted"
    ]
    spendable = [
        transaction
        for transaction in weekly_transactions
        if transaction.direction == "outflow"
        and not transaction.is_transfer
        and transaction.category not in EXCLUDED_SPENDING_CATEGORIES
    ]
    income = [
        transaction
        for transaction in weekly_transactions
        if transaction.direction == "inflow" and not transaction.is_transfer
    ]
    weekly_spending = sum((item.amount for item in spendable), ZERO)
    weekly_income = sum((item.amount for item in income), ZERO)

    category_totals: dict[str, Decimal] = defaultdict(lambda: ZERO)
    day_totals: dict[str, Decimal] = defaultdict(lambda: ZERO)
    for transaction in spendable:
        category_totals[transaction.category] += transaction.amount
        day_totals[transaction.occurred_at.date().isoformat()] += transaction.amount

    category_summaries = [
        SpendingCategorySummary(
            category=category,
            label=category.replace("_", " ").title(),
            amount=amount,
            percent=(amount / weekly_spending * Decimal("100")) if weekly_spending else ZERO,
        )
        for category, amount in sorted(
            category_totals.items(), key=lambda item: (-item[1], item[0])
        )
    ]
    daily_spending = [
        DailySpendingPoint(
            date=(now - timedelta(days=days_ago)).date().isoformat(),
            amount=day_totals[(now - timedelta(days=days_ago)).date().isoformat()],
        )
        for days_ago in range(6, -1, -1)
    ]

    cash_balance = sum(
        (
            account.current_balance
            for account in accounts
            if account.account_type in {"checking", "savings", "cash"}
        ),
        ZERO,
    )
    card_balance = sum(
        (account.current_balance for account in accounts if account.account_type == "credit_card"),
        ZERO,
    )
    monthly_recurring = sum((stream.average_amount for stream in subscriptions), ZERO)

    return MoneyOverviewResponse(
        cash_balance=cash_balance,
        card_balance=card_balance,
        net_cash_position=cash_balance - card_balance,
        weekly_spending=weekly_spending,
        weekly_income=weekly_income,
        monthly_recurring=monthly_recurring,
        annualized_recurring=monthly_recurring * Decimal("12"),
        last_synced_at=max(
            (
                connection.last_synced_at
                for connection in connections
                if connection.last_synced_at is not None
            ),
            default=None,
        ),
        demo_mode=demo_mode,
        spending_by_category=category_summaries,
        daily_spending=daily_spending,
        accounts=accounts,
        recent_transactions=transaction_result.items[:8],
        subscriptions=subscriptions,
    )
