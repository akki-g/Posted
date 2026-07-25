from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, Protocol
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
from app.providers.schwab.mapper import map_schwab_positions
from app.providers.schwab.oauth import OAuthTokenSet, SchwabOAuthClient
from app.security.brokerage_credentials import BrokerageCredentialStore

ZERO = Decimal("0")
TOKEN_REFRESH_BUFFER = timedelta(minutes=2)


class SchwabAccountsClient(Protocol):
    async def get_account_numbers(self) -> list[dict[str, Any]]: ...

    async def get_accounts_with_positions(self) -> list[dict[str, Any]]: ...


SchwabTraderFactory = Callable[[str], SchwabAccountsClient]


class SchwabSyncError(ValueError):
    """A safe, user-readable failure that leaves the last portfolio intact."""


@dataclass(frozen=True, slots=True)
class SchwabSyncSummary:
    sync_run_id: UUID
    status: str
    accounts_seen: int
    positions_seen: int
    positions_changed: int
    positions_rejected: int
    synced_at: datetime
    repeated: bool = False


@dataclass(frozen=True, slots=True)
class _PositionMetrics:
    day_change: Decimal
    total_gain: Decimal


def _aware_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _decimal(value: object) -> Decimal | None:
    if value is None:
        return None
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return result if result.is_finite() else None


def _first_decimal(values: Sequence[object], default: Decimal = ZERO) -> Decimal:
    for value in values:
        parsed = _decimal(value)
        if parsed is not None:
            return parsed
    return default


def _securities_account(raw: dict[str, Any]) -> dict[str, Any]:
    account = raw.get("securitiesAccount", raw)
    if not isinstance(account, dict):
        raise SchwabSyncError("Schwab returned an invalid account object")
    return account


def _account_hashes(raw_numbers: Sequence[dict[str, Any]]) -> dict[str, str]:
    result: dict[str, str] = {}
    for item in raw_numbers:
        account_number = str(item.get("accountNumber") or "").strip()
        hash_value = str(item.get("hashValue") or "").strip()
        if not account_number or not hash_value:
            raise SchwabSyncError("Schwab returned an incomplete account identifier mapping")
        if account_number in result and result[account_number] != hash_value:
            raise SchwabSyncError("Schwab returned conflicting account identifier mappings")
        result[account_number] = hash_value
    return result


def _account_identity(
    raw: dict[str, Any],
    *,
    hashes: dict[str, str],
) -> tuple[str, str, str]:
    account = _securities_account(raw)
    account_number = str(account.get("accountNumber") or "").strip()
    provider_id = hashes.get(account_number)
    if not account_number or not provider_id:
        # Never fall back to persisting the full brokerage account number.
        raise SchwabSyncError("Schwab account could not be matched to its opaque identifier")
    account_type = str(account.get("type") or "Brokerage").strip() or "Brokerage"
    display_type = account_type.replace("_", " ").title()
    return provider_id, f"{display_type} ••{account_number[-4:]}", account_type


def _raw_positions(raw: dict[str, Any]) -> list[dict[str, Any]]:
    positions = _securities_account(raw).get("positions") or []
    if not isinstance(positions, list) or not all(isinstance(item, dict) for item in positions):
        raise SchwabSyncError("Schwab returned an invalid position list")
    return positions


def _position_metrics(raw_positions: Sequence[dict[str, Any]]) -> dict[str, _PositionMetrics]:
    result: dict[str, _PositionMetrics] = {}
    for raw in raw_positions:
        instrument = raw.get("instrument") or {}
        if not isinstance(instrument, dict):
            continue
        symbol = str(instrument.get("symbol") or "").strip().upper()
        if not symbol:
            continue
        prior = result.get(symbol, _PositionMetrics(ZERO, ZERO))
        day_change = _first_decimal((raw.get("currentDayProfitLoss"),))
        total_gain = sum(
            (
                _decimal(raw.get("longOpenProfitLoss")) or ZERO,
                _decimal(raw.get("shortOpenProfitLoss")) or ZERO,
            ),
            ZERO,
        )
        result[symbol] = _PositionMetrics(
            day_change=prior.day_change + day_change,
            total_gain=prior.total_gain + total_gain,
        )
    return result


