from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Protocol
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import (
    FinancialAccount,
    FinancialConnection,
    MoneyTransactionRecord,
    RecurringStream,
)
from app.money.enums import (
    LedgerActionKind,
    MoneyAccountType,
    SpendingTreatment,
    TransactionDirection,
    TransactionSource,
    TransactionStatus,
)
from app.money.models import (
    MoneyAccountIdentity,
    NormalizedTransaction,
    ProviderTransactionRef,
    StoredMoneyTransaction,
)
from app.money.normalize import normalize_transactions
from app.money.reconcile import reconcile_ledger
from app.money.recurring import detect_recurring_transactions
from app.money.spending import summarize_weekly_spending
from app.providers.plaid.client import PlaidSyncPage
from app.providers.plaid.mapper import map_plaid_account_values, map_plaid_transaction


class PlaidTransactionClient(Protocol):
    async def sync_transactions(
        self,
        access_token: str,
        *,
        cursor: str | None = None,
    ) -> PlaidSyncPage: ...


class PlaidMoneyClient(PlaidTransactionClient, Protocol):
    async def get_accounts(self, access_token: str) -> tuple[dict[str, object], ...]: ...


class PlaidSyncError(ValueError):
    """Raised when advancing the cursor would discard unusable provider data."""


logger = structlog.get_logger()


@dataclass(frozen=True, slots=True)
class PlaidSyncSummary:
    inserted: int
    updated: int
    deleted: int
    unchanged: int
    replaced_pending: int
    normalized: int
    rejected: int
    synced_at: datetime
    cursor: str


def _aware_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _account_type(value: str) -> MoneyAccountType:
    try:
        return MoneyAccountType(value)
    except ValueError:
        return MoneyAccountType.OTHER


def _stored(record: MoneyTransactionRecord) -> StoredMoneyTransaction:
    return StoredMoneyTransaction(
        transaction_id=record.id,
        account_id=record.account_id,
        account_type=_account_type(record.account.account_type),
        source=TransactionSource(record.source),
        provider_transaction_id=record.provider_transaction_id,
        pending_provider_transaction_id=record.pending_provider_transaction_id,
        status=TransactionStatus(record.status),
        direction=TransactionDirection(record.direction),
        amount=record.amount,
        currency=record.currency,
        merchant_name=record.merchant_name,
        description=record.description,
        occurred_at=_aware_utc(record.occurred_at),
        posted_at=_aware_utc(record.posted_at) if record.posted_at else None,
        category_primary=record.category_primary,
        category_detailed=record.category_detailed,
        payment_channel=record.payment_channel,
        fingerprint=record.fingerprint,
    )


def _apply_values(
    record: MoneyTransactionRecord,
    transaction: NormalizedTransaction,
) -> None:
    record.account_id = transaction.account_id
    record.source = transaction.source.value
    record.provider_transaction_id = transaction.provider_transaction_id
    record.pending_provider_transaction_id = transaction.pending_provider_transaction_id
    record.status = transaction.status.value
    record.direction = transaction.direction.value
    record.amount = transaction.amount
    record.currency = transaction.currency
    record.merchant_name = transaction.merchant_name
    record.description = transaction.description
    record.occurred_at = transaction.occurred_at
    record.posted_at = transaction.posted_at
    record.category_primary = transaction.category_primary
    record.category_detailed = transaction.category_detailed
    record.payment_channel = transaction.payment_channel
    record.fingerprint = transaction.fingerprint


async def _fetch_changes(
    client: PlaidTransactionClient,
    *,
    access_token: str,
    cursor: str | None,
) -> tuple[list[dict[str, object]], list[dict[str, object]], str]:
    changed: list[dict[str, object]] = []
    removed: list[dict[str, object]] = []
    next_cursor = cursor

    # A hard cap protects the worker from a malformed provider response that keeps
    # returning has_more without moving its cursor.
    for _ in range(100):
        page = await client.sync_transactions(access_token, cursor=next_cursor)
        changed.extend(page.added)
        changed.extend(page.modified)
        removed.extend(page.removed)
        if page.next_cursor == next_cursor and page.has_more:
            raise PlaidSyncError("Plaid pagination cursor did not advance")
        next_cursor = page.next_cursor
        if not page.has_more:
            return changed, removed, next_cursor
    raise PlaidSyncError("Plaid transaction sync exceeded 100 pages")


