from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

MONEY = Numeric(20, 4)
QUANTITY = Numeric(24, 8)
PERCENT = Numeric(12, 6)


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)


class UserPreference(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "user_preferences"

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    immediate_alert_level: Mapped[str] = mapped_column(
        String(20), default="important", nullable=False
    )
    push_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    email_digest_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    daily_briefing_time: Mapped[str] = mapped_column(String(8), default="08:00", nullable=False)


class SmsLink(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "sms_links"

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    phone_number: Mapped[str] = mapped_column(String(20), index=True)
    code_hash: Mapped[str | None] = mapped_column(String(64))
    code_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    request_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    request_window_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    opted_out: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class BrokerageConnection(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "brokerage_connections"

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="demo", nullable=False)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    accounts: Mapped[list["BrokerageAccount"]] = relationship(
        back_populates="connection", cascade="all, delete-orphan"
    )


class BrokerageCredential(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "brokerage_credentials"

    connection_id: Mapped[UUID] = mapped_column(
        ForeignKey("brokerage_connections.id", ondelete="CASCADE"), unique=True, index=True
    )
    access_token_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    refresh_token_encrypted: Mapped[str | None] = mapped_column(Text)
    token_type: Mapped[str] = mapped_column(String(32), default="Bearer", nullable=False)
    scope: Mapped[str | None] = mapped_column(Text)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class BrokerageAccount(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "brokerage_accounts"
    __table_args__ = (UniqueConstraint("connection_id", "provider_account_id"),)

    connection_id: Mapped[UUID] = mapped_column(ForeignKey("brokerage_connections.id"), index=True)
    provider_account_id: Mapped[str] = mapped_column(String(160), nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    account_type: Mapped[str] = mapped_column(String(80), nullable=False)
    balance: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    day_change: Mapped[Decimal] = mapped_column(MONEY, default=0, nullable=False)
    total_gain: Mapped[Decimal] = mapped_column(MONEY, default=0, nullable=False)

    connection: Mapped[BrokerageConnection] = relationship(back_populates="accounts")
    positions: Mapped[list["Position"]] = relationship(
        back_populates="account", cascade="all, delete-orphan"
    )


class FinancialConnection(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "financial_connections"
    __table_args__ = (UniqueConstraint("provider", "provider_item_id"),)

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    provider_item_id: Mapped[str | None] = mapped_column(String(160))
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="demo", nullable=False)
    cursor: Mapped[str | None] = mapped_column(Text)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    accounts: Mapped[list["FinancialAccount"]] = relationship(
        back_populates="connection", cascade="all, delete-orphan"
    )
    credential: Mapped["FinancialCredential | None"] = relationship(
        back_populates="connection", cascade="all, delete-orphan"
    )


class FinancialCredential(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "financial_credentials"

    connection_id: Mapped[UUID] = mapped_column(
        ForeignKey("financial_connections.id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )
    access_token_encrypted: Mapped[str] = mapped_column(Text, nullable=False)

    connection: Mapped[FinancialConnection] = relationship(back_populates="credential")


class FinancialAccount(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "financial_accounts"
    __table_args__ = (UniqueConstraint("connection_id", "provider_account_id"),)

    connection_id: Mapped[UUID] = mapped_column(
        ForeignKey("financial_connections.id", ondelete="CASCADE"), index=True
    )
    provider_account_id: Mapped[str] = mapped_column(String(160), nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    mask: Mapped[str | None] = mapped_column(String(8))
    account_type: Mapped[str] = mapped_column(String(40), nullable=False)
    subtype: Mapped[str | None] = mapped_column(String(80))
    currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)
    current_balance: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    available_balance: Mapped[Decimal | None] = mapped_column(MONEY)
    credit_limit: Mapped[Decimal | None] = mapped_column(MONEY)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    connection: Mapped[FinancialConnection] = relationship(back_populates="accounts")
    transactions: Mapped[list["MoneyTransactionRecord"]] = relationship(
        back_populates="account", cascade="all, delete-orphan"
    )
    balance_snapshots: Mapped[list["BalanceSnapshot"]] = relationship(
        back_populates="account", cascade="all, delete-orphan"
    )


class BalanceSnapshot(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "balance_snapshots"
    __table_args__ = (Index("ix_balance_snapshots_account_time", "account_id", "observed_at"),)

    account_id: Mapped[UUID] = mapped_column(
        ForeignKey("financial_accounts.id", ondelete="CASCADE")
    )
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    current_balance: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    available_balance: Mapped[Decimal | None] = mapped_column(MONEY)

    account: Mapped[FinancialAccount] = relationship(back_populates="balance_snapshots")


class MoneyTransactionRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "money_transactions"
    __table_args__ = (
        UniqueConstraint("account_id", "provider_transaction_id"),
        Index("ix_money_transactions_account_time", "account_id", "occurred_at"),
        Index("ix_money_transactions_merchant", "merchant_name"),
    )

    account_id: Mapped[UUID] = mapped_column(
        ForeignKey("financial_accounts.id", ondelete="CASCADE"), index=True
    )
    source: Mapped[str] = mapped_column(String(40), nullable=False)
    provider_transaction_id: Mapped[str | None] = mapped_column(String(200))
    pending_provider_transaction_id: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    direction: Mapped[str] = mapped_column(String(20), nullable=False)
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)
    merchant_name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    category_primary: Mapped[str] = mapped_column(String(100), nullable=False)
    category_detailed: Mapped[str | None] = mapped_column(String(160))
    payment_channel: Mapped[str | None] = mapped_column(String(40))
    fingerprint: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    is_transfer: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_recurring: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    account: Mapped[FinancialAccount] = relationship(back_populates="transactions")


class RecurringStream(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "recurring_streams"
    __table_args__ = (
        UniqueConstraint("user_id", "stream_key"),
        Index("ix_recurring_streams_user_next", "user_id", "next_expected_date"),
    )

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    stream_key: Mapped[str] = mapped_column(String(160), nullable=False)
    merchant_name: Mapped[str] = mapped_column(String(200), nullable=False)
    frequency: Mapped[str] = mapped_column(String(20), nullable=False)
    average_amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    last_amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)
    last_charged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    next_expected_date: Mapped[date] = mapped_column(Date, nullable=False)
    confidence: Mapped[Decimal] = mapped_column(PERCENT, nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="active", nullable=False)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class Security(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "securities"

    symbol: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    asset_type: Mapped[str] = mapped_column(String(40), nullable=False)
    sector: Mapped[str | None] = mapped_column(String(120))
    cik: Mapped[str | None] = mapped_column(String(20), unique=True)

    positions: Mapped[list["Position"]] = relationship(back_populates="security")


class Position(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "positions"
    __table_args__ = (
        UniqueConstraint("account_id", "security_id"),
        Index("ix_positions_security_account", "security_id", "account_id"),
    )

    account_id: Mapped[UUID] = mapped_column(ForeignKey("brokerage_accounts.id"))
    security_id: Mapped[UUID] = mapped_column(ForeignKey("securities.id"))
    quantity: Mapped[Decimal] = mapped_column(QUANTITY, nullable=False)
    average_price: Mapped[Decimal | None] = mapped_column(MONEY)
    last_price: Mapped[Decimal | None] = mapped_column(MONEY)
    market_value: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    day_change: Mapped[Decimal] = mapped_column(MONEY, default=0, nullable=False)
    day_change_percent: Mapped[Decimal] = mapped_column(PERCENT, default=0, nullable=False)
    total_gain: Mapped[Decimal] = mapped_column(MONEY, default=0, nullable=False)
    total_gain_percent: Mapped[Decimal] = mapped_column(PERCENT, default=0, nullable=False)
    portfolio_weight: Mapped[Decimal] = mapped_column(PERCENT, default=0, nullable=False)

    account: Mapped[BrokerageAccount] = relationship(back_populates="positions")
    security: Mapped[Security] = relationship(back_populates="positions")


class PortfolioSnapshot(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "portfolio_snapshots"
    __table_args__ = (Index("ix_portfolio_snapshots_user_time", "user_id", "observed_at"),)

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    total_value: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    day_change: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    day_change_percent: Mapped[Decimal] = mapped_column(PERCENT, nullable=False)
    total_gain: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    total_gain_percent: Mapped[Decimal] = mapped_column(PERCENT, nullable=False)


class MarketEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "market_events"
    __table_args__ = (
        Index("ix_market_events_occurred_at", "occurred_at"),
        Index("ix_market_events_level_time", "level", "occurred_at"),
    )

    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    headline: Mapped[str] = mapped_column(String(500), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source_name: Mapped[str] = mapped_column(String(160), nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text)
    fingerprint: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    score: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    level: Mapped[str] = mapped_column(String(32), nullable=False)
    confidence: Mapped[Decimal] = mapped_column(PERCENT, nullable=False)
    unread: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    reasons: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list, nullable=False)
    ai_insight: Mapped[str | None] = mapped_column(Text)

    securities: Mapped[list["EventSecurityLink"]] = relationship(
        back_populates="event", cascade="all, delete-orphan"
    )


class EventSecurityLink(Base):
    __tablename__ = "event_security_links"

    event_id: Mapped[UUID] = mapped_column(
        ForeignKey("market_events.id", ondelete="CASCADE"), primary_key=True
    )
    security_id: Mapped[UUID] = mapped_column(
        ForeignKey("securities.id", ondelete="CASCADE"), primary_key=True
    )
    match_confidence: Mapped[Decimal] = mapped_column(PERCENT, nullable=False)
    effective_weight: Mapped[Decimal] = mapped_column(PERCENT, nullable=False)

    event: Mapped[MarketEvent] = relationship(back_populates="securities")
    security: Mapped[Security] = relationship()


class AssistantMessage(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "assistant_messages"
    __table_args__ = (Index("ix_assistant_messages_user_time", "user_id", "created_at"),)

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    section: Mapped[str | None] = mapped_column(String(16))
    sources: Mapped[list[dict[str, str]] | None] = mapped_column(JSON)


class Alert(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "alerts"
    __table_args__ = (UniqueConstraint("user_id", "event_id", "policy_version"),)

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    event_id: Mapped[UUID] = mapped_column(ForeignKey("market_events.id"), index=True)
    policy_version: Mapped[str] = mapped_column(String(40), nullable=False)
    channel: Mapped[str] = mapped_column(String(32), default="in_app", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)


class SyncRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "sync_runs"
    __table_args__ = (UniqueConstraint("connection_id", "idempotency_key"),)

    connection_id: Mapped[UUID] = mapped_column(ForeignKey("brokerage_connections.id"), index=True)
    status: Mapped[str] = mapped_column(String(48), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False)
    trigger: Mapped[str] = mapped_column(String(32), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    counts: Mapped[dict[str, int]] = mapped_column(JSON, default=dict, nullable=False)
    warnings: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list, nullable=False)
