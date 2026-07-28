from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from app.money.enums import (
    TransactionDirection,
    TransactionSource,
    TransactionStatus,
)
from app.money.models import TransactionObservation


def _timestamp(value: object) -> datetime | None:
    if not value:
        return None
    raw = str(value).replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _decimal(value: object) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def map_plaid_account_values(raw: dict[str, Any]) -> dict[str, object]:
    plaid_type = str(raw.get("type") or "other")
    subtype = str(raw.get("subtype") or "") or None
    if plaid_type == "depository" and subtype in {"checking", "savings"}:
        account_type = subtype
    elif plaid_type == "credit":
        account_type = "credit_card"
    elif plaid_type == "loan":
        account_type = "loan"
    else:
        account_type = "other"
    balances = raw.get("balances") or {}
    current = _decimal(balances.get("current")) or Decimal("0")
    currency = balances.get("iso_currency_code") or balances.get("unofficial_currency_code")
    return {
        "display_name": str(raw.get("official_name") or raw.get("name") or "Account"),
        "mask": str(raw["mask"]) if raw.get("mask") else None,
        "account_type": account_type,
        "subtype": subtype,
        "currency": str(currency or "USD").upper(),
        "current_balance": current,
        "available_balance": _decimal(balances.get("available")),
        "credit_limit": _decimal(balances.get("limit")),
        "is_active": True,
    }


def map_plaid_transaction(raw: dict[str, Any]) -> TransactionObservation:
    try:
        signed_amount = Decimal(str(raw["amount"]))
    except (KeyError, InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("Plaid transaction has no valid amount") from exc

    pending = bool(raw.get("pending"))
    posted_at = _timestamp(raw.get("datetime")) or _timestamp(raw.get("date"))
    occurred_at = (
        _timestamp(raw.get("authorized_datetime"))
        or _timestamp(raw.get("authorized_date"))
        # Some institutions never populate authorized_date for pending transactions.
        # date/datetime is still a faithful occurrence time in that case.
        or (posted_at if pending else None)
    )
    category = raw.get("personal_finance_category") or {}
    merchant = raw.get("merchant_name")
    description = str(raw.get("name") or merchant or "Unknown transaction")
    currency = raw.get("iso_currency_code") or raw.get("unofficial_currency_code") or ""

    return TransactionObservation(
        source=TransactionSource.PLAID,
        provider_transaction_id=(str(raw["transaction_id"]) if raw.get("transaction_id") else None),
        provider_account_id=str(raw.get("account_id") or ""),
        pending_provider_transaction_id=(
            str(raw["pending_transaction_id"]) if raw.get("pending_transaction_id") else None
        ),
        status=TransactionStatus.PENDING if pending else TransactionStatus.POSTED,
        direction=(
            TransactionDirection.OUTFLOW if signed_amount >= 0 else TransactionDirection.INFLOW
        ),
        amount=abs(signed_amount),
        currency=str(currency),
        merchant_name=str(merchant) if merchant else None,
        description=description,
        authorized_at=occurred_at,
        posted_at=None if pending else posted_at,
        category_primary=(str(category["primary"]) if category.get("primary") else None),
        category_detailed=(str(category["detailed"]) if category.get("detailed") else None),
        payment_channel=(str(raw["payment_channel"]) if raw.get("payment_channel") else None),
    )
