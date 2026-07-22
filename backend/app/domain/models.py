from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import UUID

from app.domain.enums import (
    AssetType,
    DedupeReason,
    EventProvider,
    EventType,
    ImpactLevel,
    ImpactReasonCode,
    PositionChangeKind,
    RejectionReason,
    SyncRunStatus,
    SyncTrigger,
)


@dataclass(frozen=True, slots=True)
class PositionObservation:
    account_id: UUID
    observed_at: datetime
    provider_instrument_id: str | None
    symbol: str | None
    cusip: str | None
    asset_type: AssetType
    quantity: Decimal
    market_value: Decimal | None
    average_price: Decimal | None


@dataclass(frozen=True, slots=True)
class StoredPosition:
    position_id: UUID
    account_id: UUID
    security_id: UUID
    canonical_symbol: str
    quantity: Decimal
    market_value: Decimal | None
    average_price: Decimal | None


@dataclass(frozen=True, slots=True)
class SecurityIdentity:
    security_id: UUID
    canonical_symbol: str


@dataclass(frozen=True, slots=True)
class RejectedObservation:
    observation: PositionObservation
    reason: RejectionReason
    detail: str


@dataclass(frozen=True, slots=True)
class ReconciledPosition:
    account_id: UUID
    security_id: UUID
    canonical_symbol: str
    quantity: Decimal
    market_value: Decimal | None
    average_price: Decimal | None


@dataclass(frozen=True, slots=True)
class PositionDelta:
    account_id: UUID
    security_id: UUID
    kind: PositionChangeKind
    previous_quantity: Decimal
    current_quantity: Decimal
    quantity_delta: Decimal


@dataclass(frozen=True, slots=True)
class ReconciliationResult:
    positions: tuple[ReconciledPosition, ...]
    deltas: tuple[PositionDelta, ...]
    rejected: tuple[RejectedObservation, ...]


@dataclass(frozen=True, slots=True)
class ProviderEventEnvelope:
    provider: EventProvider
    provider_event_id: str | None
    source_name: str
    source_url: str | None
    headline: str
    summary: str | None
    published_at: datetime
    received_at: datetime
    symbols: tuple[str, ...]
    cik: str | None = None
    accession_number: str | None = None
    form_type: str | None = None
    raw_category: str | None = None


@dataclass(frozen=True, slots=True)
class SecurityMatch:
    security_id: UUID
    canonical_symbol: str
    confidence: float


@dataclass(frozen=True, slots=True)
class EventSourceRef:
    provider: EventProvider
    source_name: str
    source_url: str | None
    provider_event_id: str | None
    confidence: float = 1.0


@dataclass(frozen=True, slots=True)
class CanonicalEvent:
    event_id: UUID
    event_type: EventType
    headline: str
    summary: str | None
    occurred_at: datetime
    first_seen_at: datetime
    last_seen_at: datetime
    primary_source: EventSourceRef
    sources: tuple[EventSourceRef, ...]
    security_ids: tuple[UUID, ...]
    symbols: tuple[str, ...]
    cik: str | None
    accession_number: str | None
    form_type: str | None
    canonical_url: str | None
    fingerprint: str


@dataclass(frozen=True, slots=True)
class RejectedEvent:
    envelope: ProviderEventEnvelope
    reason: RejectionReason
    detail: str


@dataclass(frozen=True, slots=True)
class DedupePolicy:
    title_similarity_threshold: float = 0.90
    fuzzy_window: timedelta = timedelta(hours=18)
    provider_priority: Mapping[EventProvider, int] | None = None


@dataclass(frozen=True, slots=True)
class DuplicateCluster:
    canonical: CanonicalEvent
    merged_event_ids: tuple[UUID, ...]
    reasons: tuple[DedupeReason, ...]


@dataclass(frozen=True, slots=True)
class DedupeResult:
    events: tuple[CanonicalEvent, ...]
    clusters: tuple[DuplicateCluster, ...]


@dataclass(frozen=True, slots=True)
class ExposurePath:
    kind: str
    weight: Decimal
    via_security_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class PortfolioExposure:
    security_id: UUID
    symbol: str
    direct_weight: Decimal
    indirect_weight: Decimal
    market_value: Decimal
    paths: tuple[ExposurePath, ...] = ()


@dataclass(frozen=True, slots=True)
class EventAssessmentInput:
    event: CanonicalEvent
    exposures: tuple[PortfolioExposure, ...]
    source_confidence: float
    entity_match_confidence: float
    assessed_at: datetime
    previous_related_event_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class ScoreComponents:
    materiality: float
    exposure: float
    recency: float
    novelty: float
    confidence: float


@dataclass(frozen=True, slots=True)
class ImpactReason:
    code: ImpactReasonCode
    message: str
    value: float | str | None = None


@dataclass(frozen=True, slots=True)
class ImpactPolicy:
    version: str
    base_materiality: Mapping[EventType, float]
    form_materiality: Mapping[str, float]
    urgent_threshold: float = 80.0
    important_threshold: float = 60.0
    notable_threshold: float = 35.0
    max_event_age: timedelta = timedelta(days=7)
    novelty_window: timedelta = timedelta(days=2)
    immediate_alert_max_age: timedelta = timedelta(hours=24)
    minimum_alert_match_confidence: float = 0.75
    future_clock_skew: timedelta = timedelta(minutes=5)


@dataclass(frozen=True, slots=True)
class ImpactAssessment:
    score: float
    level: ImpactLevel
    components: ScoreComponents
    affected_security_ids: tuple[UUID, ...]
    effective_portfolio_weight: Decimal
    reasons: tuple[ImpactReason, ...]
    eligible_for_immediate_alert: bool
    policy_version: str


@dataclass(frozen=True, slots=True)
class SyncPortfolioCommand:
    user_id: UUID
    connection_id: UUID
    requested_by: SyncTrigger
    idempotency_key: str
    force_full_event_scan: bool = False


@dataclass(frozen=True, slots=True)
class ProviderWarning:
    provider: str
    code: str
    message: str
    retryable: bool


@dataclass(frozen=True, slots=True)
class SyncPortfolioResult:
    sync_run_id: UUID
    status: SyncRunStatus
    positions_seen: int
    positions_changed: int
    events_fetched: int
    events_created: int
    events_merged: int
    assessments_created: int
    alerts_created: int
    provider_warnings: tuple[ProviderWarning, ...] = ()
