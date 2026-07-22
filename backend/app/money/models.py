from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from app.money.enums import (
    LedgerActionKind,
    MoneyAccountType,
    RecurrenceFrequency,
    SpendingTreatment,
    TransactionDirection,
    TransactionRejectionReason,
    TransactionSource,
    TransactionStatus,
)


@dataclass(frozen=True, slots=True)
class MoneyAccountIdentity:
    account_id: UUID
    account_type: MoneyAccountType
    display_name: str


@dataclass(frozen=True, slots=True)
class TransactionObservation:
    source: TransactionSource
    provider_transaction_id: str | None
    provider_account_id: str
    pending_provider_transaction_id: str | None
    status: TransactionStatus
    direction: TransactionDirection
    amount: Decimal
    currency: str
    merchant_name: str | None
    description: str
    authorized_at: datetime | None
    posted_at: datetime | None
    category_primary: str | None = None
    category_detailed: str | None = None
    payment_channel: str | None = None


@dataclass(frozen=True, slots=True)
class NormalizedTransaction:
    account_id: UUID
    account_type: MoneyAccountType
    source: TransactionSource
    provider_transaction_id: str | None
    pending_provider_transaction_id: str | None
    status: TransactionStatus
    direction: TransactionDirection
    amount: Decimal
    currency: str
    merchant_name: str
    description: str
    occurred_at: datetime
    posted_at: datetime | None
    category_primary: str
    category_detailed: str | None
    payment_channel: str | None
    fingerprint: str


@dataclass(frozen=True, slots=True)
class RejectedMoneyTransaction:
    observation: TransactionObservation
    reason: TransactionRejectionReason
    detail: str


@dataclass(frozen=True, slots=True)
class TransactionNormalizationResult:
    transactions: tuple[NormalizedTransaction, ...]
    rejected: tuple[RejectedMoneyTransaction, ...]


@dataclass(frozen=True, slots=True)
class StoredMoneyTransaction:
    transaction_id: UUID
    account_id: UUID
    account_type: MoneyAccountType
    source: TransactionSource
    provider_transaction_id: str | None
    pending_provider_transaction_id: str | None
    status: TransactionStatus
    direction: TransactionDirection
    amount: Decimal
    currency: str
    merchant_name: str
    description: str
    occurred_at: datetime
    posted_at: datetime | None
    category_primary: str
    category_detailed: str | None
    payment_channel: str | None
    fingerprint: str


@dataclass(frozen=True, slots=True)
class ProviderTransactionRef:
    source: TransactionSource
    provider_transaction_id: str


@dataclass(frozen=True, slots=True)
class LedgerAction:
    kind: LedgerActionKind
    existing_transaction_id: UUID | None
    transaction: NormalizedTransaction | None
    detail: str


@dataclass(frozen=True, slots=True)
class LedgerReconciliationResult:
    actions: tuple[LedgerAction, ...]


@dataclass(frozen=True, slots=True)
class SpendingPolicy:
    transfer_window: timedelta = timedelta(days=3)
    transfer_categories: frozenset[str] = frozenset(
        {"TRANSFER_IN", "TRANSFER_OUT", "INTERNAL_TRANSFER"}
    )
    credit_card_payment_categories: frozenset[str] = frozenset(
        {"CREDIT_CARD_PAYMENT", "LOAN_PAYMENTS"}
    )
    investment_categories: frozenset[str] = frozenset({"INVESTMENT_TRANSFER", "BROKERAGE"})
    refund_categories: frozenset[str] = frozenset({"REFUND"})


@dataclass(frozen=True, slots=True)
class SpendingDecision:
    transaction_id: UUID
    treatment: SpendingTreatment
    reason: str


@dataclass(frozen=True, slots=True)
class CategorySpend:
    category: str
    amount: Decimal


@dataclass(frozen=True, slots=True)
class WeeklySpendingSummary:
    period_start: datetime
    period_end: datetime
    total_spending: Decimal
    total_income: Decimal
    total_excluded: Decimal
    by_category: tuple[CategorySpend, ...]
    decisions: tuple[SpendingDecision, ...]


@dataclass(frozen=True, slots=True)
class RecurringPolicy:
    minimum_occurrences: int = 3
    maximum_amount_variation: Decimal = Decimal("0.25")
    frequency_windows: Mapping[RecurrenceFrequency, tuple[int, int]] | None = None


@dataclass(frozen=True, slots=True)
class RecurringStreamCandidate:
    stream_key: str
    merchant_name: str
    frequency: RecurrenceFrequency
    average_amount: Decimal
    last_amount: Decimal
    currency: str
    last_charged_at: datetime
    next_expected_date: date
    confidence: float
    transaction_ids: tuple[UUID, ...]


@dataclass(frozen=True, slots=True)
class RecurringDetectionResult:
    streams: tuple[RecurringStreamCandidate, ...]