async def _refresh_analytics(
    session: AsyncSession,
    *,
    user_id: UUID,
    as_of: datetime,
) -> None:
    result = await session.scalars(
        select(MoneyTransactionRecord)
        .join(FinancialAccount)
        .join(FinancialConnection)
        .where(FinancialConnection.user_id == user_id)
        .options(selectinload(MoneyTransactionRecord.account))
        .order_by(MoneyTransactionRecord.occurred_at, MoneyTransactionRecord.id)
    )
    records = list(result.all())
    if not records:
        return

    stored = tuple(_stored(record) for record in records)
    period_start = min(item.occurred_at for item in stored)
    spending = summarize_weekly_spending(
        stored,
        period_start=period_start,
        period_end=as_of,
    )
    treatments = {decision.transaction_id: decision.treatment for decision in spending.decisions}
    recurring = detect_recurring_transactions(stored, as_of=as_of)
    recurring_ids = {
        transaction_id for stream in recurring.streams for transaction_id in stream.transaction_ids
    }

    for record in records:
        record.is_transfer = treatments.get(record.id) is SpendingTreatment.INTERNAL_TRANSFER
        record.is_recurring = record.id in recurring_ids

    existing_result = await session.scalars(
        select(RecurringStream).where(RecurringStream.user_id == user_id)
    )
    existing_by_key = {stream.stream_key: stream for stream in existing_result.all()}
    active_keys = set()
    for candidate in recurring.streams:
        active_keys.add(candidate.stream_key)
        stream = existing_by_key.get(candidate.stream_key)
        if stream is None:
            stream = RecurringStream(
                user_id=user_id,
                stream_key=candidate.stream_key,
                is_demo=False,
            )
            session.add(stream)
        stream.merchant_name = candidate.merchant_name
        stream.frequency = candidate.frequency.value
        stream.average_amount = candidate.average_amount
        stream.last_amount = candidate.last_amount
        stream.currency = candidate.currency
        stream.last_charged_at = candidate.last_charged_at
        stream.next_expected_date = candidate.next_expected_date
        stream.confidence = Decimal(str(candidate.confidence))
        stream.status = "active"

    for stream_key, stream in existing_by_key.items():
        if stream_key not in active_keys and not stream.is_demo:
            stream.status = "inactive"


