from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    BrokerageAccount,
    BrokerageConnection,
    PortfolioSnapshot,
    Position,
    Security,
    SyncRun,
)
from app.domain.enums import AssetType, PositionChangeKind
from app.domain.models import PositionObservation, SecurityIdentity, StoredPosition
from app.portfolio.reconcile import reconcile_positions

ZERO = Decimal("0")


class BrokerageSyncError(ValueError):
    """A safe, user-readable failure that leaves the last portfolio intact."""


@dataclass(frozen=True, slots=True)
class PositionMetrics:
    day_change: Decimal
    total_gain: Decimal


@dataclass(frozen=True, slots=True)
class RawBrokerageAccount:
    provider_account_id: str
    display_name: str
    account_type: str
    balance: Decimal
    day_change: Decimal
    total_gain: Decimal
    positions: tuple[PositionObservation, ...]
    security_names: dict[str, str]
    metrics: dict[str, PositionMetrics]


@dataclass(frozen=True, slots=True)
class BrokerageSyncSummary:
    sync_run_id: UUID
    status: str
    accounts_seen: int
    positions_seen: int
    positions_changed: int
    positions_rejected: int
    synced_at: datetime
    repeated: bool = False


def _aware_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


async def prior_summary(
    session: AsyncSession,
    *,
    connection_id: UUID,
    idempotency_key: str,
) -> BrokerageSyncSummary | None:
    existing = await session.scalar(
        select(SyncRun).where(
            SyncRun.connection_id == connection_id,
            SyncRun.idempotency_key == idempotency_key,
        )
    )
    if existing is None:
        return None
    if existing.status not in {"completed", "completed_with_warnings"}:
        raise BrokerageSyncError(
            "This synchronization key was already used by a non-completed run; use a new key"
        )
    counts = existing.counts
    return BrokerageSyncSummary(
        sync_run_id=existing.id,
        status=existing.status,
        accounts_seen=counts.get("accounts_seen", 0),
        positions_seen=counts.get("positions_seen", 0),
        positions_changed=counts.get("positions_changed", 0),
        positions_rejected=counts.get("positions_rejected", 0),
        synced_at=_aware_utc(existing.completed_at or existing.started_at),
        repeated=True,
    )


async def record_failed_run(
    session: AsyncSession,
    *,
    connection: BrokerageConnection,
    idempotency_key: str,
    message: str,
    as_of: datetime,
) -> None:
    run = SyncRun(
        id=uuid4(),
        connection_id=connection.id,
        status="failed",
        idempotency_key=idempotency_key.strip(),
        trigger="manual",
        started_at=as_of,
        completed_at=as_of,
        counts={},
        warnings=[{"code": "brokerage_sync_failed", "message": message}],
    )
    session.add(run)
    connection.status = "error"
    await session.commit()


async def sync_brokerage_snapshot(
    session: AsyncSession,
    *,
    connection: BrokerageConnection,
    idempotency_key: str,
    accounts: Sequence[RawBrokerageAccount],
    as_of: datetime | None = None,
) -> BrokerageSyncSummary:
    normalized_key = idempotency_key.strip()
    if len(normalized_key) < 8:
        raise BrokerageSyncError("idempotency_key must contain at least eight characters")
    as_of = as_of or datetime.now(UTC)
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise BrokerageSyncError("as_of must be timezone-aware")
    as_of = as_of.astimezone(UTC)

    prior = await prior_summary(
        session, connection_id=connection.id, idempotency_key=normalized_key
    )
    if prior is not None:
        return prior

    run = SyncRun(
        id=uuid4(), connection_id=connection.id, status="requested",
        idempotency_key=normalized_key, trigger="manual", started_at=as_of,
        counts={}, warnings=[],
    )
    session.add(run)
    await session.commit()
    try:
        return await _persist(
            session, connection=connection, run=run, accounts=accounts, as_of=as_of
        )
    except Exception as exc:
        await session.rollback()
        failed_run = await session.get(SyncRun, run.id)
        failed_connection = await session.get(BrokerageConnection, connection.id)
        if failed_run is not None:
            failed_run.status = "failed"
            failed_run.completed_at = datetime.now(UTC)
            failed_run.warnings = [{
                "code": "brokerage_sync_failed",
                "message": str(exc) if isinstance(exc, BrokerageSyncError)
                else "Portfolio synchronization failed",
            }]
        if failed_connection is not None:
            failed_connection.status = "error"
        await session.commit()
        if isinstance(exc, BrokerageSyncError):
            raise
        raise BrokerageSyncError(
            "Portfolio synchronization failed; the prior portfolio was kept"
        ) from exc


