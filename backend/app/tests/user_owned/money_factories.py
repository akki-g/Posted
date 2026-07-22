from dataclasses import replace
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import UUID

from app.money.enums import (
    MoneyAccountType,
    TransactionDirection,
    TransactionSource,
    TransactionStatus,
)
from app.money.models import (
    MoneyAccountIdentity,
    NormalizedTransaction,
    StoredMoneyTransaction,
    TransactionObservation,
)
from app.tests.user_owned.factories import NOW, stable_id

MONEY_ACCOUNTS = {
    "plaid-checking": MoneyAccountIdentity(
        account_id=stable_id("money-checking"),
        account_type=MoneyAccountType.CHECKING,
        display_name="Everyday checking",
    ),
    "plaid-credit": MoneyAccountIdentity(
        account_id=stable_id("money-credit"),
        account_type=MoneyAccountType.CREDIT_CARD,
        display_name="Rewards card",
    ),
}


def resolve_money_account(provider_account_id: str) -> MoneyAccountIdentity | None:
    return MONEY_ACCOUNTS.get(provider_account_id)


def transaction_observation(
    name: str = "coffee",
    *,
    account: str = "plaid-checking",
    amount: str = "6.50",
    direction: TransactionDirection = TransactionDirection.OUTFLOW,
    status: TransactionStatus = TransactionStatus.POSTED,
    merchant: str | None = "  NORTHSTAR   COFFEE  ",
    description: str = "NORTHSTAR COFFEE #104",
    occurred_at: datetime | None = NOW,
    category: str | None = "FOOD_AND_DRINK",
    pending_provider_transaction_id: str | None = None,
) -> TransactionObservation:
    return TransactionObservation(
        source=TransactionSource.PLAID,
        provider_transaction_id=f"tx-{name}",
        provider_account_id=account,
        pending_provider_transaction_id=pending_provider_transaction_id,
        status=status,
        direction=direction,
        amount=Decimal(amount),
        currency="usd",
        merchant_name=merchant,
        description=description,
        authorized_at=occurred_at,
        posted_at=occurred_at if status is TransactionStatus.POSTED else None,
        category_primary=category,
        category_detailed=None,
        payment_channel="in_store",
    )


def normalized_transaction(
    name: str = "coffee",
    **changes: object,
) -> NormalizedTransaction:
    observation = transaction_observation(name)
    account = MONEY_ACCOUNTS[observation.provider_account_id]
    base = NormalizedTransaction(
        account_id=account.account_id,
        account_type=account.account_type,
        source=observation.source,
        provider_transaction_id=observation.provider_transaction_id,
        pending_provider_transaction_id=observation.pending_provider_transaction_id,
        status=observation.status,
        direction=observation.direction,
        amount=observation.amount,
        currency="USD",
        merchant_name="Northstar Coffee",
        description=observation.description,
        occurred_at=NOW,
        posted_at=NOW,
        category_primary=observation.category_primary or "UNCATEGORIZED",
        category_detailed=None,
        payment_channel=observation.payment_channel,
        fingerprint=f"fingerprint-{name}",
    )
    return replace(base, **changes)


def stored_money_transaction(
    name: str = "coffee",
    **changes: object,
) -> StoredMoneyTransaction:
    normalized = normalized_transaction(name)
    values = {
        field: getattr(normalized, field) for field in NormalizedTransaction.__dataclass_fields__
    }
    values.update(changes)
    return StoredMoneyTransaction(
        transaction_id=stable_id(f"money-transaction-{name}"),
        **values,
    )


def recurring_charge(
    name: str,
    *,
    days_ago: int,
    amount: str = "14.99",
    merchant: str = "Streambox",
) -> StoredMoneyTransaction:
    occurred_at = NOW - timedelta(days=days_ago)
    return stored_money_transaction(
        f"{name}-{days_ago}",
        amount=Decimal(amount),
        merchant_name=merchant,
        occurred_at=occurred_at,
        posted_at=occurred_at,
        category_primary="ENTERTAINMENT",
    )


def transaction_id(name: str) -> UUID:
    return stable_id(f"money-transaction-{name}")
