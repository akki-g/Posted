from enum import StrEnum


class MoneyAccountType(StrEnum):
    CHECKING = "checking"
    SAVINGS = "savings"
    CREDIT_CARD = "credit_card"
    CASH = "cash"
    LOAN = "loan"
    OTHER = "other"


class TransactionSource(StrEnum):
    PLAID = "plaid"
    APPLE_FINANCEKIT = "apple_financekit"
    MANUAL = "manual"
    DEMO = "demo"


class TransactionDirection(StrEnum):
    INFLOW = "inflow"
    OUTFLOW = "outflow"


class TransactionStatus(StrEnum):
    PENDING = "pending"
    POSTED = "posted"


class TransactionRejectionReason(StrEnum):
    INVALID_AMOUNT = "invalid_amount"
    INVALID_CURRENCY = "invalid_currency"
    INVALID_TIMESTAMP = "invalid_timestamp"
    MISSING_IDENTITY = "missing_identity"
    UNRESOLVED_ACCOUNT = "unresolved_account"


class LedgerActionKind(StrEnum):
    INSERT = "insert"
    UPDATE = "update"
    DELETE = "delete"
    UNCHANGED = "unchanged"
    REPLACE_PENDING = "replace_pending"


class SpendingTreatment(StrEnum):
    SPENDING = "spending"
    INCOME = "income"
    INTERNAL_TRANSFER = "internal_transfer"
    CREDIT_CARD_PAYMENT = "credit_card_payment"
    REFUND = "refund"
    INVESTMENT = "investment"
    PENDING = "pending"
    EXCLUDED = "excluded"


class RecurrenceFrequency(StrEnum):
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"
