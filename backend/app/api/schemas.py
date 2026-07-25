from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class APIModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class HealthResponse(APIModel):
    status: str
    app: str
    environment: str
    demo_mode: bool


class MoneyMovement(APIModel):
    amount: Decimal
    percent: Decimal


class PortfolioSummary(APIModel):
    total_value: Decimal
    day_change: MoneyMovement
    total_gain: MoneyMovement
    last_synced_at: datetime | None
    connection_status: str
    demo_mode: bool


class ChartPoint(APIModel):
    timestamp: datetime
    value: Decimal


class AccountSummary(APIModel):
    id: UUID
    name: str
    account_type: str
    balance: Decimal
    day_change: Decimal
    total_gain: Decimal


class HoldingSummary(APIModel):
    security_id: UUID
    symbol: str
    name: str
    asset_type: str
    sector: str | None
    quantity: Decimal
    average_price: Decimal | None
    last_price: Decimal | None
    market_value: Decimal
    day_change: Decimal
    day_change_percent: Decimal
    total_gain: Decimal
    total_gain_percent: Decimal
    portfolio_weight: Decimal
    account_count: int


class EventReason(APIModel):
    code: str
    message: str
    value: float | str | None = None


class EventSecurity(APIModel):
    security_id: UUID
    symbol: str
    name: str
    match_confidence: Decimal
    effective_weight: Decimal


class EventSummary(APIModel):
    id: UUID
    event_type: str
    headline: str
    summary: str | None
    occurred_at: datetime
    source_name: str
    source_url: str | None
    score: Decimal
    level: str
    confidence: Decimal
    unread: bool
    is_demo: bool
    reasons: list[EventReason]
    securities: list[EventSecurity]
    ai_insight: str | None = None


class DashboardResponse(APIModel):
    portfolio: PortfolioSummary
    history: list[ChartPoint]
    accounts: list[AccountSummary]
    top_holdings: list[HoldingSummary]
    important_events: list[EventSummary]
    unread_event_count: int


class FeedResponse(APIModel):
    items: list[EventSummary]
    unread_count: int
    total: int


class NewsRefreshResponse(APIModel):
    held_symbols: int
    fetched: int
    normalized: int
    rejected: int
    duplicates_skipped: int
    inserted: int
    providers: list[str]
    warnings: list[str]


class MorningDebriefResponse(APIModel):
    generated_at: datetime
    available: bool
    summary: str | None


class AssistantMessageSummary(APIModel):
    id: UUID
    role: str
    content: str
    section: str | None
    sources: list[dict[str, str]] | None
    created_at: datetime


class AssistantChatRequest(APIModel):
    message: str
    section: str = "general"
    screen_context: str | None = Field(default=None, max_length=1200)


class AssistantConversationResponse(APIModel):
    messages: list[AssistantMessageSummary]


class ConnectionStatus(APIModel):
    id: UUID
    provider: str
    display_name: str
    status: str
    last_synced_at: datetime | None
    account_count: int
    demo_mode: bool


class OAuthAuthorizeResponse(APIModel):
    authorization_url: str


class AuthUser(APIModel):
    id: UUID
    email: str
    display_name: str


class SmsLinkRequest(APIModel):
    phone_number: str = Field(min_length=8, max_length=20)


class SmsVerifyRequest(APIModel):
    code: str = Field(min_length=6, max_length=6)


class SmsLinkStatus(APIModel):
    status: str
    phone_number_masked: str | None = None
    opted_out: bool = False


class SyncRequest(APIModel):
    idempotency_key: str = Field(min_length=8, max_length=160)


class SyncAccepted(APIModel):
    sync_run_id: UUID
    status: str
    message: str


class UserPreferences(APIModel):
    immediate_alert_level: str = "important"
    push_enabled: bool = True
    email_digest_enabled: bool = False
    daily_briefing_time: str = "08:00"


class MoneyAccountSummary(APIModel):
    id: UUID
    name: str
    provider: str
    account_type: str
    mask: str | None
    currency: str
    current_balance: Decimal
    available_balance: Decimal | None
    credit_limit: Decimal | None
    is_liability: bool


class MoneyTransactionSummary(APIModel):
    id: UUID
    account_id: UUID
    account_name: str
    merchant_name: str
    description: str
    status: str
    direction: str
    amount: Decimal
    currency: str
    occurred_at: datetime
    category: str
    payment_channel: str | None
    is_transfer: bool
    is_recurring: bool


class SpendingCategorySummary(APIModel):
    category: str
    label: str
    amount: Decimal
    percent: Decimal


class DailySpendingPoint(APIModel):
    date: str
    amount: Decimal


class RecurringStreamSummary(APIModel):
    id: UUID
    merchant_name: str
    frequency: str
    average_amount: Decimal
    last_amount: Decimal
    currency: str
    last_charged_at: datetime
    next_expected_date: str
    confidence: Decimal
    status: str


class MoneyConnectionStatus(APIModel):
    id: UUID
    provider: str
    display_name: str
    status: str
    last_synced_at: datetime | None
    account_count: int
    is_demo: bool


class MoneySyncResponse(APIModel):
    connection_id: UUID
    status: str
    inserted: int
    updated: int
    deleted: int
    unchanged: int
    replaced_pending: int
    normalized: int
    rejected: int
    synced_at: datetime


class PlaidLinkTokenResponse(APIModel):
    link_token: str
    expiration: datetime
    request_id: str | None = None


class PlaidExchangeRequest(APIModel):
    public_token: str = Field(min_length=8, max_length=500)


class MoneyTransactionsResponse(APIModel):
    items: list[MoneyTransactionSummary]
    total: int


class MoneyOverviewResponse(APIModel):
    cash_balance: Decimal
    card_balance: Decimal
    net_cash_position: Decimal
    weekly_spending: Decimal
    weekly_income: Decimal
    monthly_recurring: Decimal
    annualized_recurring: Decimal
    last_synced_at: datetime | None
    demo_mode: bool
    spending_by_category: list[SpendingCategorySummary]
    daily_spending: list[DailySpendingPoint]
    accounts: list[MoneyAccountSummary]
    recent_transactions: list[MoneyTransactionSummary]
    subscriptions: list[RecurringStreamSummary]