async def _persist(
    session: AsyncSession,
    *,
    connection: BrokerageConnection,
    run: SyncRun,
    accounts: Sequence[RawBrokerageAccount],
    as_of: datetime,
) -> BrokerageSyncSummary:
    if not accounts:
        raise BrokerageSyncError("The brokerage returned no accounts")

    existing_accounts_result = await session.scalars(
        select(BrokerageAccount).where(BrokerageAccount.connection_id == connection.id)
    )
    existing_accounts = list(existing_accounts_result.all())
    existing_by_provider_id = {
        account.provider_account_id: account for account in existing_accounts
    }
    had_demo_accounts = any(
        account.provider_account_id.startswith("demo-") for account in existing_accounts
    )

    account_by_provider_id: dict[str, BrokerageAccount] = {}
    current_provider_ids: set[str] = set()
    for raw in accounts:
        provider_id = raw.provider_account_id
        if provider_id in current_provider_ids:
            raise BrokerageSyncError("The brokerage returned a duplicate brokerage account")
        current_provider_ids.add(provider_id)
        account = existing_by_provider_id.get(provider_id)
        if account is None:
            account = BrokerageAccount(
                connection_id=connection.id,
                provider_account_id=provider_id,
                display_name=raw.display_name,
                account_type=raw.account_type,
                balance=raw.balance,
                day_change=raw.day_change,
                total_gain=raw.total_gain,
            )
            session.add(account)
        else:
            account.display_name = raw.display_name
            account.account_type = raw.account_type
            account.balance = raw.balance
            account.day_change = raw.day_change
            account.total_gain = raw.total_gain
        account_by_provider_id[provider_id] = account
    await session.flush()

    observations = tuple(
        replace(obs, account_id=account_by_provider_id[raw.provider_account_id].id)
        for raw in accounts
        for obs in raw.positions
    )
    names: dict[str, str] = {}
    for raw in accounts:
        names.update(raw.security_names)
    symbols = sorted(
        {
            observation.symbol
            for observation in observations
            if observation.symbol
            and observation.asset_type in {AssetType.EQUITY, AssetType.ETF}
        }
    )
    security_result = await session.scalars(select(Security).where(Security.symbol.in_(symbols)))
    security_by_symbol = {security.symbol: security for security in security_result.all()}
    asset_type_by_symbol = {
        observation.symbol: observation.asset_type
        for observation in observations
        if observation.symbol
    }
    for symbol in symbols:
        if symbol in security_by_symbol:
            continue
        security = Security(
            symbol=symbol,
            name=names.get(symbol, symbol),
            asset_type=asset_type_by_symbol[symbol].value,
        )
        session.add(security)
        security_by_symbol[symbol] = security
    await session.flush()

    def resolve_security(observation: PositionObservation) -> SecurityIdentity | None:
        security = security_by_symbol.get(observation.symbol or "")
        if security is None:
            return None
        return SecurityIdentity(
            security_id=security.id,
            canonical_symbol=security.symbol,
        )

    previous_result = await session.execute(
        select(Position, Security)
        .join(Security, Position.security_id == Security.id)
        .join(BrokerageAccount, Position.account_id == BrokerageAccount.id)
        .where(BrokerageAccount.connection_id == connection.id)
    )
    previous_rows = list(previous_result.all())
    previous = tuple(
        StoredPosition(
            position_id=position.id,
            account_id=position.account_id,
            security_id=position.security_id,
            canonical_symbol=security.symbol,
            quantity=position.quantity,
            market_value=position.market_value,
            average_price=position.average_price,
        )
        for position, security in previous_rows
    )
    reconciliation = reconcile_positions(
        observations=observations,
        previous=previous,
        resolve_security=resolve_security,
    )

    current_keys = {
        (position.account_id, position.security_id)
        for position in reconciliation.positions
    }
    existing_position_by_key = {
        (position.account_id, position.security_id): position
        for position, _security in previous_rows
    }
    for key, record in existing_position_by_key.items():
        if key not in current_keys:
            await session.delete(record)

    metrics_by_account_symbol = {
        (account_by_provider_id[raw.provider_account_id].id, symbol): m
        for raw in accounts
        for symbol, m in raw.metrics.items()
    }
    total_value = sum((account.balance for account in account_by_provider_id.values()), ZERO)
    for current in reconciliation.positions:
        record = existing_position_by_key.get((current.account_id, current.security_id))
        if record is None:
            record = Position(
                account_id=current.account_id,
                security_id=current.security_id,
            )
            session.add(record)
        metrics = metrics_by_account_symbol.get(
            (current.account_id, current.canonical_symbol),
            PositionMetrics(ZERO, ZERO),
        )
        market_value = current.market_value or ZERO
        record.quantity = current.quantity
        record.average_price = current.average_price
        record.last_price = (
            market_value / current.quantity if current.quantity != ZERO else None
        )
        record.market_value = market_value
        record.day_change = metrics.day_change
        previous_value = market_value - metrics.day_change
        record.day_change_percent = (
            metrics.day_change / previous_value * Decimal("100")
            if previous_value
            else ZERO
        )
        record.total_gain = metrics.total_gain
        cost = market_value - metrics.total_gain
        record.total_gain_percent = (
            metrics.total_gain / cost * Decimal("100") if cost else ZERO
        )
        record.portfolio_weight = (
            market_value / total_value * Decimal("100") if total_value else ZERO
        )

    stale_account_ids = [
        account.id
        for account in existing_accounts
        if account.provider_account_id not in current_provider_ids
    ]
    if stale_account_ids:
        await session.execute(
            delete(Position).where(Position.account_id.in_(stale_account_ids))
        )
        await session.execute(
            delete(BrokerageAccount).where(BrokerageAccount.id.in_(stale_account_ids))
        )
    if had_demo_accounts:
        # Demo history must not be presented as real performance after the
        # first successful live synchronization.
        await session.execute(
            delete(PortfolioSnapshot).where(
                PortfolioSnapshot.user_id == connection.user_id
            )
        )

    day_change = sum((account.day_change for account in account_by_provider_id.values()), ZERO)
    total_gain = sum((account.total_gain for account in account_by_provider_id.values()), ZERO)
    prior_value = total_value - day_change
    cost = total_value - total_gain
    session.add(
        PortfolioSnapshot(
            user_id=connection.user_id,
            observed_at=as_of,
            total_value=total_value,
            day_change=day_change,
            day_change_percent=(
                day_change / prior_value * Decimal("100") if prior_value else ZERO
            ),
            total_gain=total_gain,
            total_gain_percent=(
                total_gain / cost * Decimal("100") if cost else ZERO
            ),
        )
    )

    changed = sum(
        delta.kind is not PositionChangeKind.UNCHANGED
        for delta in reconciliation.deltas
    )
    warnings = [
        {
            "code": rejection.reason.value,
            "message": rejection.detail,
            "symbol": rejection.observation.symbol,
        }
        for rejection in reconciliation.rejected
    ]
    status = "completed_with_warnings" if warnings else "completed"
    counts = {
        "accounts_seen": len(account_by_provider_id),
        "positions_seen": len(observations),
        "positions_changed": changed,
        "positions_rejected": len(reconciliation.rejected),
    }
    run.status = status
    run.completed_at = as_of
    run.counts = counts
    run.warnings = warnings
    connection.status = "connected"
    connection.last_synced_at = as_of
    await session.commit()
    return BrokerageSyncSummary(
        sync_run_id=run.id,
        status=status,
        accounts_seen=len(account_by_provider_id),
        positions_seen=len(observations),
        positions_changed=changed,
        positions_rejected=len(reconciliation.rejected),
        synced_at=as_of,
    )
