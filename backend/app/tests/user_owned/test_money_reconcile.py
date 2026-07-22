from dataclasses import replace
from decimal import Decimal

import pytest

from app.money.enums import LedgerActionKind, TransactionStatus
from app.money.models import ProviderTransactionRef
from app.money.reconcile import reconcile_ledger
from app.tests.user_owned.money_factories import (
    normalized_transaction,
    stored_money_transaction,
)

pytestmark = pytest.mark.user_owned


def test_new_transaction_is_inserted() -> None:
    result = reconcile_ledger(incoming=[normalized_transaction()], existing=[], removed=[])

    assert len(result.actions) == 1
    assert result.actions[0].kind is LedgerActionKind.INSERT
    assert result.actions[0].transaction is not None


def test_identical_transaction_is_unchanged() -> None:
    incoming = normalized_transaction()
    stored = stored_money_transaction()

    result = reconcile_ledger(incoming=[incoming], existing=[stored], removed=[])

    assert result.actions[0].kind is LedgerActionKind.UNCHANGED
    assert result.actions[0].existing_transaction_id == stored.transaction_id


def test_changed_provider_transaction_is_updated() -> None:
    stored = stored_money_transaction()
    incoming = replace(normalized_transaction(), amount=Decimal("7.25"))

    result = reconcile_ledger(incoming=[incoming], existing=[stored], removed=[])

    assert result.actions[0].kind is LedgerActionKind.UPDATE
    assert result.actions[0].existing_transaction_id == stored.transaction_id


def test_explicitly_removed_provider_transaction_is_deleted() -> None:
    stored = stored_money_transaction()
    provider_id = stored.provider_transaction_id
    assert provider_id is not None

    result = reconcile_ledger(
        incoming=[],
        existing=[stored],
        removed=[ProviderTransactionRef(source=stored.source, provider_transaction_id=provider_id)],
    )

    assert result.actions[0].kind is LedgerActionKind.DELETE
    assert result.actions[0].existing_transaction_id == stored.transaction_id


def test_posted_transaction_replaces_its_pending_predecessor() -> None:
    pending = stored_money_transaction(
        "pending-coffee",
        provider_transaction_id="tx-pending-coffee",
        status=TransactionStatus.PENDING,
        posted_at=None,
    )
    posted = normalized_transaction(
        "posted-coffee",
        provider_transaction_id="tx-posted-coffee",
        pending_provider_transaction_id="tx-pending-coffee",
    )

    result = reconcile_ledger(incoming=[posted], existing=[pending], removed=[])

    assert result.actions[0].kind is LedgerActionKind.REPLACE_PENDING
    assert result.actions[0].existing_transaction_id == pending.transaction_id


def test_reconciliation_is_order_independent() -> None:
    coffee = normalized_transaction("coffee")
    groceries = normalized_transaction("groceries")

    forward = reconcile_ledger(incoming=[coffee, groceries], existing=[], removed=[])
    reverse = reconcile_ledger(incoming=[groceries, coffee], existing=[], removed=[])

    assert forward == reverse
