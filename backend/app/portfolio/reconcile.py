"""Human-owned portfolio reconciliation exercise.

Implementation contract: guides/01-PORTFOLIO-RECONCILIATION.md.
The coding agent must not implement or replace this module unless explicitly asked.
"""

from collections.abc import Sequence
from decimal import Decimal
from typing import Protocol
from uuid import UUID

from app.domain.enums import AssetType, PositionChangeKind, RejectionReason
from app.domain.models import (
    PositionDelta,
    PositionObservation,
    ReconciledPosition,
    ReconciliationResult,
    RejectedObservation,
    SecurityIdentity,
    StoredPosition,
)

ZERO = Decimal("0")
SUPPORTED_ASSET_TYPES = frozenset({AssetType.EQUITY, AssetType.ETF})

PositionKey = tuple[UUID, UUID]


class SecurityResolver(Protocol):
    def __call__(self, observation: PositionObservation) -> SecurityIdentity | None: ...


def reconcile_positions(
    *,
    observations: Sequence[PositionObservation],
    previous: Sequence[StoredPosition],
    resolve_security: SecurityResolver,
) -> ReconciliationResult:
    """Create canonical current positions and deltas from one complete broker snapshot."""

    rejected: list[RejectedObservation] = []
    groups: dict[PositionKey, list[PositionObservation]] = {}
    identity_by_key: dict[PositionKey, SecurityIdentity] = {}

    for observation in observations:
        reason = _rejection_reason(observation)
        if reason is not None:
            rejected.append(
                RejectedObservation(
                    observation=observation,
                    reason=reason,
                    detail=_rejection_detail(reason),
                )
            )
            # Invalid records must not reach resolution or contaminate a valid group.
            continue

        identity = resolve_security(observation)
        if identity is None:
            rejected.append(
                RejectedObservation(
                    observation=observation,
                    reason=RejectionReason.UNRESOLVED_SECURITY,
                    detail="No canonical security matched this observation.",
                )
            )
            # An unresolved record has no security_id, so it cannot form a canonical key.
            continue

        # Provider symbols can change; the account and internal security IDs are stable.
        key = (observation.account_id, identity.security_id)
        groups.setdefault(key, []).append(observation)
        identity_by_key.setdefault(key, identity)

    current_by_key: dict[PositionKey, ReconciledPosition] = {}
    for key, group in groups.items():
        current = _coalesce(group, identity_by_key[key])
        if current is not None:
            current_by_key[key] = current

    previous_by_key: dict[PositionKey, StoredPosition] = {
        (stored.account_id, stored.security_id): stored for stored in previous
    }

    deltas: list[PositionDelta] = []
    # The union is required because a position absent from a complete snapshot is closed.
    for account_id, security_id in set(current_by_key) | set(previous_by_key):
        key = (account_id, security_id)
        old = previous_by_key.get(key)
        new = current_by_key.get(key)

        old_quantity = old.quantity if old is not None else ZERO
        new_quantity = new.quantity if new is not None else ZERO
        deltas.append(
            PositionDelta(
                account_id=account_id,
                security_id=security_id,
                kind=_change_kind(old, new),
                previous_quantity=old_quantity,
                current_quantity=new_quantity,
                quantity_delta=new_quantity - old_quantity,
            )
        )

    return ReconciliationResult(
        positions=tuple(sorted(current_by_key.values(), key=_position_sort_key)),
        deltas=tuple(sorted(deltas, key=_position_sort_key)),
        rejected=tuple(sorted(rejected, key=_rejection_sort_key)),
    )


def _rejection_reason(observation: PositionObservation) -> RejectionReason | None:
    """Return the first validation failure in the contract's required order."""

    if observation.observed_at.tzinfo is None or observation.observed_at.utcoffset() is None:
        return RejectionReason.INVALID_TIMESTAMP
    if observation.quantity < ZERO:
        return RejectionReason.NEGATIVE_QUANTITY
    if observation.asset_type not in SUPPORTED_ASSET_TYPES:
        return RejectionReason.UNSUPPORTED_ASSET_TYPE
    if (
        not observation.symbol
        and not observation.cusip
        and not observation.provider_instrument_id
    ):
        return RejectionReason.MISSING_IDENTITY
    return None


def _rejection_detail(reason: RejectionReason) -> str:
    """Give every validation rejection a specific, human-readable audit message."""

    details = {
        RejectionReason.INVALID_TIMESTAMP: "Observation timestamp must be timezone-aware.",
        RejectionReason.NEGATIVE_QUANTITY: "Negative quantities are not supported.",
        RejectionReason.UNSUPPORTED_ASSET_TYPE: "Only equity and ETF positions are supported.",
        RejectionReason.MISSING_IDENTITY: "Observation has no provider security identifier.",
    }
    return details[reason]


def _coalesce(
    observations: Sequence[PositionObservation],
    identity: SecurityIdentity,
) -> ReconciledPosition | None:
    """Combine observations for one account/security identity into one current position."""

    if not observations:
        raise ValueError("cannot coalesce an empty observation group")

    total_quantity = sum((observation.quantity for observation in observations), ZERO)
    if total_quantity == ZERO:
        return None

    # A partial sum would present incomplete provider data as a complete market value.
    total_market_value = (
        None
        if any(observation.market_value is None for observation in observations)
        else sum(
            (
                observation.market_value
                for observation in observations
                if observation.market_value is not None
            ),
            ZERO,
        )
    )

    if any(observation.average_price is None for observation in observations):
        combined_average_price = None
    else:
        # Quantity weighting preserves each lot's economic contribution to cost basis.
        weighted_cost = sum(
            (
                observation.quantity * observation.average_price
                for observation in observations
                if observation.average_price is not None
            ),
            ZERO,
        )
        combined_average_price = weighted_cost / total_quantity

    first = observations[0]
    return ReconciledPosition(
        account_id=first.account_id,
        security_id=identity.security_id,
        canonical_symbol=identity.canonical_symbol,
        quantity=total_quantity,
        market_value=total_market_value,
        average_price=combined_average_price,
    )


def _change_kind(
    previous: StoredPosition | None,
    current: ReconciledPosition | None,
) -> PositionChangeKind:
    """Classify a position transition using existence first, then quantity."""

    if previous is None and current is None:
        raise AssertionError("a reconciliation key must exist in at least one snapshot")
    if previous is None:
        return PositionChangeKind.OPENED
    if current is None:
        return PositionChangeKind.CLOSED
    if current.quantity > previous.quantity:
        return PositionChangeKind.INCREASED
    if current.quantity < previous.quantity:
        return PositionChangeKind.DECREASED
    return PositionChangeKind.UNCHANGED


def _position_sort_key(
    value: ReconciledPosition | PositionDelta,
) -> tuple[str, str]:
    """Return a stable identity order for positions and their deltas."""

    return (str(value.account_id), str(value.security_id))


def _rejection_sort_key(rejection: RejectedObservation) -> tuple[str, ...]:
    """Return a total ordering that cannot compare None with strings."""

    observation = rejection.observation
    return (
        str(observation.account_id),
        observation.symbol or "",
        observation.cusip or "",
        observation.provider_instrument_id or "",
        observation.observed_at.isoformat(),
        observation.asset_type.value,
        str(observation.quantity),
        str(observation.market_value) if observation.market_value is not None else "",
        str(observation.average_price) if observation.average_price is not None else "",
        rejection.reason.value,
        rejection.detail,
    )