def _account_values(raw: dict[str, Any]) -> tuple[Decimal, Decimal, Decimal]:
    account = _securities_account(raw)
    balances = account.get("currentBalances") or {}
    if not isinstance(balances, dict):
        balances = {}
    positions = _raw_positions(raw)
    metrics = _position_metrics(positions)
    day_change = sum((item.day_change for item in metrics.values()), ZERO)
    total_gain = sum((item.total_gain for item in metrics.values()), ZERO)
    balance = next(
        (
            parsed
            for value in (
                balances.get("liquidationValue"),
                balances.get("equity"),
                balances.get("accountValue"),
            )
            if (parsed := _decimal(value)) is not None
        ),
        None,
    )
    if balance is None:
        raise SchwabSyncError("Schwab account is missing a usable total balance")
    return balance, day_change, total_gain


def _security_names(raw_accounts: Sequence[dict[str, Any]]) -> dict[str, str]:
    names: dict[str, str] = {}
    for raw_account in raw_accounts:
        for raw_position in _raw_positions(raw_account):
            instrument = raw_position.get("instrument") or {}
            if not isinstance(instrument, dict):
                continue
            symbol = str(instrument.get("symbol") or "").strip().upper()
            description = str(
                instrument.get("description")
                or instrument.get("assetType")
                or symbol
            ).strip()
            if symbol:
                names.setdefault(symbol, description or symbol)
    return names


async def _valid_access_token(
    session: AsyncSession,
    *,
    connection_id: UUID,
    credential_store: BrokerageCredentialStore,
    oauth_client: SchwabOAuthClient,
    as_of: datetime,
) -> str:
    stored = await credential_store.load(connection_id=connection_id)
    # End the implicit read transaction before any provider request.
    await session.commit()
    if stored is None:
        raise SchwabSyncError("Reconnect Schwab before synchronizing this portfolio")
    if (
        stored.expires_at is not None
        and _aware_utc(stored.expires_at) > as_of + TOKEN_REFRESH_BUFFER
    ):
        return stored.access_token
    if not stored.refresh_token:
        raise SchwabSyncError("Schwab authorization expired; reconnect the account")

    refreshed = await oauth_client.refresh(refresh_token=stored.refresh_token)
    if refreshed.refresh_token is None:
        refreshed = OAuthTokenSet(
            access_token=refreshed.access_token,
            refresh_token=stored.refresh_token,
            token_type=refreshed.token_type,
            expires_in=refreshed.expires_in,
            scope=refreshed.scope,
            obtained_at=refreshed.obtained_at,
        )
    await credential_store.save(
        connection_id=connection_id,
        access_token=refreshed.access_token,
        refresh_token=refreshed.refresh_token,
        token_type=refreshed.token_type,
        scope=refreshed.scope,
        expires_at=refreshed.expires_at,
    )
    await session.commit()
    return refreshed.access_token


async def _prior_summary(
    session: AsyncSession,
    *,
    connection_id: UUID,
    idempotency_key: str,
) -> SchwabSyncSummary | None:
    existing = await session.scalar(
        select(SyncRun).where(
            SyncRun.connection_id == connection_id,
            SyncRun.idempotency_key == idempotency_key,
        )
    )
    if existing is None:
        return None
    if existing.status not in {"completed", "completed_with_warnings"}:
        raise SchwabSyncError(
            "This synchronization key was already used by a non-completed run; use a new key"
        )
    counts = existing.counts
    return SchwabSyncSummary(
        sync_run_id=existing.id,
        status=existing.status,
        accounts_seen=counts.get("accounts_seen", 0),
        positions_seen=counts.get("positions_seen", 0),
        positions_changed=counts.get("positions_changed", 0),
        positions_rejected=counts.get("positions_rejected", 0),
        synced_at=_aware_utc(existing.completed_at or existing.started_at),
        repeated=True,
    )


