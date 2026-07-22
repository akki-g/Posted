"""Human-owned transaction-normalization exercise.

Implementation contract: guides/06-TRANSACTION-NORMALIZATION.md.
The coding agent must not implement or replace this module unless explicitly asked.
"""

from collections.abc import Callable, Sequence
from datetime import datetime

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
    selected = merchant or _clean_text(observation.description)
    if selected.isupper() or selected.islower():
        return selected.title()
    return selected


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
    raise NotImplementedError("Follow guides/06-TRANSACTION-NORMALIZATION.md")
