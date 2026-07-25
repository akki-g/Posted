"""Human-owned transaction-normalization exercise.

Implementation contract: guides/06-TRANSACTION-NORMALIZATION.md.
The coding agent must not implement or replace this module unless explicitly asked.
"""

from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from decimal import Decimal
from hashlib import sha256

from app.money.enums import TransactionRejectionReason
from app.money.models import (
    MoneyAccountIdentity,
    NormalizedTransaction,
    RejectedMoneyTransaction,
    TransactionNormalizationResult,
    TransactionObservation,
)

AccountResolver = Callable[[str], MoneyAccountIdentity | None]


def _occurrence_time(observation: TransactionObservation) -> datetime | None:
    """Choose the documented economic occurrence timestamp fallback."""

    return observation.authorized_at or observation.posted_at


def _is_timezone_aware(value: datetime) -> bool:
    """Return whether a provider timestamp identifies an actual UTC offset."""

    return value.tzinfo is not None and value.utcoffset() is not None


def _clean_text(value: str) -> str:
    """Collapse every run of whitespace in provider text."""

    return " ".join(value.split())


def _clean_optional_text(value: str | None) -> str | None:
    """Normalize optional provider text and turn blank text into None."""

    if value is None:
        return None
    normalized = _clean_text(value)
    return normalized or None


def _merchant_name(observation: TransactionObservation) -> str:
    """Choose the documented merchant fallback and normalize test-style casing."""

    merchant = _clean_optional_text(observation.merchant_name)
    selected = merchant or _clean_text(observation.description) or "Unknown transaction"
    if selected.isupper() or selected.islower():
        return selected.title()
    return selected


def _rejection_reason(
    observation: TransactionObservation,
) -> TransactionRejectionReason | None:
    """Validate one observation in a stable, user-explainable order."""

    if not observation.amount.is_finite() or observation.amount <= Decimal("0"):
        return TransactionRejectionReason.INVALID_AMOUNT

    currency = observation.currency.strip()
    if len(currency) != 3 or not currency.isascii() or not currency.isalpha():
        return TransactionRejectionReason.INVALID_CURRENCY

    provider_id = _clean_optional_text(observation.provider_transaction_id)
    fallback_text = _clean_optional_text(observation.merchant_name) or _clean_optional_text(
        observation.description
    )
    if provider_id is None and fallback_text is None:
        return TransactionRejectionReason.MISSING_IDENTITY

    occurred_at = _occurrence_time(observation)
    if occurred_at is None or not _is_timezone_aware(occurred_at):
        return TransactionRejectionReason.INVALID_TIMESTAMP
    if observation.posted_at is not None and not _is_timezone_aware(observation.posted_at):
        return TransactionRejectionReason.INVALID_TIMESTAMP

    return None


def _fingerprint(
    observation: TransactionObservation,
    account: MoneyAccountIdentity,
    currency: str,
    merchant: str,
    occurred_at: datetime,
) -> str:
    """Hash canonical economic fields into a durable, account-scoped identity."""

    fields = (
        observation.source.value,
        str(account.account_id),
        _clean_optional_text(observation.provider_transaction_id) or "",
        observation.direction.value,
        format(observation.amount, "f"),
        currency,
        merchant,
        occurred_at.isoformat(),
    )
    return sha256("|".join(fields).encode("utf-8")).hexdigest()


def _normalize_one(
    observation: TransactionObservation,
    account: MoneyAccountIdentity,
) -> NormalizedTransaction:
    """Construct one accepted ledger candidate from already-validated input."""

    raw_occurred_at = _occurrence_time(observation)
    if raw_occurred_at is None:  # Protected by _rejection_reason; keeps this helper total.
        raise ValueError("accepted transaction requires an occurrence timestamp")

    occurred_at = raw_occurred_at.astimezone(UTC)
    posted_at = observation.posted_at.astimezone(UTC) if observation.posted_at else None
    currency = observation.currency.strip().upper()
    merchant = _merchant_name(observation)
    description = _clean_text(observation.description) or merchant
    category_primary = (
        _clean_optional_text(observation.category_primary) or "UNCATEGORIZED"
    ).upper()

    return NormalizedTransaction(
        account_id=account.account_id,
        account_type=account.account_type,
        source=observation.source,
        provider_transaction_id=_clean_optional_text(observation.provider_transaction_id),
        pending_provider_transaction_id=_clean_optional_text(
            observation.pending_provider_transaction_id
        ),
        status=observation.status,
        direction=observation.direction,
        amount=observation.amount,
        currency=currency,
        merchant_name=merchant,
        description=description,
        occurred_at=occurred_at,
        posted_at=posted_at,
        category_primary=category_primary,
        category_detailed=_clean_optional_text(observation.category_detailed),
        payment_channel=_clean_optional_text(observation.payment_channel),
        fingerprint=_fingerprint(observation, account, currency, merchant, occurred_at),
    )


def _transaction_sort_key(transaction: NormalizedTransaction) -> tuple[str, str, str, str]:
    """Return a stable ordering key for accepted transactions."""

    return (
        transaction.occurred_at.isoformat(),
        transaction.source.value,
        transaction.provider_transaction_id or "",
        transaction.fingerprint,
    )


def _rejection_sort_key(rejection: RejectedMoneyTransaction) -> tuple[str, ...]:
    """Return a stable ordering key containing no incomparable optional values."""

    observation = rejection.observation
    occurred_at = _occurrence_time(observation)
    return (
        observation.source.value,
        observation.provider_account_id,
        observation.provider_transaction_id or "",
        occurred_at.isoformat() if occurred_at is not None else "",
        rejection.reason.value,
    )


def normalize_transactions(
    observations: Sequence[TransactionObservation],
    *,
    resolve_account: AccountResolver,
) -> TransactionNormalizationResult:
    """Convert provider-neutral observations into deterministic ledger candidates."""

    accepted: list[NormalizedTransaction] = []
    rejected: list[RejectedMoneyTransaction] = []

    for observation in observations:
        reason = _rejection_reason(observation)
        if reason is not None:
            rejected.append(
                RejectedMoneyTransaction(
                    observation=observation,
                    reason=reason,
                    detail=f"Transaction rejected: {reason.value}",
                )
            )
            continue

        account = resolve_account(observation.provider_account_id)
        if account is None:
            rejected.append(
                RejectedMoneyTransaction(
                    observation=observation,
                    reason=TransactionRejectionReason.UNRESOLVED_ACCOUNT,
                    detail="Provider account does not map to a Posted account",
                )
            )
            continue

        accepted.append(_normalize_one(observation, account))

    return TransactionNormalizationResult(
        transactions=tuple(sorted(accepted, key=_transaction_sort_key)),
        rejected=tuple(sorted(rejected, key=_rejection_sort_key)),
    )