async def sync_plaid_transactions(
    session: AsyncSession,
    *,
    connection: FinancialConnection,
    access_token: str,
    client: PlaidTransactionClient,
    as_of: datetime | None = None,
) -> PlaidSyncSummary:
    """Fetch, normalize, reconcile, persist, and analyze one Plaid cursor update."""

    as_of = as_of or datetime.now(UTC)
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise PlaidSyncError("as_of must be timezone-aware")
    as_of = as_of.astimezone(UTC)
    account_result = await session.scalars(
        select(FinancialAccount).where(FinancialAccount.connection_id == connection.id)
    )
    accounts = list(account_result.all())
    account_by_provider_id = {account.provider_account_id: account for account in accounts}

    changed_raw, removed_raw, next_cursor = await _fetch_changes(
        client,
        access_token=access_token,
        cursor=connection.cursor,
    )
    observations = tuple(map_plaid_transaction(raw) for raw in changed_raw)

    def resolve_account(provider_account_id: str) -> MoneyAccountIdentity | None:
        account = account_by_provider_id.get(provider_account_id)
        if account is None:
            return None
        return MoneyAccountIdentity(
            account_id=account.id,
            account_type=_account_type(account.account_type),
            display_name=account.display_name,
        )

    normalized = normalize_transactions(observations, resolve_account=resolve_account)
    if normalized.rejected:
        reasons = sorted({item.reason.value for item in normalized.rejected})
        logger.warning(
            "plaid_transactions_rejected",
            connection_id=str(connection.id),
            rejected_count=len(normalized.rejected),
            reasons=reasons,
        )

    existing_result = await session.scalars(
        select(MoneyTransactionRecord)
        .where(MoneyTransactionRecord.account_id.in_([account.id for account in accounts]))
        .options(selectinload(MoneyTransactionRecord.account))
    )
    existing_records = list(existing_result.all())
    existing_by_id = {record.id: record for record in existing_records}
    removed = tuple(
        ProviderTransactionRef(
            source=TransactionSource.PLAID,
            provider_transaction_id=str(item["transaction_id"]),
        )
        for item in removed_raw
        if item.get("transaction_id")
    )
    plan = reconcile_ledger(
        incoming=normalized.transactions,
        existing=tuple(_stored(record) for record in existing_records),
        removed=removed,
    )

    counts = {kind.value: 0 for kind in LedgerActionKind}
    for action in plan.actions:
        counts[action.kind.value] += 1
        if action.kind is LedgerActionKind.INSERT:
            if action.transaction is None:
                raise PlaidSyncError("insert action is missing its transaction")
            record = MoneyTransactionRecord(is_transfer=False, is_recurring=False, is_demo=False)
            _apply_values(record, action.transaction)
            session.add(record)
        elif action.kind is LedgerActionKind.DELETE:
            if action.existing_transaction_id is not None:
                record = existing_by_id[action.existing_transaction_id]
                await session.delete(record)
        elif action.kind in {LedgerActionKind.UPDATE, LedgerActionKind.REPLACE_PENDING}:
            if action.existing_transaction_id is None or action.transaction is None:
                raise PlaidSyncError("update action is missing its stored or incoming record")
            _apply_values(existing_by_id[action.existing_transaction_id], action.transaction)

    await session.flush()
    await _refresh_analytics(session, user_id=connection.user_id, as_of=as_of)
    connection.cursor = next_cursor
    connection.last_synced_at = as_of
    connection.status = "connected"
    await session.commit()

    return PlaidSyncSummary(
        inserted=counts[LedgerActionKind.INSERT.value],
        updated=counts[LedgerActionKind.UPDATE.value],
        deleted=counts[LedgerActionKind.DELETE.value],
        unchanged=counts[LedgerActionKind.UNCHANGED.value],
        replaced_pending=counts[LedgerActionKind.REPLACE_PENDING.value],
        normalized=len(normalized.transactions),
        rejected=len(normalized.rejected),
        synced_at=as_of,
        cursor=next_cursor,
    )


async def sync_plaid_money_connection(
    session: AsyncSession,
    *,
    connection: FinancialConnection,
    access_token: str,
    client: PlaidMoneyClient,
    as_of: datetime | None = None,
) -> PlaidSyncSummary:
    """Refresh account balances, then sync transactions, for one Plaid money connection."""

    raw_accounts = await client.get_accounts(access_token)
    for raw_account in raw_accounts:
        provider_account_id = str(raw_account.get("account_id") or "")
        if not provider_account_id:
            continue
        account = await session.scalar(
            select(FinancialAccount).where(
                FinancialAccount.connection_id == connection.id,
                FinancialAccount.provider_account_id == provider_account_id,
            )
        )
        values = map_plaid_account_values(raw_account)
        if account is None:
            session.add(
                FinancialAccount(
                    connection_id=connection.id,
                    provider_account_id=provider_account_id,
                    **values,
                )
            )
        else:
            for name, value in values.items():
                setattr(account, name, value)
    await session.flush()

    return await sync_plaid_transactions(
        session, connection=connection, access_token=access_token, client=client, as_of=as_of
    )
