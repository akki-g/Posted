from dataclasses import replace
from datetime import datetime
from decimal import Decimal

import pytest

from app.domain.enums import AssetType, PositionChangeKind, RejectionReason
from app.domain.models import PositionObservation, SecurityIdentity, StoredPosition
from app.portfolio.reconcile import reconcile_positions
from app.tests.user_owned.factories import (
    SECURITIES,
    observation,
    resolve_security,
    stable_id,
    stored_position,
)

pytestmark = pytest.mark.user_owned


def test_new_position_is_opened() -> None:
    result = reconcile_positions(
        observations=[observation()], previous=[], resolve_security=resolve_security
    )
    assert len(result.positions) == 1
    assert result.deltas[0].kind is PositionChangeKind.OPENED
    assert result.deltas[0].quantity_delta == Decimal("10")


def test_identical_position_is_unchanged() -> None:
    result = reconcile_positions(
        observations=[observation()],
        previous=[stored_position()],
        resolve_security=resolve_security,
    )
    assert result.deltas[0].kind is PositionChangeKind.UNCHANGED
    assert result.deltas[0].quantity_delta == 0


def test_missing_current_position_is_closed() -> None:
    result = reconcile_positions(
        observations=[], previous=[stored_position()], resolve_security=resolve_security
    )
    assert result.positions == ()
    assert result.deltas[0].kind is PositionChangeKind.CLOSED
    assert result.deltas[0].current_quantity == 0


def test_duplicates_coalesce_with_weighted_average() -> None:
    result = reconcile_positions(
        observations=[
            observation(quantity="2", market_value="400", average_price="100"),
            observation(quantity="3", market_value="900", average_price="200"),
        ],
        previous=[],
        resolve_security=resolve_security,
    )
    assert result.positions[0].quantity == Decimal("5")
    assert result.positions[0].market_value == Decimal("1300")
    assert result.positions[0].average_price == Decimal("160")


def test_partial_market_value_is_unknown() -> None:
    result = reconcile_positions(
        observations=[
            observation(quantity="2", market_value="400"),
            observation(quantity="3", market_value=None),
        ],
        previous=[],
        resolve_security=resolve_security,
    )
    assert result.positions[0].market_value is None


def test_unsupported_asset_is_rejected() -> None:
    result = reconcile_positions(
        observations=[observation(asset_type=AssetType.OPTION)],
        previous=[],
        resolve_security=resolve_security,
    )
    assert result.positions == ()
    assert result.rejected[0].reason is RejectionReason.UNSUPPORTED_ASSET_TYPE


def test_result_does_not_depend_on_observation_order() -> None:
    first = observation("AAPL")
    second = observation("MSFT")
    forward = reconcile_positions(
        observations=[first, second], previous=[], resolve_security=resolve_security
    )
    reverse = reconcile_positions(
        observations=[second, first], previous=[], resolve_security=resolve_security
    )
    assert forward == reverse


@pytest.mark.parametrize(
    ("old_quantity", "new_quantity", "expected_kind"),
    [
        ("5", "8", PositionChangeKind.INCREASED),
        ("8", "5", PositionChangeKind.DECREASED),
    ],
)
def test_quantity_change_is_classified(
    old_quantity: str,
    new_quantity: str,
    expected_kind: PositionChangeKind,
) -> None:
    result = reconcile_positions(
        observations=[observation(quantity=new_quantity)],
        previous=[stored_position(quantity=old_quantity)],
        resolve_security=resolve_security,
    )

    assert result.deltas[0].kind is expected_kind
    assert result.deltas[0].quantity_delta == Decimal(new_quantity) - Decimal(old_quantity)


def test_market_value_change_does_not_change_quantity_classification() -> None:
    result = reconcile_positions(
        observations=[observation(market_value="2500")],
        previous=[stored_position()],
        resolve_security=resolve_security,
    )

    assert result.deltas[0].kind is PositionChangeKind.UNCHANGED


def test_same_security_in_two_accounts_remains_two_positions() -> None:
    result = reconcile_positions(
        observations=[observation(account="taxable"), observation(account="ira")],
        previous=[],
        resolve_security=resolve_security,
    )

    assert len(result.positions) == 2
    assert {position.account_id for position in result.positions} == {
        stable_id("taxable"),
        stable_id("ira"),
    }


def test_symbol_aliases_resolving_to_one_security_coalesce() -> None:
    def resolve_alias(observed: PositionObservation) -> SecurityIdentity | None:
        return SECURITIES["AAPL"] if observed.symbol in {"AAPL", "APPLE"} else None

    result = reconcile_positions(
        observations=[observation("AAPL", quantity="2"), observation("APPLE", quantity="3")],
        previous=[],
        resolve_security=resolve_alias,
    )

    assert len(result.positions) == 1
    assert result.positions[0].quantity == Decimal("5")


def test_unresolved_security_is_rejected() -> None:
    result = reconcile_positions(
        observations=[observation("UNKNOWN")],
        previous=[],
        resolve_security=resolve_security,
    )

    assert result.positions == ()
    assert result.rejected[0].reason is RejectionReason.UNRESOLVED_SECURITY


def test_negative_quantity_is_rejected_before_resolution() -> None:
    def unexpected_resolver(_observation: PositionObservation) -> SecurityIdentity | None:
        raise AssertionError("invalid observations must not reach the resolver")

    result = reconcile_positions(
        observations=[observation(quantity="-1")],
        previous=[],
        resolve_security=unexpected_resolver,
    )

    assert result.positions == ()
    assert result.rejected[0].reason is RejectionReason.NEGATIVE_QUANTITY


def test_naive_timestamp_is_rejected() -> None:
    naive = replace(observation(), observed_at=datetime(2026, 7, 22, 12))

    result = reconcile_positions(
        observations=[naive],
        previous=[],
        resolve_security=resolve_security,
    )

    assert result.positions == ()
    assert result.rejected[0].reason is RejectionReason.INVALID_TIMESTAMP


def test_partial_average_price_is_unknown() -> None:
    result = reconcile_positions(
        observations=[
            observation(quantity="2", average_price="100"),
            observation(quantity="3", average_price=None),
        ],
        previous=[],
        resolve_security=resolve_security,
    )

    assert result.positions[0].average_price is None


def test_zero_total_group_does_not_create_a_position() -> None:
    result = reconcile_positions(
        observations=[observation(quantity="0")],
        previous=[],
        resolve_security=resolve_security,
    )

    assert result.positions == ()
    assert result.deltas == ()


def test_replaying_current_state_produces_unchanged_delta() -> None:
    first = reconcile_positions(
        observations=[observation(quantity="12")],
        previous=[],
        resolve_security=resolve_security,
    )
    current = first.positions[0]
    replay_previous = StoredPosition(
        position_id=stable_id("replayed-aapl"),
        account_id=current.account_id,
        security_id=current.security_id,
        canonical_symbol=current.canonical_symbol,
        quantity=current.quantity,
        market_value=current.market_value,
        average_price=current.average_price,
    )

    replay = reconcile_positions(
        observations=[observation(quantity="12")],
        previous=[replay_previous],
        resolve_security=resolve_security,
    )

    assert replay.deltas[0].kind is PositionChangeKind.UNCHANGED
    assert replay.deltas[0].quantity_delta == 0