async def _persist_snapshot(
    session: AsyncSession,
    *,
    connection: BrokerageConnection,
    run: SyncRun,
    raw_accounts: Sequence[dict[str, Any]],
    hashes: dict[str, str],
    as_of: datetime,
) -> SchwabSyncSummary:
    if not raw_accounts:
        raise SchwabSyncError("Schwab returned no brokerage accounts")

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

    account_rows: list[tuple[BrokerageAccount, dict[str, Any]]] = []
    current_provider_ids: set[str] = set()
    for raw in raw_accounts:
        provider_id, display_name, account_type = _account_identity(raw, hashes=hashes)
        if provider_id in current_provider_ids:
            raise SchwabSyncError("Schwab returned a duplicate brokerage account")
        current_provider_ids.add(provider_id)
        balance, day_change, total_gain = _account_values(raw)
        account = existing_by_provider_id.get(provider_id)
        if account is None:
            account = BrokerageAccount(
                connection_id=connection.id,
                provider_account_id=provider_id,
                display_name=display_name,
                account_type=account_type,
                balance=balance,
                day_change=day_change,
                total_gain=total_gain,
            )
            session.add(account)
        else:
            account.display_name = display_name
            account.account_type = account_type
            account.balance = balance
            account.day_change = day_change
            account.total_gain = total_gain
        account_rows.append((account, raw))
    await session.flush()

    observations = tuple(
        observation
        for account, raw in account_rows
        for observation in map_schwab_positions(
            raw,
            account_id=account.id,
            observed_at=as_of,
        )
    )
    names = _security_names(raw_accounts)
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
        (account.id, symbol): metrics
        for account, raw in account_rows
        for symbol, metrics in _position_metrics(_raw_positions(raw)).items()
    }
    total_value = sum((account.balance for account, _raw in account_rows), ZERO)
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
            _PositionMetrics(ZERO, ZERO),
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

    day_change = sum((account.day_change for account, _raw in account_rows), ZERO)
    total_gain = sum((account.total_gain for account, _raw in account_rows), ZERO)
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
        "accounts_seen": len(account_rows),
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
    return SchwabSyncSummary(
        sync_run_id=run.id,
        status=status,
        accounts_seen=len(account_rows),
        positions_seen=len(observations),
        positions_changed=changed,
        positions_rejected=len(reconciliation.rejected),
        synced_at=as_of,
    )


async def sync_schwab_connection(
    session: AsyncSession,
    *,
    connection: BrokerageConnection,
    idempotency_key: str,
    credential_store: BrokerageCredentialStore,
    oauth_client: SchwabOAuthClient,
    trader_factory: SchwabTraderFactory,
    as_of: datetime | None = None,
) -> SchwabSyncSummary:
    """Refresh credentials, fetch a complete snapshot, and atomically replace holdings."""

    normalized_key = idempotency_key.strip()
    if len(normalized_key) < 8:
        raise SchwabSyncError("idempotency_key must contain at least eight characters")
    as_of = as_of or datetime.now(UTC)
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise SchwabSyncError("as_of must be timezone-aware")
    as_of = as_of.astimezone(UTC)

    prior = await _prior_summary(
        session,
        connection_id=connection.id,
        idempotency_key=normalized_key,
    )
    if prior is not None:
        return prior

    run = SyncRun(
        id=uuid4(),
        connection_id=connection.id,
        status="requested",
        idempotency_key=normalized_key,
        trigger="manual",
        started_at=as_of,
        counts={},
        warnings=[],
    )
    session.add(run)
    await session.commit()

    try:
        access_token = await _valid_access_token(
            session,
            connection_id=connection.id,
            credential_store=credential_store,
            oauth_client=oauth_client,
            as_of=as_of,
        )
        trader = trader_factory(access_token)
        raw_numbers = await trader.get_account_numbers()
        raw_accounts = await trader.get_accounts_with_positions()
        hashes = _account_hashes(raw_numbers)
        return await _persist_snapshot(
            session,
            connection=connection,
            run=run,
            raw_accounts=raw_accounts,
            hashes=hashes,
            as_of=as_of,
        )
    except Exception as exc:
        await session.rollback()
        failed_run = await session.get(SyncRun, run.id)
        failed_connection = await session.get(BrokerageConnection, connection.id)
        if failed_run is not None:
            failed_run.status = "failed"
            failed_run.completed_at = datetime.now(UTC)
            failed_run.warnings = [
                {
                    "code": "schwab_sync_failed",
                    "message": (
                        str(exc)
                        if isinstance(exc, SchwabSyncError)
                        else "Schwab synchronization failed"
                    ),
                }
            ]
        if failed_connection is not None:
            failed_connection.status = "error"
        await session.commit()
        if isinstance(exc, SchwabSyncError):
            raise
        raise SchwabSyncError(
            "Schwab synchronization failed; the prior portfolio was kept"
        ) from exc
