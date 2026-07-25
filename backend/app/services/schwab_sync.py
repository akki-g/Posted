from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, Protocol
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import BrokerageConnection
from app.providers.schwab.mapper import map_schwab_positions
from app.providers.schwab.oauth import OAuthTokenSet, SchwabOAuthClient
from app.security.brokerage_credentials import BrokerageCredentialStore
from app.services.brokerage_sync import (
    BrokerageSyncError,
    BrokerageSyncSummary,
    PositionMetrics,
    RawBrokerageAccount,
    prior_summary,
    record_failed_run,
    sync_brokerage_snapshot,
)

ZERO = Decimal("0")
TOKEN_REFRESH_BUFFER = timedelta(minutes=2)


class SchwabAccountsClient(Protocol):
    async def get_account_numbers(self) -> list[dict[str, Any]]: ...

    async def get_accounts_with_positions(self) -> list[dict[str, Any]]: ...


SchwabTraderFactory = Callable[[str], SchwabAccountsClient]


class SchwabSyncError(BrokerageSyncError):
    """A safe, user-readable Schwab failure that leaves the last portfolio intact."""


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


def _position_metrics(raw_positions: Sequence[dict[str, Any]]) -> dict[str, PositionMetrics]:
    result: dict[str, PositionMetrics] = {}
    for raw in raw_positions:
        instrument = raw.get("instrument") or {}
        if not isinstance(instrument, dict):
            continue
        symbol = str(instrument.get("symbol") or "").strip().upper()
        if not symbol:
            continue
        prior = result.get(symbol, PositionMetrics(ZERO, ZERO))
        day_change = _first_decimal((raw.get("currentDayProfitLoss"),))
        total_gain = sum(
            (
                _decimal(raw.get("longOpenProfitLoss")) or ZERO,
                _decimal(raw.get("shortOpenProfitLoss")) or ZERO,
            ),
            ZERO,
        )
        result[symbol] = PositionMetrics(
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


def _to_raw_accounts(
    raw_accounts: Sequence[dict[str, Any]], *, hashes: dict[str, str], as_of: datetime
) -> list[RawBrokerageAccount]:
    names = _security_names(raw_accounts)
    result: list[RawBrokerageAccount] = []
    for raw in raw_accounts:
        provider_id, display_name, account_type = _account_identity(raw, hashes=hashes)
        balance, day_change, total_gain = _account_values(raw)
        placeholder = uuid4()
        observations = map_schwab_positions(raw, account_id=placeholder, observed_at=as_of)
        metrics = {
            symbol: PositionMetrics(day_change=m.day_change, total_gain=m.total_gain)
            for symbol, m in _position_metrics(_raw_positions(raw)).items()
        }
        symbols = {obs.symbol for obs in observations if obs.symbol}
        result.append(RawBrokerageAccount(
            provider_account_id=provider_id, display_name=display_name,
            account_type=account_type, balance=balance, day_change=day_change,
            total_gain=total_gain, positions=observations,
            security_names={s: names.get(s, s) for s in symbols},
            metrics=metrics,
        ))
    return result


async def sync_schwab_connection(
    session: AsyncSession,
    *,
    connection: BrokerageConnection,
    idempotency_key: str,
    credential_store: BrokerageCredentialStore,
    oauth_client: SchwabOAuthClient,
    trader_factory: SchwabTraderFactory,
    as_of: datetime | None = None,
) -> BrokerageSyncSummary:
    """Refresh credentials, fetch a complete snapshot, and atomically replace holdings."""

    if as_of is not None and (as_of.tzinfo is None or as_of.utcoffset() is None):
        raise SchwabSyncError("as_of must be timezone-aware")
    as_of = (as_of or datetime.now(UTC)).astimezone(UTC)
    prior = await prior_summary(
        session, connection_id=connection.id, idempotency_key=idempotency_key.strip()
    )
    if prior is not None:
        return prior
    try:
        access_token = await _valid_access_token(
            session, connection_id=connection.id, credential_store=credential_store,
            oauth_client=oauth_client, as_of=as_of,
        )
        trader = trader_factory(access_token)
        raw_numbers = await trader.get_account_numbers()
        raw_accounts = await trader.get_accounts_with_positions()
        hashes = _account_hashes(raw_numbers)
        accounts = _to_raw_accounts(raw_accounts, hashes=hashes, as_of=as_of)
    except SchwabSyncError as exc:
        await record_failed_run(
            session, connection=connection, idempotency_key=idempotency_key,
            message=str(exc), as_of=datetime.now(UTC),
        )
        raise
    except Exception as exc:
        await record_failed_run(
            session, connection=connection, idempotency_key=idempotency_key,
            message="Schwab synchronization failed", as_of=datetime.now(UTC),
        )
        raise SchwabSyncError(
            "Schwab synchronization failed; the prior portfolio was kept"
        ) from exc
    return await sync_brokerage_snapshot(
        session, connection=connection, idempotency_key=idempotency_key,
        accounts=accounts, as_of=as_of,
    )
